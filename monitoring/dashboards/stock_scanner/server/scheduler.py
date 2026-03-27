"""
Daily scan scheduler — fires a full scan once per day at 8:30 AM ET
(one hour before US markets open at 9:30 AM ET), Monday–Friday.

On app startup:
  • If it is a weekday AND the current ET time is between 8:00 AM and 5:00 PM
    AND no scan has run today → start an immediate scan.
  • Then a background thread sleeps until the next 8:30 AM ET and repeats.
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
    from zoneinfo import ZoneInfo          # Python 3.9+
    ET = ZoneInfo("America/New_York")
except ImportError:                        # fallback: fixed UTC-5 offset (close enough for scheduling)
    from datetime import timezone as _tz
    ET = _tz(timedelta(hours=-5), "ET")

SCAN_HOUR   = 8    # 8:30 AM ET
SCAN_MINUTE = 30


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_et() -> datetime:
    return datetime.now(tz=ET)


def _already_ran_today() -> bool:
    """True if a scan (any status) started today in ET time."""
    session = get_latest_session()
    if not session or not session.get("started_at"):
        return False
    try:
        raw = session["started_at"]
        # DB stores UTC without 'Z'; normalise
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt_utc = datetime.fromisoformat(raw)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        dt_et = dt_utc.astimezone(ET)
        return dt_et.date() == _now_et().date()
    except Exception as exc:
        log.debug("_already_ran_today parse error: %s", exc)
        return False


def _next_scan_datetime() -> datetime:
    """Return the next scheduled 8:30 AM ET on a weekday (≥ now)."""
    now = _now_et()
    target = now.replace(hour=SCAN_HOUR, minute=SCAN_MINUTE, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    # Skip weekends (Monday=0 … Sunday=6)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    return target


def get_schedule_info() -> dict:
    """Return schedule metadata consumed by the /api/scanner/schedule endpoint."""
    session   = get_latest_session()
    next_scan = _next_scan_datetime()

    data_age_hours: float | None = None
    last_status = session.get("status") if session else None

    if session and session.get("completed_at"):
        try:
            raw = session["completed_at"]
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            completed = datetime.fromisoformat(raw)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            age_secs = (datetime.now(timezone.utc) - completed).total_seconds()
            data_age_hours = round(age_secs / 3600, 1)
        except Exception:
            pass

    return {
        "next_scan_et":       next_scan.strftime("%b %d, %Y %I:%M %p ET"),
        "next_scan_iso":      next_scan.isoformat(),
        "already_ran_today":  _already_ran_today(),
        "data_age_hours":     data_age_hours,
        "last_session_status": last_status,
        "scan_time_label":    f"Daily auto-scan at {SCAN_HOUR}:{SCAN_MINUTE:02d} AM ET (Mon–Fri)",
    }


# ── Scheduler loop ─────────────────────────────────────────────────────────────

def _scheduler_loop():
    log.info(
        "[Scheduler] Daily scan scheduler started — target %02d:%02d ET, weekdays only",
        SCAN_HOUR, SCAN_MINUTE,
    )
    while True:
        next_dt    = _next_scan_datetime()
        sleep_secs = (next_dt - _now_et()).total_seconds()
        log.info(
            "[Scheduler] Next scheduled scan: %s (%.0fs away)",
            next_dt.strftime("%Y-%m-%d %H:%M ET"), sleep_secs,
        )
        time.sleep(max(sleep_secs, 1))

        # Double-check weekday and avoid duplicate
        now = _now_et()
        if now.weekday() < 5 and not _already_ran_today() and not is_scanning():
            log.info("[Scheduler] Firing scheduled daily scan")
            start_scan_background()
        else:
            log.info("[Scheduler] Skipping trigger (already ran today, scanning, or weekend)")

        # Brief pause so we don't loop immediately after a scan fires
        time.sleep(120)


# ── Public entry ───────────────────────────────────────────────────────────────

def start_scheduler():
    """
    Call once at app startup.
    • Triggers an immediate scan if it is a weekday, within the 8 AM–5 PM ET
      window, and no scan has run today.
    • Launches the long-running scheduler daemon thread.
    """
    now = _now_et()
    is_weekday      = now.weekday() < 5
    in_market_window = 8 <= now.hour < 17   # 8 AM – 5 PM ET

    if is_weekday and in_market_window and not _already_ran_today() and not is_scanning():
        log.info("[Scheduler] App startup: no scan found for today — starting scan now")
        start_scan_background()
    else:
        log.info(
            "[Scheduler] App startup: skipping immediate scan "
            "(weekday=%s, in_window=%s, ran_today=%s, scanning=%s)",
            is_weekday, in_market_window, _already_ran_today(), is_scanning(),
        )

    t = threading.Thread(target=_scheduler_loop, daemon=True, name="scan-scheduler")
    t.start()
