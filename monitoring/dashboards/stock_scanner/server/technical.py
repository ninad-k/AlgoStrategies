"""
Technical analysis engine.
All indicators computed with pure pandas/numpy — no TA-Lib dependency.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


# ── Indicator primitives ───────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(close: pd.Series, period: int = 14) -> float:
    if len(close) < period + 1:
        return 50.0
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 1) if pd.notna(val) else 50.0


def calc_macd_direction(close: pd.Series) -> str:
    if len(close) < 35:
        return "NEUTRAL"
    macd = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd, 9)
    m, s = float(macd.iloc[-1]), float(signal.iloc[-1])
    if m > s and m > 0:
        return "BULLISH"
    if m < s and m < 0:
        return "BEARISH"
    return "NEUTRAL"


# ── Stage analysis (Weinstein) ─────────────────────────────────────────────────

def detect_stage(close: pd.Series) -> int:
    """
    Stage 2 = advancing (price > EMA50 > EMA150 > EMA200, 200 EMA rising).
    Returns 1-4 or 0 if insufficient data.
    """
    if len(close) < 200:
        return 0

    e20  = float(_ema(close, 20).iloc[-1])
    e50  = float(_ema(close, 50).iloc[-1])
    e150 = float(_ema(close, 150).iloc[-1])
    e200_series = _ema(close, 200)
    e200 = float(e200_series.iloc[-1])
    price = float(close.iloc[-1])

    # EMA200 slope over last 21 bars
    slope_ref = float(e200_series.iloc[-21]) if len(e200_series) > 21 else e200
    slope = (e200 - slope_ref) / slope_ref if slope_ref else 0

    if price > e50 > e150 > e200 and slope > 0:
        return 2
    if price < e50 < e150 < e200 and slope < -0.01:
        return 4
    if slope >= -0.005:
        return 1
    return 3


# ── Relative strength vs SPY ───────────────────────────────────────────────────

def calc_rs_vs_spy(stock_close: pd.Series, spy_close: pd.Series, days: int = 63) -> float:
    """RS > 1.0 = stock outperforming SPY over last `days` trading days."""
    if len(stock_close) < days or len(spy_close) < days:
        return 1.0
    stock_ret = float(stock_close.iloc[-1]) / float(stock_close.iloc[-days]) - 1
    spy_ret   = float(spy_close.iloc[-1])   / float(spy_close.iloc[-days])   - 1
    if spy_ret == 0:
        return 1.0
    return round(1 + (stock_ret - spy_ret), 3)


# ── Volume ratio ───────────────────────────────────────────────────────────────

def calc_volume_ratio(volume: pd.Series, days: int = 20) -> float:
    if len(volume) < days + 1:
        return 1.0
    avg = float(volume.iloc[-days - 1 : -1].mean())
    return round(float(volume.iloc[-1]) / avg, 2) if avg else 1.0


# ── Volatility Contraction Pattern ────────────────────────────────────────────

def detect_vcp(close: pd.Series, window: int = 60) -> bool:
    """
    Simple VCP: last N bars show tightening pivot ranges
    (each swing range smaller than the previous).
    """
    if len(close) < window:
        return False
    prices = close.iloc[-window:]
    w = 5
    highs, lows = [], []
    for i in range(w, len(prices) - w):
        sl = prices.iloc[i - w : i + w + 1]
        if prices.iloc[i] == sl.max():
            highs.append(float(prices.iloc[i]))
        if prices.iloc[i] == sl.min():
            lows.append(float(prices.iloc[i]))

    if len(highs) < 3 or len(lows) < 2:
        return False

    ranges = [
        abs(highs[i] - lows[i]) / lows[i]
        for i in range(min(len(highs), len(lows)))
        if lows[i] > 0
    ]
    if len(ranges) < 3:
        return False

    contracting = sum(ranges[i] < ranges[i - 1] for i in range(1, len(ranges)))
    return contracting >= len(ranges) - 1


# ── Support proximity ──────────────────────────────────────────────────────────

def near_support(low: pd.Series, close: pd.Series, threshold: float = 0.03) -> bool:
    if len(close) < 20:
        return False
    price = float(close.iloc[-1])
    support = float(low.iloc[-20:].min())
    return (abs(price - support) / support) < threshold if support > 0 else False


# ── Candle pattern ─────────────────────────────────────────────────────────────

def is_bullish_candle(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> bool:
    if len(close) < 1:
        return False
    c, o, h, l = (
        float(close.iloc[-1]), float(open_.iloc[-1]),
        float(high.iloc[-1]),  float(low.iloc[-1]),
    )
    rng = h - l
    if rng == 0:
        return False
    return c > o and c >= l + rng * 0.67  # close in upper third


# ── 52-week position ───────────────────────────────────────────────────────────

def week52_position(close: pd.Series) -> dict:
    period = close.iloc[-252:] if len(close) >= 252 else close
    hi, lo, price = float(period.max()), float(period.min()), float(close.iloc[-1])
    return {
        "w52_high":      round(hi, 2),
        "w52_low":       round(lo, 2),
        "pct_from_high": round((price - hi) / hi * 100, 1) if hi else 0,
        "pct_from_low":  round((price - lo) / lo * 100, 1) if lo else 0,
    }


# ── Master function ────────────────────────────────────────────────────────────

def analyze_technicals(df: pd.DataFrame, spy_close: pd.Series | None = None) -> dict:
    """
    Compute all technical indicators for a single stock.
    `df` must have Open / High / Low / Close / Volume columns with a date index.
    """
    if df is None or len(df) < 20:
        return {}

    close  = df["Close"].dropna()
    high   = df["High"].dropna()
    low    = df["Low"].dropna()
    open_  = df["Open"].dropna()
    volume = df["Volume"].dropna()

    if len(close) < 20:
        return {}

    result: dict = {}
    result["price"]            = round(float(close.iloc[-1]), 2)
    result["price_change_pct"] = round(
        (float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100, 2
    ) if len(close) > 1 else 0.0

    result["rsi"]           = calc_rsi(close)
    result["macd_direction"]= calc_macd_direction(close)
    result["stage"]         = detect_stage(close)
    result["volume_ratio"]  = calc_volume_ratio(volume)
    result["is_vcp"]        = detect_vcp(close)
    result["near_support"]  = near_support(low, close)
    result["bullish_candle"]= is_bullish_candle(open_, high, low, close)
    result["avg_volume_20d"]= round(float(volume.iloc[-20:].mean()), 0) if len(volume) >= 20 else 0.0
    result["rs_vs_spy"]     = calc_rs_vs_spy(close, spy_close) if spy_close is not None else 1.0
    result.update(week52_position(close))

    if len(close) >= 20:  result["ema20"]  = round(float(_ema(close, 20).iloc[-1]),  2)
    if len(close) >= 50:  result["ema50"]  = round(float(_ema(close, 50).iloc[-1]),  2)
    if len(close) >= 150: result["ema150"] = round(float(_ema(close, 150).iloc[-1]), 2)
    if len(close) >= 200: result["ema200"] = round(float(_ema(close, 200).iloc[-1]), 2)

    return result
