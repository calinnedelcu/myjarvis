"""
Mobile API — endpoints consumed by the Flutter phone client.

Phase 1 surface:
    GET  /api/mobile/health             liveness check (no auth — used to detect PC online)
    GET  /api/mobile/dashboard          slim dashboard payload
    POST /api/mobile/ask                stream brain reply via SSE; optional PC TTS playback

All non-health routes require Bearer token in Authorization header.
"""

import asyncio
import json
import threading
from datetime import datetime
from typing import Any

import psutil
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from ui.routes.auth import require_api_key


router = APIRouter(prefix="/api/mobile", tags=["mobile"])

# Shared singletons set by ui.dashboard.init_dashboard()
_brain = None
_tts = None
_stt = None


def set_runtime(brain=None, tts=None, stt=None) -> None:
    """Called from ui.dashboard at startup to wire in the live Brain + TTS + STT."""
    global _brain, _tts, _stt
    _brain = brain
    _tts = tts
    _stt = stt


# ── Health ───────────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict:
    """Cheap heartbeat used by the phone to detect PC reachability."""
    return {
        "ok": True,
        "time": datetime.now().isoformat(timespec="seconds"),
        "brain_ready": _brain is not None,
        "tts_ready": _tts is not None,
    }


# ── Slim dashboard ───────────────────────────────────────────────

@router.get("/dashboard", dependencies=[Depends(require_api_key)])
async def dashboard_mobile() -> dict:
    """Compact dashboard payload (<5KB) for phone home screen.

    Same data as /api/dashboard but stripped of HTML formatting and trimmed
    to mobile essentials.
    """
    data: dict[str, Any] = {}

    vm = psutil.virtual_memory()
    data["system"] = {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "ram_percent": vm.percent,
        "ram_used_gb": round(vm.used / (1024 ** 3), 1),
        "ram_total_gb": round(vm.total / (1024 ** 3), 1),
        "uptime_hours": round(
            (datetime.now().timestamp() - psutil.boot_time()) / 3600, 1
        ),
    }

    try:
        import requests
        resp = requests.get(
            "https://wttr.in/Bucharest?format=j1",
            timeout=4,
            headers={"User-Agent": "curl/7.68.0"},
        )
        cur = resp.json()["current_condition"][0]
        data["weather"] = {
            "city": "Bucharest",
            "temp_c": int(cur["temp_C"]),
            "feels_like": int(cur["FeelsLikeC"]),
            "description": cur["weatherDesc"][0]["value"],
            "humidity": int(cur["humidity"]),
        }
    except Exception:
        data["weather"] = None

    try:
        from tools.calendar_tool import get_schedule
        schedule = get_schedule(date="today")
        data["calendar"] = str(schedule)[:500] if schedule else "No events today."
    except Exception:
        data["calendar"] = None

    try:
        from tools.gmail import read_emails
        emails = read_emails(max_results=3)
        data["emails"] = str(emails)[:600] if emails else "Inbox empty."
    except Exception:
        data["emails"] = None

    try:
        from tools.spotify import spotify_now_playing
        data["spotify"] = str(spotify_now_playing())[:200]
    except Exception:
        data["spotify"] = None

    try:
        from tools.hue import hue_status
        data["lights"] = str(hue_status())[:200]
    except Exception:
        data["lights"] = None

    return data


# ── Ask (SSE streaming) ──────────────────────────────────────────

class AskRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    language: str = Field(default="en", pattern="^(en|ro)$")
    play_on_pc: bool = False


@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(req: AskRequest):
    """Stream brain reply as Server-Sent Events.

    Each event is JSON: {"type": "chunk", "text": "..."}.
    Final event: {"type": "done"}. Errors: {"type": "error", "message": "..."}.
    """
    if _brain is None:
        raise HTTPException(503, "Brain not initialized.")

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    full_reply_chunks: list[str] = []

    def _producer() -> None:
        """Drain the brain generator on a worker thread; push chunks to the asyncio queue."""
        try:
            for chunk in _brain.think_stream(req.text, req.language):
                full_reply_chunks.append(chunk)
                event = json.dumps({"type": "chunk", "text": chunk})
                asyncio.run_coroutine_threadsafe(queue.put(f"data: {event}\n\n"), loop)
        except Exception as exc:
            logger.exception("Mobile /ask brain stream failed")
            err = json.dumps({"type": "error", "message": str(exc)[:200]})
            asyncio.run_coroutine_threadsafe(queue.put(f"data: {err}\n\n"), loop)
        finally:
            done = json.dumps({"type": "done"})
            asyncio.run_coroutine_threadsafe(queue.put(f"data: {done}\n\n"), loop)
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    threading.Thread(target=_producer, daemon=True).start()

    async def _event_stream():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
        if req.play_on_pc and _tts is not None and full_reply_chunks:
            text = "".join(full_reply_chunks)
            try:
                threading.Thread(
                    target=_tts.speak,
                    args=(text,),
                    kwargs={"language": req.language},
                    daemon=True,
                ).start()
            except Exception:
                logger.exception("Mobile /ask play_on_pc failed")

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Transcribe (phone mic → text) ────────────────────────────────

@router.post("/transcribe", dependencies=[Depends(require_api_key)])
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("en"),
) -> dict:
    """Receive a WAV upload from the phone, return Whisper transcript."""
    if _stt is None:
        raise HTTPException(503, "STT not initialized.")
    if language not in ("en", "ro"):
        language = "en"

    wav_bytes = await audio.read()
    if not wav_bytes:
        raise HTTPException(400, "Empty audio upload.")

    loop = asyncio.get_event_loop()
    text, lang = await loop.run_in_executor(
        None, _stt.transcribe, wav_bytes, language
    )
    return {"text": text, "language": lang}


# ── Synthesize (text → audio for phone playback) ─────────────────

class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    language: str = Field(default="en", pattern="^(en|ro)$")


@router.post("/synthesize", dependencies=[Depends(require_api_key)])
async def synthesize(req: SynthesizeRequest):
    """Render text via the configured TTS engine, return WAV bytes."""
    if _tts is None:
        raise HTTPException(503, "TTS not initialized.")

    loop = asyncio.get_event_loop()
    wav = await loop.run_in_executor(
        None, _tts.synthesize_to_wav, req.text, req.language
    )
    if not wav:
        raise HTTPException(500, "TTS produced no audio.")

    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
