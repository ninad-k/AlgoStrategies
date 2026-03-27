"""
FastAPI server for the Market Sentiment Dashboard.

Endpoints:
  GET  /                        → Serve frontend dashboard
  GET  /api/symbols             → List all available symbols grouped
  GET  /api/analysis/{symbol}   → Full AI analysis for one symbol
  GET  /api/dashboard           → Bulk analysis for a list of symbols
  GET  /api/news/{symbol}       → Raw news for a symbol
  GET  /api/calendar            → Upcoming economic events
  POST /api/refresh/{symbol}    → Force-invalidate cache for a symbol
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import analyze_symbol
from .config import CACHE_TTL, DEFAULT_SYMBOLS, DISPLAY_NAMES, SYMBOL_GROUPS, TICKER_MAP
from .data import fetch_economic_calendar, fetch_news, fetch_ohlcv, fetch_price
from .models import DashboardResponse, EconomicEvent, NewsArticle, SymbolAnalysis
from .technical import compute_technical_levels
from .scanner.database import (
    get_connection as sc_get_conn,
    get_latest_session as sc_latest_session,
    get_results as sc_get_results,
    get_sectors as sc_get_sectors,
    init_db as sc_init_db,
)
from .scanner.scanner import get_scan_status, is_scanning, start_scan_background
from .scanner.scheduler import get_schedule_info, start_scheduler

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Rey Capital Dashboard",
    description="AI-powered market analysis + US Stock Scanner",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files / frontend ───────────────────────────────────────────────────
CLIENT_DIR = Path(__file__).parent.parent / "client"


@app.get("/", include_in_schema=False)
def root():
    index = CLIENT_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "Market Sentiment API is running. Frontend not found."})


# Mount static assets (CSS, JS) if the directory exists
_static_dir = CLIENT_DIR / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ── In-memory cache ───────────────────────────────────────────────────────────

_analysis_cache: dict[str, tuple[float, SymbolAnalysis]] = {}  # symbol → (ts, result)
_calendar_cache: tuple[float, list[EconomicEvent]] | None = None

# ── News cache (per-symbol, longer TTL) ──────────────────────────────────────
_news_cache: dict[str, tuple[float, list[NewsArticle]]] = {}  # symbol → (ts, articles)
NEWS_CACHE_TTL = 4 * 3600  # 4 hours


def _news_cache_get(symbol: str) -> list[NewsArticle] | None:
    entry = _news_cache.get(symbol)
    if entry and (time.time() - entry[0]) < NEWS_CACHE_TTL:
        return entry[1]
    return None


def _news_cache_set(symbol: str, articles: list[NewsArticle]):
    _news_cache[symbol] = (time.time(), articles)


def _cache_get(symbol: str) -> Optional[SymbolAnalysis]:
    entry = _analysis_cache.get(symbol)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1]
    return None


def _cache_set(symbol: str, analysis: SymbolAnalysis):
    _analysis_cache[symbol] = (time.time(), analysis)


def _get_group(symbol: str) -> str:
    for group, symbols in SYMBOL_GROUPS.items():
        if symbol in symbols:
            return group
    return "Other"


# ── Core analysis pipeline ────────────────────────────────────────────────────

async def _run_analysis(symbol: str, force: bool = False) -> SymbolAnalysis:
    if not force:
        cached = _cache_get(symbol)
        if cached:
            return cached

    # Run all I/O in thread pool to avoid blocking the event loop
    loop = asyncio.get_event_loop()

    price, ohlcv = await asyncio.gather(
        loop.run_in_executor(None, fetch_price, symbol),
        loop.run_in_executor(None, fetch_ohlcv, symbol, "1y", "1d"),
    )

    # Check news cache first (only use cache if it has articles)
    cached_news = _news_cache_get(symbol)
    if cached_news:
        news = cached_news
    else:
        news = await loop.run_in_executor(None, fetch_news, symbol)
        if news:  # only cache non-empty results
            _news_cache_set(symbol, news)

    if price is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not fetch price data for '{symbol}'. Check if the symbol is supported.",
        )

    # Update display name on price object
    price.display_name = DISPLAY_NAMES.get(symbol, symbol)

    technical = compute_technical_levels(ohlcv)
    if technical is None:
        # Build a minimal placeholder so analysis can still run
        from .models import TechnicalLevels
        technical = TechnicalLevels(
            pivot=price.current_price,
            supports=[
                round(price.current_price * 0.99, 4),
                round(price.current_price * 0.97, 4),
                round(price.current_price * 0.95, 4),
            ],
            resistances=[
                round(price.current_price * 1.01, 4),
                round(price.current_price * 1.03, 4),
                round(price.current_price * 1.05, 4),
            ],
            swing_supports=[],
            swing_resistances=[],
            rsi_14=50.0,
            macd_signal="NEUTRAL",
            trend_signal="SIDEWAYS",
            atr=None,
        )

    # Fetch calendar (cached separately)
    events = await _get_calendar()

    display_name = DISPLAY_NAMES.get(symbol, symbol)
    group = _get_group(symbol)
    analysis = await loop.run_in_executor(
        None,
        analyze_symbol,
        symbol, display_name, group, price, technical, news, events,
    )

    _cache_set(symbol, analysis)
    return analysis


async def _get_calendar() -> list[EconomicEvent]:
    global _calendar_cache
    CALENDAR_CACHE_TTL = 12 * 3600  # 12 hours
    if _calendar_cache and (time.time() - _calendar_cache[0]) < CALENDAR_CACHE_TTL:
        return _calendar_cache[1]
    loop = asyncio.get_event_loop()
    events = await loop.run_in_executor(None, fetch_economic_calendar)
    _calendar_cache = (time.time(), events)
    return events


# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/api/symbols")
def list_symbols():
    return {
        "groups": SYMBOL_GROUPS,
        "all": list(TICKER_MAP.keys()),
        "defaults": DEFAULT_SYMBOLS,
    }


@app.get("/api/analysis/{symbol}")
async def get_analysis(symbol: str):
    symbol = symbol.upper().replace("-", "/")
    analysis = await _run_analysis(symbol)
    return analysis


@app.get("/api/dashboard")
async def get_dashboard(
    symbols: str = Query(
        default=",".join(DEFAULT_SYMBOLS),
        description="Comma-separated list of symbols",
    )
):
    requested = [s.strip().upper().replace("-", "/") for s in symbols.split(",") if s.strip()]
    valid = list(dict.fromkeys(requested))  # deduplicate, preserve order
    if not valid:
        raise HTTPException(status_code=400, detail="No valid symbols provided.")

    # Analyse all symbols concurrently
    tasks = [_run_analysis(s) for s in valid]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    analyses: list[SymbolAnalysis] = []
    for sym, res in zip(valid, results):
        if isinstance(res, Exception):
            log.error("Dashboard analysis failed for %s: %s", sym, res)
        else:
            analyses.append(res)

    events = await _get_calendar()
    cache_hits = all(
        _analysis_cache.get(s) is not None
        for s in valid
    )

    return DashboardResponse(
        symbols=analyses,
        events=events,
        generated_at=datetime.now(timezone.utc).isoformat(),
        cache_hit=cache_hits,
    )


@app.get("/api/news/{symbol}")
async def get_news(symbol: str):
    symbol = symbol.upper().replace("-", "/")
    loop = asyncio.get_event_loop()
    news = await loop.run_in_executor(None, fetch_news, symbol)
    return {"symbol": symbol, "articles": news, "count": len(news)}


@app.get("/api/calendar")
async def get_calendar():
    events = await _get_calendar()
    return {"events": events, "count": len(events)}


@app.post("/api/refresh/{symbol}")
async def refresh_symbol(symbol: str):
    symbol = symbol.upper().replace("-", "/")
    # Invalidate both analysis and news cache
    _analysis_cache.pop(symbol, None)
    _news_cache.pop(symbol, None)
    analysis = await _run_analysis(symbol, force=True)
    return {"message": f"Refreshed {symbol}", "analysis": analysis}


@app.get("/api/health")
def health():
    from .config import AI_PROVIDER, ANTHROPIC_API_KEY, GROQ_API_KEY, OPENAI_API_KEY
    return {
        "status": "ok",
        "ai_provider": AI_PROVIDER,
        "groq_key_set": bool(GROQ_API_KEY),
        "anthropic_key_set": bool(ANTHROPIC_API_KEY),
        "openai_key_set": bool(OPENAI_API_KEY),
        "cached_symbols": list(_analysis_cache.keys()),
        "scanner": "running" if is_scanning() else "idle",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    sc_init_db()
    start_scheduler()
    log.info("Stock scanner DB initialised + daily scheduler started")


# ══════════════════════════════════════════════════════════════════════════════
# Stock Scanner API Routes
# ══════════════════════════════════════════════════════════════════════════════

_VALID_CATEGORIES = {"multibagger", "investment", "swing_medium", "swing_short"}


@app.post("/api/scanner/start")
def scanner_start():
    if is_scanning():
        return {"status": "already_running", "message": "A scan is already in progress"}
    ok = start_scan_background()
    if ok:
        return {"status": "started", "message": "Full scan started in background"}
    return {"status": "error", "message": "Could not start scan"}


@app.get("/api/scanner/status")
def scanner_status():
    st = get_scan_status()
    total = st.get("total_symbols") or 0
    done  = st.get("processed_symbols") or 0
    pct   = round(done / total * 100, 1) if total else 0
    return {**st, "progress_pct": pct}


@app.get("/api/scanner/schedule")
def scanner_schedule():
    return get_schedule_info()


@app.get("/api/scanner/results/{category}")
def scanner_results(
    category: str,
    page:           int   = Query(default=1,    ge=1),
    page_size:      int   = Query(default=25,   ge=5, le=100),
    sort_by:        str   = Query(default=None),
    min_score:      float = Query(default=50.0, ge=0, le=100),
    sector:         str   = Query(default=None),
    min_market_cap: float = Query(default=None),
    max_market_cap: float = Query(default=None),
    session_id:     int   = Query(default=None),
):
    if category not in _VALID_CATEGORIES:
        raise HTTPException(400, f"Invalid category. Choose from: {sorted(_VALID_CATEGORIES)}")

    if session_id is None:
        latest = sc_latest_session()
        if not latest:
            return {"total": 0, "page": 1, "page_size": page_size,
                    "total_pages": 0, "results": [], "session": None}
        session_id = latest["id"]

    data = sc_get_results(
        session_id=session_id, category=category, page=page,
        page_size=page_size, sort_by=sort_by, min_score=min_score,
        sector=sector, min_market_cap=min_market_cap, max_market_cap=max_market_cap,
    )

    for row in data["results"]:
        for field in ("red_flags", "score_breakdown", "ai_insight"):
            if isinstance(row.get(field), str):
                try:
                    row[field] = json.loads(row[field])
                except Exception:
                    pass

    return data


@app.get("/api/scanner/stock/{symbol}")
def scanner_stock(symbol: str, session_id: int = Query(default=None)):
    symbol = symbol.upper()
    if session_id is None:
        latest = sc_latest_session()
        if not latest:
            raise HTTPException(404, "No scan data available")
        session_id = latest["id"]

    with sc_get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM stock_scores WHERE session_id = ? AND symbol = ?",
            (session_id, symbol),
        ).fetchone()

    if not row:
        raise HTTPException(404, f"{symbol} not found in scan results")

    result = dict(row)
    for field in ("red_flags", "score_breakdown", "ai_insight"):
        if isinstance(result.get(field), str):
            try:
                result[field] = json.loads(result[field])
            except Exception:
                pass
    return result


@app.get("/api/scanner/sectors")
def scanner_sectors(session_id: int = Query(default=None)):
    if session_id is None:
        latest = sc_latest_session()
        if not latest:
            return {"sectors": []}
        session_id = latest["id"]
    return {"sectors": sc_get_sectors(session_id)}


@app.get("/api/scanner/sessions")
def scanner_sessions():
    with sc_get_conn() as conn:
        rows = conn.execute(
            "SELECT id, started_at, completed_at, status, total_symbols, processed_symbols "
            "FROM scan_sessions ORDER BY id DESC LIMIT 10"
        ).fetchall()
    return {"sessions": [dict(r) for r in rows]}
