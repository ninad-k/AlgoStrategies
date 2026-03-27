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

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import analyze_symbol
from .config import CACHE_TTL, DEFAULT_SYMBOLS, DISPLAY_NAMES, SYMBOL_GROUPS, TICKER_MAP
from .data import fetch_economic_calendar, fetch_news, fetch_ohlcv, fetch_price
from .models import DashboardResponse, EconomicEvent, NewsArticle, SymbolAnalysis
from .technical import compute_technical_levels

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Market Sentiment Dashboard",
    description="AI-powered market analysis using Claude",
    version="1.0.0",
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

    price, ohlcv, news = await asyncio.gather(
        loop.run_in_executor(None, fetch_price, symbol),
        loop.run_in_executor(None, fetch_ohlcv, symbol, "1y", "1d"),
        loop.run_in_executor(None, fetch_news, symbol),
    )

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
    if _calendar_cache and (time.time() - _calendar_cache[0]) < CACHE_TTL:
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
    # Invalidate cache
    _analysis_cache.pop(symbol, None)
    analysis = await _run_analysis(symbol, force=True)
    return {"message": f"Refreshed {symbol}", "analysis": analysis}


@app.get("/api/health")
def health():
    from .config import AI_PROVIDER, ANTHROPIC_API_KEY, GROQ_API_KEY
    return {
        "status": "ok",
        "ai_provider": AI_PROVIDER,
        "anthropic_key_set": bool(ANTHROPIC_API_KEY),
        "groq_key_set": bool(GROQ_API_KEY),
        "cached_symbols": list(_analysis_cache.keys()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
