"""
Daily scan scheduler — fires at 8:30 AM ET (Mon–Fri).
On startup: triggers immediately if it's a weekday and no scan ran today.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from .database import get_latest_session
from .scanner import is_scanning, start_scan_background

log = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except ImportError:
    from datetime import timezone as _tz
    ET = _tz(timedelta(hours=-5), "ET")

SCAN_HOUR   = 8
SCAN_MINUTE = 30


def _now_et() -> datetime:
    return datetime.now(tz=ET)


def _already_ran_today() -> bool:
    session = get_latest_session()
    if not session or not session.get("started_at"):
        return False
    try:
        raw = session["started_at"]
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt_utc = datetime.fromisoformat(raw)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        return dt_utc.astimezone(ET).date() == _now_et().date()
    except Exception:
        return False


def _next_scan_datetime() -> datetime:
    now = _now_et()
    target = now.replace(hour=SCAN_HOUR, minute=SCAN_MINUTE, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    return target


def get_schedule_info() -> dict:
    session   = get_latest_session()
    next_scan = _next_scan_datetime()

    data_age_hours = None
    last_status = session.get("status") if session else None

    if session and session.get("completed_at"):
        try:
            raw = session["completed_at"]
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            completed = datetime.fromisoformat(raw)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            data_age_hours = round(
                (datetime.now(timezone.utc) - completed).total_seconds() / 3600, 1
            )
        except Exception:
            pass

    return {
        "next_scan_et":        next_scan.strftime("%b %d, %Y %I:%M %p ET"),
        "next_scan_iso":       next_scan.isoformat(),
        "already_ran_today":   _already_ran_today(),
        "data_age_hours":      data_age_hours,
        "last_session_status": last_status,
        "scan_time_label":     f"Daily auto-scan at {SCAN_HOUR}:{SCAN_MINUTE:02d} AM ET (Mon–Fri)",
    }


def _scheduler_loop():
    log.info("[Scanner Scheduler] Started — target %02d:%02d ET weekdays", SCAN_HOUR, SCAN_MINUTE)
    while True:
        next_dt    = _next_scan_datetime()
        sleep_secs = (next_dt - _now_et()).total_seconds()
        log.info("[Scanner Scheduler] Next scan: %s (%.0fs away)",
                 next_dt.strftime("%Y-%m-%d %H:%M ET"), sleep_secs)
        time.sleep(max(sleep_secs, 1))

        now = _now_et()
        if now.weekday() < 5 and not _already_ran_today() and not is_scanning():
            log.info("[Scanner Scheduler] Firing scheduled daily scan")
            start_scan_background()
        else:
            log.info("[Scanner Scheduler] Skipping trigger (already ran today, scanning, or weekend)")

        time.sleep(120)


def start_scheduler():
    """Start the scheduler daemon. Call once at app startup."""
    if not _already_ran_today() and not is_scanning():
        now = _now_et()
        if now.weekday() < 5:
            log.info("[Scanner Scheduler] Startup: no scan today — starting scan now")
            start_scan_background()

    t = threading.Thread(target=_scheduler_loop, daemon=True, name="scan-scheduler")
    t.start()
