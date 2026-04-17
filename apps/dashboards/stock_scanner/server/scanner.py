"""
Full scan orchestrator — runs as a background thread.

Pipeline phases
───────────────
1. Download symbol universe (~7 000 tickers from NASDAQ FTP)
2. Batch-download 5-day prices → filter price >= $2
3. Download SPY 1-year OHLCV (benchmark for RS calculation)
4. Batch-download 1-year OHLCV for filtered universe (batches of 50)
5. Compute technical indicators for every stock
6. Fetch fundamental data for the top-800 by technical score
7. Calculate all four composite scores, store in SQLite
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf

from .database import (
    create_session,
    get_latest_session,
    init_db,
    update_session,
    upsert_stock,
)
from .fundamental import get_fundamental_data
from .scoring import calculate_all_scores, score_swing_medium, score_swing_short
from .technical import analyze_technicals
from .universe import get_us_stock_universe

log = logging.getLogger(__name__)

_scan_lock = threading.Lock()
_current_scan: Optional[dict] = None


# ── Public state queries ───────────────────────────────────────────────────────

def get_scan_status() -> dict:
    with _scan_lock:
        if _current_scan:
            return dict(_current_scan)
    session = get_latest_session()
    if session:
        return session
    return {"status": "idle", "phase": "", "processed_symbols": 0, "total_symbols": 0}


def is_scanning() -> bool:
    with _scan_lock:
        return bool(_current_scan and _current_scan.get("status") == "running")


# ── Progress helper ────────────────────────────────────────────────────────────

def _progress(session_id: int, phase: str, processed: int, total: int, status: str = "running"):
    update_session(
        session_id,
        phase=phase,
        processed_symbols=processed,
        total_symbols=total,
        status=status,
    )
    with _scan_lock:
        if _current_scan:
            _current_scan.update(
                {"phase": phase, "processed_symbols": processed, "total_symbols": total, "status": status}
            )


# ── yfinance batch helpers ─────────────────────────────────────────────────────

def _batch_prices(symbols: list[str], batch_size: int = 200) -> dict[str, float]:
    """Return latest close price for each symbol (only needs 5 days of data)."""
    prices: dict[str, float] = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        try:
            raw = yf.download(
                batch,
                period="5d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
            if raw.empty:
                continue
            if len(batch) == 1:
                sym = batch[0]
                if "Close" in raw.columns:
                    val = raw["Close"].dropna()
                    if not val.empty:
                        prices[sym] = float(val.iloc[-1])
            else:
                for sym in batch:
                    try:
                        close = raw[sym]["Close"].dropna()
                        if not close.empty:
                            prices[sym] = float(close.iloc[-1])
                    except (KeyError, TypeError):
                        pass
        except Exception as exc:
            log.debug("Batch price error (offset %d): %s", i, exc)
        time.sleep(0.4)
    return prices


def _batch_ohlcv(symbols: list[str], batch_size: int = 50) -> dict[str, pd.DataFrame]:
    """Return 1-year daily OHLCV DataFrames keyed by symbol."""
    result: dict[str, pd.DataFrame] = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        try:
            raw = yf.download(
                batch,
                period="1y",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
            if raw.empty:
                continue
            if len(batch) == 1:
                sym = batch[0]
                if "Close" in raw.columns and not raw["Close"].dropna().empty:
                    result[sym] = raw.dropna(how="all")
            else:
                for sym in batch:
                    try:
                        df = raw[sym].dropna(how="all")
                        if not df.empty and "Close" in df.columns:
                            result[sym] = df
                    except (KeyError, TypeError):
                        pass
        except Exception as exc:
            log.debug("Batch OHLCV error (offset %d): %s", i, exc)
        time.sleep(0.8)
    return result


# ── Main scan pipeline ─────────────────────────────────────────────────────────

def run_scan():
    """Execute full scan. Called in a background daemon thread."""
    init_db()

    with _scan_lock:
        global _current_scan
        if _current_scan and _current_scan.get("status") == "running":
            log.warning("Scan already running — skipping duplicate start")
            return
        _current_scan = {"status": "running", "phase": "Starting…", "processed_symbols": 0, "total_symbols": 0}

    session_id = create_session()
    with _scan_lock:
        _current_scan["id"] = session_id

    try:
        # ── Phase 1: Symbol universe ───────────────────────────────────────────
        log.info("[Phase 1] Fetching symbol universe…")
        _progress(session_id, "Phase 1/5 — Downloading symbol universe", 0, 1)
        symbols = get_us_stock_universe()
        _progress(session_id, f"Phase 1/5 — Universe: {len(symbols):,} symbols", 1, 1)

        # ── Phase 2: Price pre-filter ──────────────────────────────────────────
        log.info("[Phase 2] Price pre-filter (%d symbols)…", len(symbols))
        _progress(session_id, "Phase 2/5 — Fetching prices for pre-filter", 0, len(symbols))
        prices = _batch_prices(symbols, batch_size=200)
        filtered = [s for s, p in prices.items() if p and p >= 2.0]
        log.info("[Phase 2] %d symbols pass price >= $2 filter", len(filtered))
        _progress(session_id, f"Phase 2/5 — {len(filtered):,} symbols after price filter", len(filtered), len(symbols))

        # ── Phase 3: SPY benchmark ─────────────────────────────────────────────
        log.info("[Phase 3] Downloading SPY benchmark…")
        _progress(session_id, "Phase 3/5 — Downloading OHLCV + SPY benchmark", 0, len(filtered))
        spy_close: Optional[pd.Series] = None
        try:
            spy_raw = yf.download("SPY", period="1y", interval="1d", auto_adjust=True, progress=False)
            if not spy_raw.empty and "Close" in spy_raw.columns:
                spy_close = spy_raw["Close"].dropna()
        except Exception as exc:
            log.warning("SPY download failed: %s", exc)

        # ── Phase 4: 1-year OHLCV + technical analysis ─────────────────────────
        log.info("[Phase 4] Downloading OHLCV and running technicals (%d stocks)…", len(filtered))
        tech_results: dict[str, dict] = {}
        total = len(filtered)

        for i in range(0, total, 50):
            batch = filtered[i : i + 50]
            ohlcv_batch = _batch_ohlcv(batch, batch_size=50)
            for sym, df in ohlcv_batch.items():
                try:
                    ta = analyze_technicals(df, spy_close)
                    if ta:
                        tech_results[sym] = ta
                except Exception as exc:
                    log.debug("Technical error %s: %s", sym, exc)

            processed = min(i + 50, total)
            _progress(
                session_id,
                f"Phase 3/5 — Technical analysis ({processed:,}/{total:,})",
                processed,
                total,
            )

        log.info("[Phase 4] Technical analysis done: %d stocks", len(tech_results))

        # ── Phase 5: Fundamental data for top-800 by technical score ───────────
        log.info("[Phase 5] Fetching fundamentals for top candidates…")
        # Quick pre-rank by best of swing scores
        ranked = sorted(
            tech_results.items(),
            key=lambda kv: max(
                score_swing_short(kv[1], {})[0],
                score_swing_medium(kv[1], {})[0],
            ),
            reverse=True,
        )
        top_syms = [s for s, _ in ranked[:800]]

        fund_results: dict[str, dict] = {}
        for idx, sym in enumerate(top_syms):
            try:
                fd = get_fundamental_data(sym)
                if fd:
                    fund_results[sym] = fd
            except Exception as exc:
                log.debug("Fundamental error %s: %s", sym, exc)

            if (idx + 1) % 50 == 0:
                _progress(
                    session_id,
                    f"Phase 4/5 — Fundamentals ({idx+1:,}/{len(top_syms):,})",
                    idx + 1,
                    len(top_syms),
                )
            time.sleep(0.12)  # gentle rate-limiting

        # ── Phase 6: Score everything and persist ──────────────────────────────
        log.info("[Phase 6] Scoring %d stocks and storing results…", len(tech_results))
        _progress(session_id, "Phase 5/5 — Finalising scores", 0, len(tech_results))

        stored = 0
        for sym, ta in tech_results.items():
            fd = fund_results.get(sym, {})
            scores = calculate_all_scores(ta, fd)

            # Skip stocks with no meaningful signal
            if max(
                scores["swing_short_score"],
                scores["swing_medium_score"],
                scores["investment_score"],
                scores["multibagger_score"],
            ) < 20:
                continue

            record = {
                "symbol":           sym,
                "company_name":     fd.get("company_name", sym),
                "sector":           fd.get("sector"),
                "industry":         fd.get("industry"),
                "market_cap":       fd.get("market_cap"),
                "price":            ta.get("price"),
                "price_change_pct": ta.get("price_change_pct"),
                "avg_volume":       ta.get("avg_volume_20d"),
                "rsi":              ta.get("rsi"),
                "stage":            ta.get("stage"),
                "rs_vs_spy":        ta.get("rs_vs_spy"),
                "volume_ratio":     ta.get("volume_ratio"),
                "revenue_growth":   fd.get("revenue_growth_yoy"),
                "gross_margin":     fd.get("gross_margin"),
                "debt_equity":      fd.get("debt_equity"),
                "eps_trend":        fd.get("eps_trend"),
                **scores,
            }
            upsert_stock(session_id, record)
            stored += 1

        log.info("[Phase 6] Stored %d stocks", stored)
        _progress(session_id, "Scan complete", len(tech_results), len(tech_results), "completed")
        update_session(session_id, completed_at=datetime.utcnow().isoformat(), status="completed")

    except Exception as exc:
        log.error("Scan failed: %s", exc, exc_info=True)
        update_session(session_id, status="failed", error=str(exc))
        _progress(session_id, f"Scan failed: {exc}", 0, 0, "failed")
    finally:
        with _scan_lock:
            _current_scan = None


def start_scan_background() -> bool:
    """Spawn the scan in a daemon thread. Returns False if already running."""
    if is_scanning():
        return False
    t = threading.Thread(target=run_scan, daemon=True, name="stock-scanner")
    t.start()
    return True
