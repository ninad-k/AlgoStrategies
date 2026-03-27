"""Historical OHLCV data download and caching via yfinance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"

TIMEFRAME_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "1h", "1d": "1d", "1wk": "1wk",
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H4": "1h", "D1": "1d", "W1": "1wk",
}

INTRADAY_LIMITS = {
    "1m": 7, "5m": 60, "15m": 60, "30m": 60, "1h": 730,
}

SYMBOL_ALIASES = {
    "XAUUSD": "GC=F",
    "XAUUSD_": "GC=F",
    "XAGUSD": "SI=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "US500": "^GSPC",
    "US30": "^DJI",
    "NAS100": "^IXIC",
    "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}


def resolve_symbol(symbol: str) -> str:
    upper = symbol.upper().strip()
    return SYMBOL_ALIASES.get(upper, upper)


def get_data_warning(timeframe: str, start_date: str, end_date: str) -> str | None:
    yf_tf = TIMEFRAME_MAP.get(timeframe, timeframe)
    limit_days = INTRADAY_LIMITS.get(yf_tf)
    if limit_days is None:
        return None
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
    requested = (end - start).days
    if requested > limit_days:
        return (
            f"yfinance only provides ~{limit_days} days of {yf_tf} data. "
            f"You requested {requested} days. Data will be truncated. "
            f"Use daily (1d) or weekly (1wk) for 5-10 year backtests."
        )
    return None


def download_ohlcv(
    symbol: str,
    timeframe: str = "1d",
    start_date: str = "2020-01-01",
    end_date: str = "",
) -> pd.DataFrame:
    yf_symbol = resolve_symbol(symbol)
    yf_tf = TIMEFRAME_MAP.get(timeframe, timeframe)

    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    cache_file = CACHE_DIR / f"{yf_symbol.replace('=', '_')}_{yf_tf}_{start_date}_{end_date}.parquet"

    if cache_file.exists():
        log.info("Loading cached data: %s", cache_file.name)
        df = pd.read_parquet(cache_file)
        if len(df) > 0:
            return df

    log.info("Downloading %s %s from %s to %s", yf_symbol, yf_tf, start_date, end_date)

    ticker = yf.Ticker(yf_symbol)

    limit_days = INTRADAY_LIMITS.get(yf_tf)
    if limit_days:
        earliest = datetime.now() - timedelta(days=limit_days)
        req_start = max(datetime.strptime(start_date, "%Y-%m-%d"), earliest)
        df = ticker.history(
            interval=yf_tf,
            start=req_start.strftime("%Y-%m-%d"),
            end=end_date,
        )
    else:
        df = ticker.history(
            interval=yf_tf,
            start=start_date,
            end=end_date,
        )

    if df.empty:
        log.warning("No data returned for %s", yf_symbol)
        return df

    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            df[col] = 0.0

    df = df[["open", "high", "low", "close", "volume"]].copy()
    df.index.name = "datetime"

    if yf_tf == "1h" and timeframe in ("4h", "H4"):
        df = _resample_to_4h(df)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_file)
    log.info("Cached %d bars to %s", len(df), cache_file.name)

    return df


def _resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    return df.resample("4h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()


def search_symbols(query: str) -> list[dict]:
    if not query or len(query) < 1:
        return []
    try:
        results = []
        for alias, yf_sym in SYMBOL_ALIASES.items():
            if query.upper() in alias:
                results.append({"symbol": alias, "yf_symbol": yf_sym, "name": alias})

        ticker = yf.Ticker(query.upper())
        info = ticker.info
        if info and info.get("symbol"):
            results.append({
                "symbol": info.get("symbol", query.upper()),
                "yf_symbol": info.get("symbol", query.upper()),
                "name": info.get("shortName", info.get("longName", query.upper())),
            })
        return results[:10]
    except Exception:
        return [{"symbol": query.upper(), "yf_symbol": query.upper(), "name": query.upper()}]
