"""
Technical analysis: support/resistance levels, pivot points,
swing highs/lows, RSI, MACD, ATR, and trend signals.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from .models import TechnicalLevels

log = logging.getLogger(__name__)


# ── Pivot Points (Classic) ────────────────────────────────────────────────────

def _pivot_points(high: float, low: float, close: float) -> dict:
    pp = (high + low + close) / 3
    r1 = 2 * pp - low
    s1 = 2 * pp - high
    r2 = pp + (high - low)
    s2 = pp - (high - low)
    r3 = high + 2 * (pp - low)
    s3 = low - 2 * (high - pp)
    return {
        "pivot": pp,
        "R1": r1, "R2": r2, "R3": r3,
        "S1": s1, "S2": s2, "S3": s3,
    }


# ── Swing High / Low Detection ────────────────────────────────────────────────

def _find_swing_levels(
    df: pd.DataFrame,
    window: int = 10,
    top_n: int = 5,
) -> tuple[list[float], list[float]]:
    """Return (swing_supports, swing_resistances) sorted by proximity to close."""
    highs: list[float] = []
    lows: list[float] = []

    for i in range(window, len(df) - window):
        h = df["High"].iloc[i]
        l = df["Low"].iloc[i]
        if h == df["High"].iloc[i - window:i + window + 1].max():
            highs.append(round(h, 4))
        if l == df["Low"].iloc[i - window:i + window + 1].min():
            lows.append(round(l, 4))

    # Cluster close levels (within 0.2% of each other)
    def cluster(levels: list[float]) -> list[float]:
        if not levels:
            return []
        levels = sorted(set(levels))
        clustered: list[float] = [levels[0]]
        for v in levels[1:]:
            if abs(v - clustered[-1]) / max(clustered[-1], 1e-9) > 0.002:
                clustered.append(v)
        return clustered

    close = df["Close"].iloc[-1]
    swing_res = sorted(
        [h for h in cluster(highs) if h > close],
        key=lambda x: abs(x - close),
    )[:top_n]
    swing_sup = sorted(
        [l for l in cluster(lows) if l < close],
        key=lambda x: abs(x - close),
    )[:top_n]

    return swing_sup, swing_res


# ── RSI ───────────────────────────────────────────────────────────────────────

def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    val = rsi.dropna().iloc[-1] if not rsi.dropna().empty else 50.0
    return round(float(val), 2)


# ── MACD ──────────────────────────────────────────────────────────────────────

def _macd_signal(series: pd.Series) -> str:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
        return "BULLISH"
    if hist.iloc[-1] < 0 and hist.iloc[-2] >= 0:
        return "BEARISH"
    if hist.iloc[-1] > 0:
        return "BULLISH"
    if hist.iloc[-1] < 0:
        return "BEARISH"
    return "NEUTRAL"


# ── ATR ───────────────────────────────────────────────────────────────────────

def _atr(df: pd.DataFrame, period: int = 14) -> float:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr_val = tr.rolling(period).mean().dropna().iloc[-1]
    return round(float(atr_val), 4)


# ── Trend Signal (MA crossover) ───────────────────────────────────────────────

def _trend_signal(series: pd.Series) -> str:
    if len(series) < 50:
        return "SIDEWAYS"
    ma50 = series.rolling(50).mean().iloc[-1]
    ma200 = series.rolling(200).mean().iloc[-1] if len(series) >= 200 else ma50
    price = series.iloc[-1]
    if price > ma50 > ma200:
        return "UPTREND"
    if price < ma50 < ma200:
        return "DOWNTREND"
    return "SIDEWAYS"


# ── Main Entry Point ──────────────────────────────────────────────────────────

def compute_technical_levels(df: pd.DataFrame) -> Optional[TechnicalLevels]:
    """
    Given an OHLCV DataFrame (columns: Open, High, Low, Close, Volume),
    compute and return TechnicalLevels.
    """
    try:
        if df is None or len(df) < 20:
            return None

        # Pivot points from last completed candle
        last = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
        pivots = _pivot_points(
            high=float(last["High"]),
            low=float(last["Low"]),
            close=float(last["Close"]),
        )

        swing_sup, swing_res = _find_swing_levels(df)
        rsi_val = _rsi(df["Close"])
        macd = _macd_signal(df["Close"])
        atr_val = _atr(df)
        trend = _trend_signal(df["Close"])

        return TechnicalLevels(
            pivot=round(pivots["pivot"], 4),
            supports=[
                round(pivots["S1"], 4),
                round(pivots["S2"], 4),
                round(pivots["S3"], 4),
            ],
            resistances=[
                round(pivots["R1"], 4),
                round(pivots["R2"], 4),
                round(pivots["R3"], 4),
            ],
            swing_supports=[round(v, 4) for v in swing_sup[:3]],
            swing_resistances=[round(v, 4) for v in swing_res[:3]],
            rsi_14=rsi_val,
            macd_signal=macd,
            trend_signal=trend,
            atr=atr_val,
        )
    except Exception as exc:
        log.error("Technical analysis error: %s", exc)
        return None


def format_levels_for_prompt(levels: TechnicalLevels, price: float) -> str:
    """Format technical levels as a readable string for the Claude prompt."""
    lines = [
        f"Pivot Point: {levels.pivot}",
        f"Pivot Supports  → S1: {levels.supports[0]}  S2: {levels.supports[1]}  S3: {levels.supports[2]}",
        f"Pivot Resistances → R1: {levels.resistances[0]}  R2: {levels.resistances[1]}  R3: {levels.resistances[2]}",
    ]
    if levels.swing_supports:
        lines.append(f"Swing Supports  : {', '.join(str(v) for v in levels.swing_supports)}")
    if levels.swing_resistances:
        lines.append(f"Swing Resistances: {', '.join(str(v) for v in levels.swing_resistances)}")

    lines += [
        f"RSI (14): {levels.rsi_14}",
        f"MACD Signal: {levels.macd_signal}",
        f"Trend (MA): {levels.trend_signal}",
        f"ATR (14): {levels.atr}",
    ]
    return "\n".join(lines)
