"""
Regime Features — Extract features for regime classification.
Uses ATR ratio, ADX, BB width, volume, return volatility.
"""

import numpy as np
import pandas as pd


def extract_regime_features(df: pd.DataFrame) -> dict:
    """
    Extract features for regime classification from OHLCV DataFrame.

    Returns dict with:
        atr_ratio: short-term ATR / long-term ATR (volatility expansion/contraction)
        adx: trend strength (0-100)
        bb_width_pct: Bollinger Band width as % of price
        vol_ratio: current volume vs 20-bar average
        return_std: standard deviation of 20-bar returns
        directional_bias: net price change over 20 bars as % of ATR
        candle_consistency: % of last 10 candles in same direction
    """
    if df is None or len(df) < 50:
        return {}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    # ATR (manual for independence from pandas_ta)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    atr_7 = tr.rolling(7).mean().iloc[-1]
    atr_30 = tr.rolling(30).mean().iloc[-1]
    atr_ratio = round(float(atr_7 / atr_30), 4) if atr_30 > 0 else 1.0

    # ADX (simplified DI calculation)
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    atr_14 = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_14)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_14)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1))
    adx = float(dx.rolling(14).mean().iloc[-1])

    # Bollinger Band width
    sma20 = close.rolling(20).mean().iloc[-1]
    std20 = close.rolling(20).std().iloc[-1]
    bb_width = round(float(4 * std20 / sma20 * 100), 4) if sma20 > 0 else 0

    # Volume ratio
    vol_sma = volume.rolling(20).mean().iloc[-1]
    vol_ratio = round(float(volume.iloc[-1] / vol_sma), 2) if vol_sma > 0 else 1.0

    # Return volatility
    returns = close.pct_change().dropna()
    return_std = round(float(returns.tail(20).std()), 6) if len(returns) >= 20 else 0

    # Directional bias: net move over 20 bars as multiple of ATR
    net_move = float(close.iloc[-1] - close.iloc[-20]) if len(close) >= 20 else 0
    atr_val = float(atr_14.iloc[-1]) if not pd.isna(atr_14.iloc[-1]) else 1
    directional_bias = round(net_move / atr_val, 2) if atr_val > 0 else 0

    # Candle consistency: % of last 10 candles going in same direction
    last_10 = df.tail(10)
    up_count = sum(float(r["close"]) >= float(r["open"]) for _, r in last_10.iterrows())
    consistency = max(up_count, 10 - up_count) / 10

    return {
        "atr_ratio": atr_ratio,
        "adx": round(adx, 2),
        "bb_width_pct": bb_width,
        "vol_ratio": vol_ratio,
        "return_std": return_std,
        "directional_bias": directional_bias,
        "candle_consistency": round(consistency, 2),
    }
