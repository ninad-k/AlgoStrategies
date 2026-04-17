# Multi-Timeframe Data Fetcher
# Author: Ninad
#
# Pulls full available history (up to 1997) from MT5 for all timeframes.
# Stores downloaded data as parquet files so training doesn't require
# re-downloading every run. MT5 must be connected before calling fetch.

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import talib
import os
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

ALL_TIMEFRAMES = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
    "W1":  mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

# Lower timeframes have limited history in most brokers
# M1: ~2-3 years, M5: ~5 years, M15+: typically full history
TIMEFRAME_START_DATES = {
    "M1":  datetime(2022, 1, 1),
    "M5":  datetime(2019, 1, 1),
    "M15": datetime(2010, 1, 1),
    "M30": datetime(2005, 1, 1),
    "H1":  datetime(2000, 1, 1),
    "H4":  datetime(1999, 1, 1),
    "D1":  datetime(1997, 1, 1),
    "W1":  datetime(1997, 1, 1),
    "MN1": datetime(1997, 1, 1),
}


def fetch_timeframe(
    symbol: str,
    tf_name: str,
    start_date: datetime = None,
    end_date: datetime = None,
    cache_dir: str = "data/raw",
) -> Optional[pd.DataFrame]:
    """Fetch full history for one symbol/timeframe. Returns cached parquet if available."""
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{symbol}_{tf_name}.parquet")

    if start_date is None:
        start_date = TIMEFRAME_START_DATES.get(tf_name, datetime(2000, 1, 1))
    if end_date is None:
        end_date = datetime.now()

    # Use cache if it exists and is from today (avoids re-downloading during same session)
    if os.path.exists(cache_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if mtime.date() == datetime.now().date():
            logger.info(f"Using cached {cache_path}")
            return pd.read_parquet(cache_path)

    mt5_tf = ALL_TIMEFRAMES[tf_name]
    logger.info(f"Downloading {symbol} {tf_name} from {start_date.date()} to {end_date.date()}")

    rates = mt5.copy_rates_range(symbol, mt5_tf, start_date, end_date)
    if rates is None or len(rates) == 0:
        logger.warning(f"No data returned for {symbol} {tf_name}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    df.index.name = 'time'

    logger.info(f"  {symbol} {tf_name}: {len(df)} bars, {df.index[0]} -> {df.index[-1]}")

    df.to_parquet(cache_path)
    return df


def fetch_all_timeframes(
    symbol: str,
    timeframes: list = None,
    cache_dir: str = "data/raw",
) -> Dict[str, pd.DataFrame]:
    """Fetch history for all (or specified) timeframes. Returns dict keyed by tf name."""
    if timeframes is None:
        timeframes = list(ALL_TIMEFRAMES.keys())

    data = {}
    for tf_name in timeframes:
        df = fetch_timeframe(symbol, tf_name, cache_dir=cache_dir)
        if df is not None and len(df) > 0:
            data[tf_name] = df
            logger.info(f"  {tf_name}: {len(df)} bars loaded")

    return data


def add_base_indicators(df: pd.DataFrame, atr_period: int = 10, vol_ma_period: int = 20) -> pd.DataFrame:
    """Add ATR, HL2, volume MA, and normalized volatility columns to a raw OHLCV frame."""
    df = df.copy()
    df['hl2'] = (df['high'] + df['low']) / 2
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=atr_period)
    df['volume_ma'] = df['tick_volume'].rolling(window=vol_ma_period).mean()
    df['volatility'] = df['close'].rolling(window=atr_period).std()
    df['norm_volatility'] = df['volatility'] / df['volatility'].rolling(window=50).mean()

    # Additional indicators useful as ML features
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    df['ema_fast'] = talib.EMA(df['close'], timeperiod=12)
    df['ema_slow'] = talib.EMA(df['close'], timeperiod=26)
    df['ema_trend'] = (df['ema_fast'] - df['ema_slow']) / df['close']
    df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)

    macd, macd_signal, macd_hist = talib.MACD(df['close'])
    df['macd_hist'] = macd_hist

    df['returns_1'] = df['close'].pct_change(1)
    df['returns_5'] = df['close'].pct_change(5)
    df['returns_20'] = df['close'].pct_change(20)

    return df
