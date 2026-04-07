"""
Phase 9 — Web Dashboard + Claude Code Terminal
FastAPI backend serving dashboard data + WebSocket for Claude terminal.
"""

import asyncio
import json
import re
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07')


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

_STATIC = Path(__file__).parent / "static"
_PROJECT = Path(__file__).resolve().parent.parent
_config: dict = {}
_claude_history: list[dict] = []  # shared conversation log
_rate_limit_info: dict = {}  # cached Claude session usage limits
_skip_continue: bool = False  # when True, next claude call omits --continue (fresh conversation)


def should_skip_continue() -> bool:
    """Check and reset the skip-continue flag. Returns True once after /clear."""
    global _skip_continue
    if _skip_continue:
        _skip_continue = False
        return True
    return False

from ui.routes import brain, briefing, projects, ide, settings
from ui.db_managers import voice_db

app = FastAPI(title="J.A.R.V.I.S. Dashboard")
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

# Include the modular routers
app.include_router(brain.router)
app.include_router(briefing.router)
app.include_router(projects.router)
app.include_router(ide.router)
app.include_router(settings.router)


def init_dashboard(config: dict) -> None:
    global _config
    _config = config


# ── Dashboard data endpoints ─────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return (_STATIC / "index.html").read_text(encoding="utf-8")

@app.post("/api/quick-action")
async def quick_action(data: dict):
    action = data.get("action", "")
    try:
        if action == "lights off":
            from tools.hue import lights_control
            result = lights_control(action="off")
        elif action == "play music":
            from tools.spotify import spotify_control
            result = spotify_control(action="play")
        elif action == "read emails":
            from tools.gmail import read_emails
            result = read_emails(max_results=5)
        elif action == "lock pc":
            import subprocess
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
            result = "PC locked."
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
        return {"status": "success", "action": action, "message": str(result)[:200]}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}

@app.get("/api/voice-log")
async def get_voice_log():
    return voice_db.get_today_logs()

@app.get("/api/dashboard")
async def dashboard_data():
    """Return all dashboard card data in one call."""
    data: dict[str, Any] = {}

    # System info
    data["system"] = {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_percent": psutil.virtual_memory().percent,
        "ram_used_gb": round(psutil.virtual_memory().used / (1024**3), 1),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "uptime_hours": round((datetime.now().timestamp() - psutil.boot_time()) / 3600, 1),
    }

    # Weather
    try:
        import requests
        resp = requests.get("https://wttr.in/Bucharest?format=j1",
                          timeout=5, headers={"User-Agent": "curl/7.68.0"})
        w = resp.json()
        cur = w["current_condition"][0]
        data["weather"] = {
            "city": "Bucharest",
            "temp_c": cur["temp_C"],
            "feels_like": cur["FeelsLikeC"],
            "description": cur["weatherDesc"][0]["value"],
            "humidity": cur["humidity"],
            "wind_kmph": cur["windspeedKmph"],
        }
    except Exception:
        data["weather"] = None

    # Calendar (today)
    try:
        from tools.calendar_tool import get_schedule
        data["calendar"] = get_schedule(date="today")
    except Exception:
        data["calendar"] = "Could not load calendar."

    # Emails (last 5)
    try:
        from tools.gmail import read_emails
        data["emails"] = read_emails(max_results=5)
    except Exception:
        data["emails"] = "Could not load emails."

    # Spotify
    try:
        from tools.spotify import spotify_now_playing
        data["spotify"] = spotify_now_playing()
    except Exception:
        data["spotify"] = "Could not check Spotify."

    # Lights
    try:
        from tools.hue import hue_status
        data["lights"] = hue_status()
    except Exception:
        data["lights"] = "Could not check lights."

    return data


@app.get("/api/system")
async def system_info():
    """Live system stats for auto-refresh."""
    gpu_pct = 0
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            gpu_pct = int(result.stdout.strip().split('\n')[0])
    except Exception:
        pass
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "ram_percent": psutil.virtual_memory().percent,
        "ram_used_gb": round(psutil.virtual_memory().used / (1024**3), 1),
        "gpu_percent": gpu_pct,
        "time": datetime.now().strftime("%H:%M:%S"),
    }


@app.get("/api/claude-limit")
async def claude_limit():
    """Return cached Claude session usage limits."""
    return _rate_limit_info




# ── Claude Code WebSocket terminal ───────────────────────────────

_ws_clients: list[WebSocket] = []
_history_ids: set = set()  # track saved message hashes to prevent duplicates


def _add_to_history(role: str, content: str):
    """Add a message to history with deduplication."""
    msg_id = f"{role}:{hash(content)}"
    if msg_id in _history_ids:
        return
    _history_ids.add(msg_id)
    _claude_history.append({
        "role": role,
        "content": content,
        "time": datetime.now().strftime("%H:%M:%S"),
    })


async def _broadcast(msg: dict):
    """Send a message to all connected WebSocket clients."""
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


def broadcast_to_clients(msg: dict):
    """Thread-safe broadcast to all WebSocket clients. Callable from any thread."""
    if _main_loop is None:
        return
    try:
        asyncio.run_coroutine_threadsafe(_broadcast(msg), _main_loop)
    except Exception:
        pass


def _run_claude_streaming(prompt: str):
    """Run claude -p in a subprocess and stream output to WebSocket clients."""
    global _rate_limit_info
    _add_to_history("user", prompt)

    broadcast_to_clients({"type": "user", "content": prompt})
    broadcast_to_clients({"type": "claude_working", "content": "true"})

    try:
        global _claude_proc
        cmd = ["claude", "-p", prompt]
        if not should_skip_continue():
            cmd.append("--continue")
        cmd += ["--output-format", "stream-json", "--verbose",
                "--include-partial-messages",
                "--dangerously-skip-permissions"]
        env = {**__import__('os').environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(_PROJECT), env=env,
        )
        _claude_proc = proc

        full_text_parts = []
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # Non-JSON line — forward as text
                clean = _strip_ansi(line)
                broadcast_to_clients({"type": "claude_stream", "content": clean + "\n"})
                full_text_parts.append(clean + "\n")
                continue

            evt_type = event.get("type")

            if evt_type == "stream_event":
                inner = event.get("event", {})
                inner_type = inner.get("type", "")

                # Text streaming
                if inner_type == "content_block_delta":
                    delta = inner.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            broadcast_to_clients({"type": "claude_stream", "content": text})
                            full_text_parts.append(text)

                # Tool use — show what Claude is doing
                elif inner_type == "content_block_start":
                    cb = inner.get("content_block", {})
                    if cb.get("type") == "tool_use":
                        tool_name = cb.get("name", "unknown")
                        tool_msg = f"\n🔧 **{tool_name}**\n"
                        broadcast_to_clients({"type": "claude_stream", "content": tool_msg})
                        full_text_parts.append(tool_msg)

                # Tool input streaming (shows what Claude is passing to the tool)
                elif inner_type == "content_block_delta":
                    delta = inner.get("delta", {})
                    if delta.get("type") == "input_json_delta":
                        pass  # skip raw JSON input — too noisy

            elif evt_type == "tool_use_event":
                # Tool execution result
                tool_name = event.get("tool_name", "")
                tool_result = event.get("tool_result", "")
                if tool_result:
                    result_preview = str(tool_result)[:300]
                    result_msg = f"```\n{result_preview}\n```\n"
                    broadcast_to_clients({"type": "claude_stream", "content": result_msg})
                    full_text_parts.append(result_msg)

            elif evt_type == "rate_limit_event":
                info = event.get("rate_limit_info", {})
                if info:
                    _rate_limit_info = info
                    broadcast_to_clients({"type": "rate_limit", "info": info})

            elif evt_type == "result":
                # Final result — use its text if we missed streaming
                if not full_text_parts and event.get("result"):
                    full_text_parts.append(event["result"])
                    broadcast_to_clients({"type": "claude_stream", "content": event["result"]})

        proc.wait()
        full_output = "".join(full_text_parts).strip()
        broadcast_to_clients({"type": "claude_working", "content": "false"})

        _add_to_history("assistant", full_output)
        broadcast_to_clients({"type": "claude_done", "content": full_output})

    except Exception as exc:
        error_msg = f"Error: {exc}"
        broadcast_to_clients({"type": "claude_working", "content": "false"})
        broadcast_to_clients({"type": "claude_error", "content": error_msg})
        _add_to_history("error", error_msg)


_main_loop: asyncio.AbstractEventLoop = None
_claude_proc: subprocess.Popen = None  # track running claude process


def _probe_claude_usage():
    """Run a minimal Claude CLI command to get current rate limit info."""
    global _rate_limit_info
    try:
        env = {**__import__('os').environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen(
            ["claude", "-p", "hi", "--output-format", "stream-json",
             "--verbose", "--no-session-persistence",
             "--dangerously-skip-permissions"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(_PROJECT), env=env,
        )
        import time as _t
        deadline = _t.time() + 30
        for line in proc.stdout:
            if _t.time() > deadline:
                break
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "rate_limit_event":
                info = event.get("rate_limit_info", {})
                if info:
                    _rate_limit_info = info
                    broadcast_to_clients({"type": "rate_limit", "info": info})
                    break
        try:
            proc.kill()
        except Exception:
            pass
        proc.wait(timeout=5)
    except Exception as e:
        logger.debug(f"Claude usage probe failed: {e}")


def _usage_poll_loop():
    """Background loop to periodically probe Claude rate limits."""
    import time
    time.sleep(10)  # Wait for server to be ready
    while True:
        _probe_claude_usage()
        time.sleep(300)  # Every 5 minutes


@app.websocket("/ws/claude")
async def claude_terminal(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)

    # Send full history in order on connect
    await ws.send_json({"type": "history", "messages": [
        {"role": m["role"], "content": m["content"], "time": m.get("time", "")}
        for m in _claude_history
    ]})

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "stop":
                if _claude_proc and _claude_proc.poll() is None:
                    _claude_proc.kill()
                    broadcast_to_clients({"type": "claude_working", "content": "false"})
                    broadcast_to_clients({"type": "claude_error", "content": "Task cancelled."})
            elif msg.get("type") == "command":
                cmd = msg.get("name", "")
                if cmd == "clear":
                    global _skip_continue
                    _claude_history.clear()
                    _history_ids.clear()
                    _skip_continue = True
                    broadcast_to_clients({"type": "cleared"})
            elif msg.get("type") == "prompt":
                prompt = msg["content"]
                # Handle pasted screenshot
                if msg.get("image"):
                    import base64
                    img_data = msg["image"].split(",", 1)[1]
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    img_path = _PROJECT / "data" / "screenshots" / f"clipboard_{ts}.png"
                    img_path.parent.mkdir(parents=True, exist_ok=True)
                    img_path.write_bytes(base64.b64decode(img_data))
                    prompt = (
                        f"{prompt}\n\n"
                        f"[User pasted a screenshot saved at: {img_path}]"
                    )
                threading.Thread(
                    target=_run_claude_streaming,
                    args=(prompt,),
                    daemon=True,
                ).start()
    except WebSocketDisconnect:
        _ws_clients.remove(ws)


# ── Server startup ───────────────────────────────────────────────

def start_dashboard(config: dict, port: int = 9000):
    """Start the dashboard server in a background thread."""
    global _main_loop
    init_dashboard(config)

    # Ensure static dir exists
    _STATIC.mkdir(parents=True, exist_ok=True)

    import uvicorn

    def _run():
        global _main_loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _main_loop = loop

            config_uv = uvicorn.Config(
                app, host="0.0.0.0", port=port,
                log_level="warning", loop="asyncio",
            )
            server = uvicorn.Server(config_uv)
            loop.run_until_complete(server.serve())
        except Exception as exc:
            logger.error(f"Dashboard server crashed: {exc}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    # Start Claude usage polling (seeds rate limit info on startup)
    threading.Thread(target=_usage_poll_loop, daemon=True, name="claude-usage-poll").start()
    # Wait briefly to confirm server actually starts
    import time
    time.sleep(1)
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            logger.info(f"Dashboard server started on http://localhost:{port}")
    except OSError:
        logger.warning(f"Dashboard server may have failed to start on port {port}")
