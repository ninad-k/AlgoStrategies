"""Historical OHLCV data download via yfinance or a local MT5 terminal."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
MT5_TEMP_DIR = Path(__file__).parent.parent / "data" / "mt5_temp"

# MetaTrader5 Python API is not safe for concurrent initialize/copy/shutdown from multiple threads.
_MT5_LOCK = threading.Lock()

TIMEFRAME_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "1h", "1d": "1d", "1wk": "1wk",
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H4": "1h", "D1": "1d", "W1": "1wk",
}

MT5_TIMEFRAME_MAP = {
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",
    "1wk": "TIMEFRAME_W1",
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
    "W1": "TIMEFRAME_W1",
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


def download_mt5_ohlcv(
    symbol: str,
    timeframe: str = "1d",
    start_date: str = "2020-01-01",
    end_date: str = "",
) -> pd.DataFrame:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise RuntimeError(
            "MetaTrader5 Python package is not installed. Install it with `pip install MetaTrader5`."
        ) from exc

    symbol = (symbol or "").strip()
    if not symbol:
        raise RuntimeError("MT5 symbol is empty.")

    start_date = (start_date or "").strip() or "2020-01-01"
    end_date = (end_date or "").strip()

    mt5_tf_name = MT5_TIMEFRAME_MAP.get(timeframe)
    if not mt5_tf_name:
        raise RuntimeError(f"Unsupported MT5 timeframe: {timeframe}")

    mt5_tf = getattr(mt5, mt5_tf_name, None)
    if mt5_tf is None:
        raise RuntimeError(f"MetaTrader5 package does not expose timeframe constant {mt5_tf_name}")

    start_dt, end_dt = _parse_mt5_date_range(start_date, end_date)

    with _MT5_LOCK:
        if not mt5.initialize():
            raise RuntimeError(_format_mt5_error(mt5, "Failed to initialize MT5 connection"))

        try:
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(_format_mt5_error(mt5, f"MT5 symbol '{symbol}' is not available"))

            rates = mt5.copy_rates_range(symbol, mt5_tf, start_dt, end_dt)
            if rates is None:
                raise RuntimeError(
                    _format_mt5_error(
                        mt5,
                        "MT5 returned no data (check symbol spelling including broker suffix, "
                        "timeframe, and that start date is before end date)",
                    )
                )
            if len(rates) == 0:
                return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

            df = pd.DataFrame(rates)
            df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df.set_index("datetime", inplace=True)
            df.rename(
                columns={
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "tick_volume": "volume",
                },
                inplace=True,
            )
            df = df[["open", "high", "low", "close", "volume"]].copy()
            df.index.name = "datetime"
            return df
        finally:
            mt5.shutdown()


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    export = df.copy()
    export.index = export.index.tz_convert("UTC") if getattr(export.index, "tz", None) else export.index
    export.insert(0, "Date", export.index.strftime("%Y-%m-%d"))
    export.insert(1, "Time", export.index.strftime("%H:%M:%S"))
    export.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
        inplace=True,
    )
    return export.to_csv(index=False).encode("utf-8")


def save_mt5_temp_data(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    df: pd.DataFrame,
) -> Path:
    MT5_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    safe_symbol = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in symbol)
    safe_end = end_date or "latest"
    file_path = MT5_TEMP_DIR / f"{safe_symbol}_{timeframe}_{start_date}_{safe_end}_latest.csv"
    file_path.write_bytes(dataframe_to_csv_bytes(df))
    return file_path


def _parse_mt5_date_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    """Naive datetimes for copy_rates_range — timezone-aware values often trigger MT5 (-2) Invalid params."""
    start = datetime.combine(datetime.strptime(start_date.strip(), "%Y-%m-%d").date(), time.min)
    if end_date and end_date.strip():
        end = datetime.combine(datetime.strptime(end_date.strip(), "%Y-%m-%d").date(), time.max)
    else:
        end = datetime.now()
    if start >= end:
        raise ValueError(
            "MT5 date range is invalid: start_date must be strictly before end_date "
            "(check that the start is not after the end, including when end is 'today')."
        )
    return start, end


def _format_mt5_error(mt5: object, message: str) -> str:
    error = getattr(mt5, "last_error", lambda: None)()
    if error:
        return f"{message}. MT5 error: {error}"
    return message
