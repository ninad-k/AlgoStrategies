"""Historical OHLCV data download via yfinance or a local MT5 terminal."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, time, timedelta
from pathlib import Path

import numpy as np
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

# Intraday: chunk by calendar days so each copy_rates_range stays under terminal maxbars (~100k).
MT5_CHUNK_DAYS: dict[str, int | None] = {
    "1m": 45,
    "M1": 45,
    "5m": 120,
    "M5": 120,
    "15m": 180,
    "M15": 180,
    "30m": 240,
    "M30": 240,
    "1h": 500,
    "H1": 500,
    "4h": 730,
    "H4": 730,
    "1d": None,
    "D1": None,
    "1wk": None,
    "W1": None,
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


def _copy_rates_range_mt5(
    mt5: object,
    symbol: str,
    mt5_tf: int,
    start_dt: datetime,
    end_dt: datetime,
    timeframe: str,
) -> tuple[np.ndarray | None, tuple | None]:
    """Single or chunked copy_rates_range. Returns (rates_array_or_none, last_error_if_failed).

    MT5 terminals cap history (~maxbars 100000); long M1/M5 ranges must be requested in chunks.
    Datetimes must be naive (local/server) — see _parse_mt5_date_range.
    """
    chunk_days = MT5_CHUNK_DAYS.get(timeframe)
    span = end_dt - start_dt
    use_chunks = chunk_days is not None and span > timedelta(days=chunk_days)

    if not use_chunks:
        rates = mt5.copy_rates_range(symbol, mt5_tf, start_dt, end_dt)
        if rates is None:
            return None, mt5.last_error()
        return rates, None

    log.info(
        "MT5 chunking copy_rates_range: timeframe=%r chunk_days=%d span_days=%d",
        timeframe,
        chunk_days,
        span.days,
    )
    chunks: list[np.ndarray] = []
    cur = start_dt
    step = timedelta(days=chunk_days)
    while cur < end_dt:
        chunk_end = min(cur + step, end_dt)
        rates = mt5.copy_rates_range(symbol, mt5_tf, cur, chunk_end)
        if rates is None:
            return None, mt5.last_error()
        if len(rates) > 0:
            chunks.append(rates)
        if chunk_end >= end_dt:
            break
        cur = chunk_end + timedelta(seconds=1)

    if not chunks:
        return None, mt5.last_error()

    combined = np.concatenate(chunks)
    order = np.argsort(combined["time"])
    combined = combined[order]
    times = combined["time"]
    _, keep = np.unique(times, return_index=True)
    combined = combined[np.sort(keep)]
    return combined, None


def download_mt5_ohlcv(
    symbol: str,
    timeframe: str = "1d",
    start_date: str = "2020-01-01",
    end_date: str = "",
) -> pd.DataFrame:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        log.exception("MetaTrader5 import failed")
        raise RuntimeError(
            "MetaTrader5 Python package is not installed. Install it with `pip install MetaTrader5`."
        ) from exc

    symbol = (symbol or "").strip()
    if not symbol:
        log.error("MT5 download rejected because symbol is empty")
        raise RuntimeError("MT5 symbol is empty.")

    start_date = (start_date or "").strip() or "2020-01-01"
    end_date = (end_date or "").strip()

    log.info(
        "MT5 OHLCV normalized inputs: symbol=%r timeframe=%r start_date=%r end_date=%r thread=%s",
        symbol,
        timeframe,
        start_date,
        end_date if end_date else "<empty -> current UTC time>",
        threading.current_thread().name,
    )

    mt5_tf_name = MT5_TIMEFRAME_MAP.get(timeframe)
    if not mt5_tf_name:
        log.error("Unsupported MT5 timeframe requested: %s", timeframe)
        raise RuntimeError(f"Unsupported MT5 timeframe: {timeframe}")

    mt5_tf = getattr(mt5, mt5_tf_name, None)
    if mt5_tf is None:
        log.error("MT5 package is missing timeframe constant %s", mt5_tf_name)
        raise RuntimeError(f"MetaTrader5 package does not expose timeframe constant {mt5_tf_name}")

    start_dt, end_dt = _parse_mt5_date_range(start_date, end_date)
    log.debug(
        "Resolved MT5 date range symbol=%s timeframe=%s start=%s end=%s constant=%s",
        symbol,
        timeframe,
        start_dt.isoformat(),
        end_dt.isoformat(),
        mt5_tf_name,
    )

    with _MT5_LOCK:
        log.debug("Acquired MT5 lock for symbol=%s timeframe=%s", symbol, timeframe)
        if not mt5.initialize():
            log.error(
                "MT5 initialize failed for symbol=%s timeframe=%s last_error=%r session=%s",
                symbol,
                timeframe,
                getattr(mt5, "last_error", lambda: None)(),
                _describe_mt5_session(mt5),
            )
            raise RuntimeError(_format_mt5_error(mt5, "Failed to initialize MT5 connection"))

        symbol_select_ok = False
        try:
            log.info("MT5 initialized. %s", _describe_mt5_session(mt5))
            symbol_select_ok = bool(mt5.symbol_select(symbol, True))
            if not symbol_select_ok:
                log.error(
                    "MT5 symbol_select failed symbol=%r last_error=%r symbol_info=%s",
                    symbol,
                    getattr(mt5, "last_error", lambda: None)(),
                    _snapshot_symbol_info(mt5, symbol),
                )
                raise RuntimeError(_format_mt5_error(mt5, f"MT5 symbol '{symbol}' is not available"))

            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is not None:
                log.debug(
                    "MT5 symbol info symbol=%s visible=%s select=%s digits=%s trade_mode=%s path=%s",
                    symbol,
                    getattr(symbol_info, "visible", None),
                    getattr(symbol_info, "select", None),
                    getattr(symbol_info, "digits", None),
                    getattr(symbol_info, "trade_mode", None),
                    getattr(symbol_info, "path", None),
                )
            else:
                log.warning("MT5 symbol_info returned None after symbol_select for symbol=%s", symbol)

            _log_mt5_copy_rates_request(
                symbol=symbol,
                timeframe=timeframe,
                start_date_in=start_date,
                end_date_in=end_date,
                start_dt=start_dt,
                end_dt=end_dt,
                mt5_tf_name=mt5_tf_name,
                mt5_tf=int(mt5_tf),
            )
            rates, copy_err = _copy_rates_range_mt5(
                mt5, symbol, mt5_tf, start_dt, end_dt, timeframe
            )
            if rates is None:
                _log_mt5_copy_rates_failure(
                    mt5,
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date_in=start_date,
                    end_date_in=end_date,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    mt5_tf_name=mt5_tf_name,
                    mt5_tf=int(mt5_tf),
                    symbol_select_ok=symbol_select_ok,
                    last_error_captured=copy_err,
                )
                msg = (
                    "MT5 returned no data (check symbol spelling including broker suffix, "
                    "timeframe, and that start date is before end date)"
                )
                if copy_err:
                    raise RuntimeError(f"{msg}. MT5 error: {copy_err}")
                raise RuntimeError(msg)
            if len(rates) == 0:
                log.warning("MT5 copy_rates_range returned 0 rows for symbol=%s timeframe=%s", symbol, timeframe)
                return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

            df = pd.DataFrame(rates)
            log.debug("MT5 copy_rates_range returned rows=%d columns=%s", len(df), list(df.columns))
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
            log.info(
                "MT5 download succeeded symbol=%s timeframe=%s rows=%d first=%s last=%s",
                symbol,
                timeframe,
                len(df),
                df.index.min(),
                df.index.max(),
            )
            return df
        finally:
            log.debug("Shutting down MT5 session for symbol=%s timeframe=%s", symbol, timeframe)
            mt5.shutdown()
            log.debug("MT5 shutdown complete for symbol=%s timeframe=%s", symbol, timeframe)


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
    """Naive local datetimes for copy_rates_range — aware UTC values trigger (-2) Invalid params."""
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


def _describe_mt5_session(mt5: object) -> str:
    terminal_info = getattr(mt5, "terminal_info", lambda: None)()
    account_info = getattr(mt5, "account_info", lambda: None)()
    version_info = getattr(mt5, "version", lambda: None)()
    return "version=%s terminal=%s account=%s" % (version_info, terminal_info, account_info)


def _describe_datetime_for_mt5(dt: datetime) -> str:
    """Human-readable datetime details for MT5 request logging."""
    try:
        ts = dt.timestamp()
    except Exception:
        ts = None
    tz = dt.tzinfo
    return (
        f"iso={dt.isoformat()!r} repr={dt!r} tzinfo={tz!r} "
        f"unix_ts={ts!r} date={dt.date()!r} time={dt.time()!r}"
    )


def _snapshot_terminal_info(mt5: object) -> str:
    try:
        ti = getattr(mt5, "terminal_info", lambda: None)()
        if ti is None:
            return "None"
        if hasattr(ti, "_asdict"):
            return str(ti._asdict())
        return repr(ti)
    except Exception as exc:
        return f"<error: {exc}>"


def _snapshot_symbol_info(mt5: object, symbol: str) -> str:
    try:
        fn = getattr(mt5, "symbol_info", None)
        si = fn(symbol) if callable(fn) else None
        if si is None:
            return "symbol_info=None"
        if hasattr(si, "_asdict"):
            return str(si._asdict())
        attrs = (
            "name", "path", "description", "currency_base", "currency_profit",
            "visible", "select", "session_deals", "digits", "spread", "trade_mode",
            "volume_min", "volume_max", "volume_step",
        )
        parts = []
        for attr in attrs:
            if hasattr(si, attr):
                parts.append(f"{attr}={getattr(si, attr)!r}")
        return ", ".join(parts) if parts else repr(si)
    except Exception as exc:
        return f"<error: {exc}>"


def _log_mt5_copy_rates_request(
    *,
    symbol: str,
    timeframe: str,
    start_date_in: str,
    end_date_in: str,
    start_dt: datetime,
    end_dt: datetime,
    mt5_tf_name: str,
    mt5_tf: int,
) -> None:
    log.info(
        "MT5 copy_rates_range request: symbol=%r timeframe_key=%r start_date_in=%r end_date_in=%r "
        "mt5_constant=%s mt5_tf_int=%s start_dt[%s] end_dt[%s]",
        symbol,
        timeframe,
        start_date_in,
        end_date_in or "<empty -> current UTC time>",
        mt5_tf_name,
        mt5_tf,
        _describe_datetime_for_mt5(start_dt),
        _describe_datetime_for_mt5(end_dt),
    )


def _log_mt5_copy_rates_failure(
    mt5: object,
    *,
    symbol: str,
    timeframe: str,
    start_date_in: str,
    end_date_in: str,
    start_dt: datetime,
    end_dt: datetime,
    mt5_tf_name: str,
    mt5_tf: int,
    symbol_select_ok: bool,
    last_error_captured: tuple | None = None,
) -> None:
    # Capture before other MT5 calls — terminal_info/symbol_info reset last_error to Success.
    last_err = last_error_captured if last_error_captured is not None else getattr(mt5, "last_error", lambda: None)()
    log.error(
        "MT5 copy_rates_range returned None - full context:\n"
        "  symbol=%r timeframe_key=%r\n"
        "  start_date_in=%r end_date_in=%r\n"
        "  mt5_constant=%s mt5_tf_int=%s\n"
        "  symbol_select_ok=%s\n"
        "  start_dt: %s\n"
        "  end_dt: %s\n"
        "  last_error_at_failure=%r\n"
        "  terminal_info=%s\n"
        "  version=%r\n"
        "  symbol_info=%s\n"
        "  session: %s",
        symbol,
        timeframe,
        start_date_in,
        end_date_in or "<empty>",
        mt5_tf_name,
        mt5_tf,
        symbol_select_ok,
        _describe_datetime_for_mt5(start_dt),
        _describe_datetime_for_mt5(end_dt),
        last_err,
        _snapshot_terminal_info(mt5),
        getattr(mt5, "version", lambda: None)(),
        _snapshot_symbol_info(mt5, symbol),
        _describe_mt5_session(mt5),
    )


def _format_mt5_error(mt5: object, message: str) -> str:
    error = getattr(mt5, "last_error", lambda: None)()
    log.debug("MT5 last_error=%s message=%s", error, message)
    if error:
        return f"{message}. MT5 error: {error}"
    return message
