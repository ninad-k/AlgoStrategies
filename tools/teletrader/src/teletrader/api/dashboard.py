"""Dashboard API endpoints for TeleTrader signal analytics."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger("teletrader.dashboard")

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _get_store(request: Request):
    """Get signal store from app state."""
    return request.app.state.signal_store


@router.get("/signals")
def dashboard_signals(
    request: Request,
    source: str | None = None,
    symbol: str | None = None,
    from_dt: str | None = None,
    to_dt: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Return filtered signal list for dashboard table."""
    store = _get_store(request)
    if not hasattr(store, "list_signals"):
        return {"signals": [], "error": "Dashboard queries require SQLite store"}

    signals = store.list_signals(
        source=source, symbol=symbol, from_dt=from_dt, to_dt=to_dt,
        limit=limit, offset=offset,
    )
    return {
        "signals": [s.to_ea_dict() for s in signals],
        "count": len(signals),
    }


@router.get("/stats")
def dashboard_stats(request: Request) -> dict:
    """Return aggregate stats: counts by source, by symbol."""
    store = _get_store(request)
    if not hasattr(store, "get_stats"):
        return {"error": "Dashboard queries require SQLite store"}
    return store.get_stats()


@router.get("/daily")
def dashboard_daily(request: Request, days: int = 30) -> dict:
    """Return daily signal counts for the last N days."""
    store = _get_store(request)
    if not hasattr(store, "get_daily_counts"):
        return {"error": "Dashboard queries require SQLite store"}
    return {"daily": store.get_daily_counts(days)}


# --- Serve the dashboard HTML page ---

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

html_router = APIRouter(tags=["dashboard-ui"])


@html_router.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard() -> HTMLResponse:
    """Serve the single-page dashboard."""
    html_path = _STATIC_DIR / "dashboard.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))
