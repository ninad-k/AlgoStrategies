"""
FastAPI server for the US Stock Scanner.

Endpoints
─────────
POST /api/scanner/start                  Start a background scan
GET  /api/scanner/status                 Poll scan progress
GET  /api/scanner/results/{category}     Paginated results (multibagger | investment | swing_medium | swing_short)
GET  /api/scanner/stock/{symbol}         Full detail + score breakdown for one stock
GET  /api/scanner/sectors                Distinct sectors in the latest scan
GET  /api/scanner/sessions               List recent scan sessions
GET  /api/health                         Health check
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import get_connection, get_latest_session, get_results, get_sectors, init_db
from .scanner import get_scan_status, is_scanning, start_scan_background
from .scheduler import get_schedule_info, start_scheduler

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="US Stock Scanner",
    description="Multi-category US stock scanner — Rey Capital",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CLIENT_DIR = Path(__file__).parent.parent / "client"

# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    init_db()
    log.info("Database initialised")
    start_scheduler()
    log.info("Daily scan scheduler started")


# ── Static files ───────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    index = CLIENT_DIR / "index.html"
    return FileResponse(str(index)) if index.exists() else JSONResponse(
        {"message": "Stock Scanner API is running. Frontend not found."}
    )

if CLIENT_DIR.exists():
    app.mount("/client", StaticFiles(directory=str(CLIENT_DIR)), name="client")


# ── Scanner control ────────────────────────────────────────────────────────────

@app.post("/api/scanner/start")
def start_scan():
    if is_scanning():
        return {"status": "already_running", "message": "A scan is already in progress"}
    ok = start_scan_background()
    if ok:
        return {"status": "started", "message": "Full scan started in background"}
    return {"status": "error", "message": "Could not start scan"}


@app.get("/api/scanner/status")
def scan_status():
    st = get_scan_status()
    total = st.get("total_symbols") or 0
    done  = st.get("processed_symbols") or 0
    pct   = round(done / total * 100, 1) if total else 0
    return {**st, "progress_pct": pct}


# ── Results ────────────────────────────────────────────────────────────────────

VALID_CATEGORIES = {"multibagger", "investment", "swing_medium", "swing_short"}


@app.get("/api/scanner/results/{category}")
def get_scan_results(
    category: str,
    page:            int   = Query(default=1,    ge=1),
    page_size:       int   = Query(default=25,   ge=5, le=100),
    sort_by:         str   = Query(default=None),
    min_score:       float = Query(default=50.0, ge=0, le=100),
    sector:          str   = Query(default=None),
    min_market_cap:  float = Query(default=None),
    max_market_cap:  float = Query(default=None),
    session_id:      int   = Query(default=None),
):
    if category not in VALID_CATEGORIES:
        raise HTTPException(400, f"Invalid category. Choose from: {sorted(VALID_CATEGORIES)}")

    if session_id is None:
        latest = get_latest_session()
        if not latest:
            return {
                "total": 0, "page": 1, "page_size": page_size,
                "total_pages": 0, "results": [], "session": None,
            }
        session_id = latest["id"]

    data = get_results(
        session_id=session_id,
        category=category,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        min_score=min_score,
        sector=sector,
        min_market_cap=min_market_cap,
        max_market_cap=max_market_cap,
    )

    # Deserialise JSON columns
    for row in data["results"]:
        for field in ("red_flags", "score_breakdown"):
            if isinstance(row.get(field), str):
                try:
                    row[field] = json.loads(row[field])
                except Exception:
                    pass

    return data


@app.get("/api/scanner/stock/{symbol}")
def get_stock_detail(symbol: str, session_id: int = Query(default=None)):
    symbol = symbol.upper()
    if session_id is None:
        latest = get_latest_session()
        if not latest:
            raise HTTPException(404, "No scan data available")
        session_id = latest["id"]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM stock_scores WHERE session_id = ? AND symbol = ?",
            (session_id, symbol),
        ).fetchone()

    if not row:
        raise HTTPException(404, f"{symbol} not found in scan results")

    result = dict(row)
    for field in ("red_flags", "score_breakdown"):
        if isinstance(result.get(field), str):
            try:
                result[field] = json.loads(result[field])
            except Exception:
                pass
    return result


@app.get("/api/scanner/sectors")
def list_sectors(session_id: int = Query(default=None)):
    if session_id is None:
        latest = get_latest_session()
        if not latest:
            return {"sectors": []}
        session_id = latest["id"]
    return {"sectors": get_sectors(session_id)}


@app.get("/api/scanner/sessions")
def list_sessions():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, started_at, completed_at, status, total_symbols, processed_symbols "
            "FROM scan_sessions ORDER BY id DESC LIMIT 10"
        ).fetchall()
    return {"sessions": [dict(r) for r in rows]}


@app.get("/api/scanner/schedule")
def scan_schedule():
    """Return auto-scan schedule info and data cache age."""
    return get_schedule_info()


@app.get("/api/health")
def health():
    return {"status": "ok", "scanner": "running" if is_scanning() else "idle"}
