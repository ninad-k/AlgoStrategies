"""
Full scan orchestrator — runs as a background thread.

Pipeline phases
───────────────
1. Download symbol universe (~7 000 tickers from NASDAQ FTP)
2. Batch-download 5-day prices → filter price >= $2, volume >= 200K
3. Download SPY 1-year OHLCV (benchmark for RS calculation)
4. Batch-download 1-year OHLCV for filtered universe (batches of 50)
5. Compute technical indicators for every stock
6. Fetch fundamental data for the top-800 by technical score
7. Calculate all four composite scores, store in SQLite
8. Generate AI insights for top-50 multibagger candidates
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
from .tech import analyze_technicals

log = logging.getLogger(__name__)

_scan_lock = threading.Lock()
_current_scan: Optional[dict] = None


# ── Public state queries ────────────────────────────────────────────────────────

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

def _extract_multi(raw: pd.DataFrame, sym: str, col: str) -> pd.Series:
    """Safely extract a column from a multi-ticker yfinance DataFrame."""
    try:
        # yfinance 1.x: MultiIndex (Ticker, OHLCV) with group_by='ticker'
        s = raw[sym][col]
    except (KeyError, TypeError):
        return pd.Series(dtype=float)
    return s.dropna() if isinstance(s, pd.Series) else pd.Series(dtype=float)


def _batch_prices(symbols: list[str], batch_size: int = 100) -> dict[str, tuple[float, float]]:
    """
    Return {symbol: (latest_close, avg_5d_volume)} for each symbol.
    Smaller default batch (100) reduces Yahoo Finance rate-limit pressure.
    """
    result: dict[str, tuple[float, float]] = {}
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
                time.sleep(1.0)
                continue
            for sym in batch:
                try:
                    if len(batch) == 1:
                        # yfinance 1.x single-ticker: columns are MultiIndex (OHLCV, Ticker)
                        c = raw["Close"]
                        v = raw["Volume"] if "Volume" in raw.columns else None
                        close  = (c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c).dropna()
                        volume = (v.iloc[:, 0] if isinstance(v, pd.DataFrame) else v).dropna() if v is not None else pd.Series(dtype=float)
                    else:
                        close  = _extract_multi(raw, sym, "Close")
                        volume = _extract_multi(raw, sym, "Volume")
                    if not close.empty:
                        avg_vol = float(volume.mean()) if not volume.empty else 0.0
                        result[sym] = (float(close.iloc[-1]), avg_vol)
                except Exception:
                    pass
        except Exception as exc:
            log.debug("Batch price error (offset %d): %s", i, exc)
        time.sleep(0.5)
    return result


def _batch_ohlcv(symbols: list[str], batch_size: int = 20) -> dict[str, pd.DataFrame]:
    """
    Return 1-year daily OHLCV DataFrames keyed by symbol.
    Smaller batch size (20) + longer sleep = far fewer Yahoo Finance rate-limit errors.
    """
    result: dict[str, pd.DataFrame] = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        for attempt in range(2):  # one retry on failure
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
                    break
                for sym in batch:
                    try:
                        if len(batch) == 1:
                            # yfinance 1.x single-ticker: flatten MultiIndex → flat OHLCV columns
                            if isinstance(raw.columns, pd.MultiIndex):
                                df = raw.droplevel(1, axis=1)
                            else:
                                df = raw.copy()
                            df = df.dropna(how="all")
                        else:
                            df = raw[sym].dropna(how="all")
                        if not df.empty and "Close" in df.columns:
                            result[sym] = df
                    except (KeyError, TypeError):
                        pass
                break  # success — no retry needed
            except Exception as exc:
                log.debug("Batch OHLCV error (offset %d, attempt %d): %s", i, attempt, exc)
                if attempt == 0:
                    time.sleep(5)  # wait before retry
        time.sleep(2.0)
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
        from .universe import get_us_stock_universe
        log.info("[Phase 1] Fetching symbol universe…")
        _progress(session_id, "Phase 1/5 — Downloading symbol universe", 0, 1)
        symbols = get_us_stock_universe()
        _progress(session_id, f"Phase 1/5 — Universe: {len(symbols):,} symbols", 1, 1)

        # ── Phase 2: Price + volume pre-filter ────────────────────────────────
        log.info("[Phase 2] Price + volume pre-filter (%d symbols)…", len(symbols))
        _progress(session_id, "Phase 2/5 — Fetching prices for pre-filter", 0, len(symbols))
        price_vol = _batch_prices(symbols, batch_size=100)
        # Filter: price >= $2 AND avg daily volume >= 200 000
        filtered = [
            s for s, (p, v) in price_vol.items()
            if p >= 2.0 and v >= 200_000
        ]
        log.info("[Phase 2] %d symbols pass price >= $2 + volume >= 200K filter", len(filtered))
        _progress(session_id, f"Phase 2/5 — {len(filtered):,} symbols after price+volume filter", len(filtered), len(symbols))

        # ── Phase 3: SPY benchmark ─────────────────────────────────────────────
        log.info("[Phase 3] Downloading SPY benchmark…")
        _progress(session_id, "Phase 3/5 — Downloading OHLCV + SPY benchmark", 0, len(filtered))
        spy_close: Optional[pd.Series] = None
        try:
            spy_raw = yf.download("SPY", period="1y", interval="1d", auto_adjust=True, progress=False)
            if not spy_raw.empty:
                close_col = spy_raw.get("Close") or spy_raw.get(("Close", "SPY"))
                if close_col is None and "Close" in spy_raw.columns:
                    close_col = spy_raw["Close"]
                if close_col is not None:
                    # yfinance 1.x single-ticker: "Close" returns a 1-col DataFrame
                    if isinstance(close_col, pd.DataFrame):
                        close_col = close_col.iloc[:, 0]
                    spy_close = close_col.dropna()
                    log.info("SPY benchmark: %d rows", len(spy_close))
        except Exception as exc:
            log.warning("SPY download failed: %s", exc)

        # ── Phase 4: 1-year OHLCV + technical analysis ─────────────────────────
        log.info("[Phase 4] Downloading OHLCV and running technicals (%d stocks)…", len(filtered))
        tech_results: dict[str, dict] = {}
        total = len(filtered)

        for i in range(0, total, 20):
            batch = filtered[i : i + 20]
            ohlcv_batch = _batch_ohlcv(batch, batch_size=20)
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
            time.sleep(0.12)

        # ── Phase 6: Score everything and persist ──────────────────────────────
        log.info("[Phase 6] Scoring %d stocks and storing results…", len(tech_results))
        _progress(session_id, "Phase 5/5 — Finalising scores", 0, len(tech_results))

        stored = 0
        for sym, ta in tech_results.items():
            fd = fund_results.get(sym, {})
            scores = calculate_all_scores(ta, fd)

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

        # ── Phase 7: AI insights for top-50 multibaggers ──────────────────────
        _progress(session_id, "Phase 5/5 — Generating AI insights for top picks…", stored, stored)
        try:
            from .ai_insight import enrich_top_picks
            enrich_top_picks(session_id, limit=50)
            log.info("[Phase 7] AI insights generated")
        except Exception as exc:
            log.warning("[Phase 7] AI insight generation failed: %s", exc)

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
