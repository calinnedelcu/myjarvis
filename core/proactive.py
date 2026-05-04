"""
Proactive notification pollers — Phase 3.

Background daemon threads that periodically check Gmail + Google Calendar
and push FCM notifications to registered phones for:

  - New unread emails (60s poll, dedupe by message id)
  - Upcoming calendar events (60s poll, fires once 10 min before each event)

All work happens off the main pipeline; failures are logged and never raise.
Config knobs live under `mobile.notifications` in config.yaml:

    mobile:
      notifications:
        enabled: true
        email_poll_seconds: 60
        calendar_lead_minutes: 10
        calendar_poll_seconds: 60
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from core import notifications


_started = False
_seen_email_ids: set[str] = set()
_notified_event_ids: set[str] = set()
_state_path = Path(__file__).resolve().parent.parent / "data" / "proactive_state.txt"


def _load_state() -> None:
    """Restore the de-dupe sets so a restart doesn't re-fire old notifications."""
    if not _state_path.is_file():
        return
    try:
        for line in _state_path.read_text().splitlines():
            if line.startswith("E:"):
                _seen_email_ids.add(line[2:])
            elif line.startswith("C:"):
                _notified_event_ids.add(line[2:])
    except Exception as exc:
        logger.warning(f"proactive: failed to load state: {exc}")


def _save_state() -> None:
    try:
        _state_path.parent.mkdir(parents=True, exist_ok=True)
        # Trim to last ~500 of each to keep the file small.
        emails = list(_seen_email_ids)[-500:]
        events = list(_notified_event_ids)[-500:]
        lines = [f"E:{e}" for e in emails] + [f"C:{c}" for c in events]
        _state_path.write_text("\n".join(lines))
    except Exception as exc:
        logger.warning(f"proactive: failed to save state: {exc}")


# ─────────────────────────────────────────────────────────────────
# Email poller
# ─────────────────────────────────────────────────────────────────

def _poll_emails(poll_seconds: int) -> None:
    """Loop: fetch unread emails, push notifications for new ones."""
    # Prime the seen set with current unread on first run so we don't spam
    # the phone with every existing unread email at startup.
    bootstrap = True
    while True:
        try:
            from tools.gmail import _get_gmail_service, _parse_message
            service = _get_gmail_service()
            result = service.users().messages().list(
                userId="me", q="is:unread", maxResults=10
            ).execute()
            messages = result.get("messages", []) or []
            new_ids = []
            for m in messages:
                if m["id"] in _seen_email_ids:
                    continue
                if bootstrap:
                    _seen_email_ids.add(m["id"])
                    continue
                new_ids.append(m["id"])

            for mid in new_ids:
                try:
                    full = service.users().messages().get(
                        userId="me", id=mid, format="full"
                    ).execute()
                    parsed = _parse_message(full)
                    sender = parsed["from"].split("<")[0].strip(" \"'")
                    title = f"📧 {sender or 'New email'}"[:80]
                    body = (parsed["subject"] or parsed["snippet"])[:120]
                    notifications.push_async(
                        title, body,
                        data={"kind": "email", "message_id": mid},
                    )
                except Exception as exc:
                    logger.warning(f"proactive email parse failed: {exc}")
                _seen_email_ids.add(mid)

            if bootstrap:
                logger.info(
                    f"proactive: bootstrapped with {len(_seen_email_ids)} known emails"
                )
                bootstrap = False
            elif new_ids:
                _save_state()

        except Exception as exc:
            logger.debug(f"proactive email poll: {exc}")

        time.sleep(max(poll_seconds, 30))


# ─────────────────────────────────────────────────────────────────
# Calendar poller
# ─────────────────────────────────────────────────────────────────

def _poll_calendar(poll_seconds: int, lead_minutes: int) -> None:
    """Loop: notify ~lead_minutes before each upcoming event (once per event)."""
    while True:
        try:
            from tools.calendar_tool import _get_calendar_service
            service = _get_calendar_service()
            now = datetime.now(timezone.utc)
            window_end = now + timedelta(minutes=lead_minutes + 5)

            events_result = service.events().list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=window_end.isoformat(),
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            for ev in events_result.get("items", []) or []:
                ev_id = ev.get("id", "")
                if not ev_id or ev_id in _notified_event_ids:
                    continue
                start = ev.get("start", {})
                if "dateTime" not in start:
                    continue  # skip all-day
                dt_start = datetime.fromisoformat(start["dateTime"])
                if dt_start.tzinfo is None:
                    dt_start = dt_start.replace(tzinfo=timezone.utc)
                minutes_until = (dt_start - now).total_seconds() / 60
                if minutes_until > lead_minutes or minutes_until < -1:
                    continue

                title_text = ev.get("summary", "(untitled)")
                location = ev.get("location", "")
                local_time = dt_start.astimezone().strftime("%H:%M")
                title = f"🗓 In {round(minutes_until)} min: {title_text}"[:80]
                body = local_time + (f" · {location}" if location else "")
                notifications.push_async(
                    title, body,
                    data={"kind": "calendar", "event_id": ev_id},
                )
                _notified_event_ids.add(ev_id)
                _save_state()

        except Exception as exc:
            logger.debug(f"proactive calendar poll: {exc}")

        time.sleep(max(poll_seconds, 30))


# ─────────────────────────────────────────────────────────────────
# Public entry
# ─────────────────────────────────────────────────────────────────

def start(config: dict) -> None:
    """Spawn both pollers as daemon threads. Idempotent."""
    global _started
    if _started:
        return
    notif_cfg = config.get("mobile", {}).get("notifications", {})
    if not notif_cfg.get("enabled", True):
        logger.info("Proactive notifications disabled via config.")
        return

    _load_state()

    email_seconds = int(notif_cfg.get("email_poll_seconds", 60))
    cal_seconds = int(notif_cfg.get("calendar_poll_seconds", 60))
    cal_lead = int(notif_cfg.get("calendar_lead_minutes", 10))

    threading.Thread(
        target=_poll_emails, args=(email_seconds,),
        name="jarvis-email-poller", daemon=True,
    ).start()
    threading.Thread(
        target=_poll_calendar, args=(cal_seconds, cal_lead),
        name="jarvis-calendar-poller", daemon=True,
    ).start()
    _started = True
    logger.info(
        f"Proactive pollers started (email {email_seconds}s, "
        f"calendar {cal_seconds}s, lead {cal_lead}min)"
    )
