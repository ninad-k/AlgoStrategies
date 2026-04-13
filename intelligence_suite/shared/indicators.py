"""
Intelligence Suite — Technical Indicator Engine
=================================================
30+ indicators computed from OHLCV data using pandas_ta.
Adapted from execution/gemma_trader/local_trader.py.
"""

import logging

import numpy as np
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


def calculate_indicators(df: pd.DataFrame, symbol: str = "") -> dict:
    """
    Calculate 30+ technical indicators from OHLCV data.
    Returns a flat dict ready for model analysis.
    """
    if df is None or len(df) < 50:
        logger.warning(
            f"Not enough data: {len(df) if df is not None else 0} bars (need 50+)"
        )
        return {}

    df = df.copy()

    # ── Trend ──
    df.ta.ema(length=9, append=True)
    df.ta.ema(length=20, append=True)
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.sma(length=20, append=True)
    df.ta.sma(length=50, append=True)
    df.ta.adx(length=14, append=True)
    df.ta.ichimoku(append=True)
    for fn, kw in [
        (df.ta.supertrend, dict(length=10, multiplier=3.0, append=True)),
        (df.ta.psar, dict(append=True)),
        (df.ta.vwap, dict(append=True)),
    ]:
        try:
            fn(**kw)
        except Exception:
            pass

    # ── Momentum ──
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.stochrsi(length=14, append=True)
    df.ta.stoch(append=True)
    df.ta.cci(length=20, append=True)
    df.ta.willr(length=14, append=True)
    df.ta.roc(length=10, append=True)
    df.ta.mfi(length=14, append=True)

    # ── Volatility ──
    df.ta.atr(length=14, append=True)
    df.ta.bbands(length=20, std=2.0, append=True)
    for fn, kw in [
        (df.ta.kc, dict(length=20, scalar=1.5, append=True)),
        (df.ta.donchian, dict(lower_length=20, upper_length=20, append=True)),
    ]:
        try:
            fn(**kw)
        except Exception:
            pass

    # ── Volume ──
    for fn in [df.ta.obv, df.ta.ad]:
        try:
            fn(append=True)
        except Exception:
            pass

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest

    def sf(col, default=0):
        try:
            v = latest.get(col, default)
            return default if pd.isna(v) else round(float(v), 4)
        except (TypeError, ValueError):
            return default

    def sf_prev(col, default=0):
        try:
            v = prev.get(col, default)
            return default if pd.isna(v) else round(float(v), 4)
        except (TypeError, ValueError):
            return default

    # ── Trend classification ──
    ema9, ema20, ema50, ema200 = sf("EMA_9"), sf("EMA_20"), sf("EMA_50"), sf("EMA_200")
    if ema9 > ema20 > ema50 > ema200:
        trend = "STRONG_BULLISH"
    elif ema9 > ema20 > ema50:
        trend = "BULLISH"
    elif ema9 < ema20 < ema50 < ema200:
        trend = "STRONG_BEARISH"
    elif ema9 < ema20 < ema50:
        trend = "BEARISH"
    else:
        trend = "MIXED"

    # EMA crossover
    prev_ema9, prev_ema20 = sf_prev("EMA_9"), sf_prev("EMA_20")
    if prev_ema9 <= prev_ema20 and ema9 > ema20:
        ema_cross = "BULLISH_CROSS_9_20"
    elif prev_ema9 >= prev_ema20 and ema9 < ema20:
        ema_cross = "BEARISH_CROSS_9_20"
    else:
        prev_ema50 = sf_prev("EMA_50")
        if sf_prev("EMA_20") <= prev_ema50 and ema20 > ema50:
            ema_cross = "GOLDEN_CROSS"
        elif sf_prev("EMA_20") >= prev_ema50 and ema20 < ema50:
            ema_cross = "DEATH_CROSS"
        else:
            ema_cross = "NONE"

    # ── Volume ──
    vol_sma = df["volume"].rolling(20).mean().iloc[-1]
    vol_ratio = round(float(latest["volume"] / vol_sma), 2) if vol_sma > 0 else 1.0
    vol_trend = (
        "SURGE" if vol_ratio > 2.0 else
        "HIGH" if vol_ratio > 1.5 else
        "ABOVE_AVG" if vol_ratio > 1.0 else "LOW"
    )

    # ── Bollinger Bands ──
    bb_upper = sf("BBU_20_2.0")
    bb_lower = sf("BBL_20_2.0")
    bb_mid = sf("BBM_20_2.0")
    close = sf("close", float(latest["close"]))
    bb_width = round((bb_upper - bb_lower) / bb_mid * 100, 2) if bb_mid > 0 else 0
    if close > bb_upper:
        bb_pos = "ABOVE_UPPER"
    elif close < bb_lower:
        bb_pos = "BELOW_LOWER"
    elif close > bb_mid:
        bb_pos = "UPPER_HALF"
    else:
        bb_pos = "LOWER_HALF"

    # ── Ichimoku ──
    isa, isb = sf("ISA_9"), sf("ISB_26")
    its, iks = sf("ITS_9"), sf("IKS_26")
    if close > max(isa, isb) and its > iks:
        ichimoku_signal = "STRONG_BULLISH"
    elif close > max(isa, isb):
        ichimoku_signal = "BULLISH"
    elif close < min(isa, isb) and its < iks:
        ichimoku_signal = "STRONG_BEARISH"
    elif close < min(isa, isb):
        ichimoku_signal = "BEARISH"
    else:
        ichimoku_signal = "IN_CLOUD"
    cloud_color = "GREEN" if isa > isb else "RED"

    # ── Supertrend ──
    st_col = [c for c in df.columns if c.startswith("SUPERT_")]
    supertrend_dir = "NONE"
    if st_col:
        supertrend_dir = "BULLISH" if close > sf(st_col[0]) else "BEARISH"

    # ── PSAR ──
    psar_long = sf("PSARl_0.02_0.2")
    psar_short = sf("PSARs_0.02_0.2")
    psar_signal = (
        "BULLISH" if psar_long > 0 and close > psar_long else
        "BEARISH" if psar_short > 0 and close < psar_short else "NEUTRAL"
    )

    # ── Candle patterns ──
    patterns = _detect_candle_patterns(df)

    # ── Last 5 candles ──
    last5 = []
    for i in range(-5, 0):
        if abs(i) <= len(df):
            c = df.iloc[i]
            body = abs(float(c["close"]) - float(c["open"]))
            total = float(c["high"]) - float(c["low"])
            body_pct = round(body / total * 100, 1) if total > 0 else 0
            direction = "UP" if float(c["close"]) >= float(c["open"]) else "DOWN"
            last5.append(f"{direction}({body_pct}%)")

    # ── Support / Resistance ──
    support, resistance = _find_support_resistance(df)

    return {
        "symbol": symbol, "data_source": "mt5",
        "close": close,
        "open": sf("open", float(latest["open"])),
        "high": sf("high", float(latest["high"])),
        "low": sf("low", float(latest["low"])),
        "volume": round(float(latest["volume"]), 0),
        "ema9": ema9, "ema20": ema20, "ema50": ema50, "ema200": ema200,
        "sma20": sf("SMA_20"), "sma50": sf("SMA_50"),
        "trend": trend, "ema_cross": ema_cross,
        "adx": sf("ADX_14"), "di_plus": sf("DMP_14"), "di_minus": sf("DMN_14"),
        "supertrend": supertrend_dir, "psar_signal": psar_signal,
        "ichimoku_tenkan": its, "ichimoku_kijun": iks,
        "ichimoku_span_a": isa, "ichimoku_span_b": isb,
        "ichimoku_signal": ichimoku_signal, "ichimoku_cloud_color": cloud_color,
        "rsi": sf("RSI_14", 50),
        "macd": sf("MACD_12_26_9"), "macd_signal": sf("MACDs_12_26_9"),
        "macd_hist": sf("MACDh_12_26_9"),
        "stoch_rsi_k": sf("STOCHRSIk_14_14_3_3", 50),
        "stoch_rsi_d": sf("STOCHRSId_14_14_3_3", 50),
        "stoch_k": sf("STOCHk_14_3_3", 50), "stoch_d": sf("STOCHd_14_3_3", 50),
        "cci": sf("CCI_20_0.015"), "williams_r": sf("WILLR_14"),
        "roc": sf("ROC_10"), "mfi": sf("MFI_14", 50),
        "atr": sf("ATRr_14"),
        "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
        "bb_pos": bb_pos, "bb_width": bb_width,
        "vol_trend": vol_trend, "vol_ratio": vol_ratio, "obv": sf("OBV"),
        "candle_patterns": ", ".join(patterns) if patterns else "NONE",
        "last_5_candles": " → ".join(last5),
        "nearest_support": support, "nearest_resistance": resistance,
        "vwap": sf("VWAP_D", close),
    }


def _detect_candle_patterns(df: pd.DataFrame) -> list:
    """Detect candlestick patterns from the last few candles."""
    patterns = []
    if len(df) < 3:
        return patterns

    c, p, pp = df.iloc[-1], df.iloc[-2], df.iloc[-3]
    o, h, l, cl = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])
    po, ph, pl, pcl = float(p["open"]), float(p["high"]), float(p["low"]), float(p["close"])
    body = abs(cl - o)
    total_range = h - l
    upper_wick = h - max(o, cl)
    lower_wick = min(o, cl) - l

    if total_range == 0:
        return patterns

    body_pct = body / total_range
    if body_pct < 0.1:
        patterns.append("DOJI")
    if lower_wick > body * 2 and upper_wick < body * 0.5 and cl > o:
        patterns.append("HAMMER")
    if upper_wick > body * 2 and lower_wick < body * 0.5 and cl < o:
        patterns.append("SHOOTING_STAR")
    if pcl < po and cl > o and cl > po and o < pcl:
        patterns.append("BULLISH_ENGULFING")
    if pcl > po and cl < o and cl < po and o > pcl:
        patterns.append("BEARISH_ENGULFING")

    ppo, ppcl = float(pp["open"]), float(pp["close"])
    if ppcl < ppo and abs(pcl - po) < (ph - pl) * 0.3 and cl > o and cl > (ppo + ppcl) / 2:
        patterns.append("MORNING_STAR")
    if ppcl > ppo and abs(pcl - po) < (ph - pl) * 0.3 and cl < o and cl < (ppo + ppcl) / 2:
        patterns.append("EVENING_STAR")
    if ppcl > ppo and pcl > po and cl > o and cl > pcl > ppcl:
        patterns.append("THREE_WHITE_SOLDIERS")
    if ppcl < ppo and pcl < po and cl < o and cl < pcl < ppcl:
        patterns.append("THREE_BLACK_CROWS")

    return patterns


def _find_support_resistance(df: pd.DataFrame, lookback: int = 50) -> tuple:
    """Find nearest support and resistance from swing highs/lows."""
    if len(df) < lookback:
        lookback = len(df)
    recent = df.tail(lookback)
    close = float(df.iloc[-1]["close"])

    highs = recent["high"].astype(float).values
    lows = recent["low"].astype(float).values
    supports, resistances = [], []

    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            if highs[i] > close:
                resistances.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            if lows[i] < close:
                supports.append(lows[i])

    nearest_support = round(max(supports), 2) if supports else round(close * 0.998, 2)
    nearest_resistance = round(min(resistances), 2) if resistances else round(close * 1.002, 2)
    return nearest_support, nearest_resistance


def compute_regime_features(df: pd.DataFrame) -> dict:
    """
    Extract features used by the Market Regime Detector.
    Returns volatility, trend strength, and volume metrics.
    """
    if df is None or len(df) < 50:
        return {}

    df = df.copy()
    df.ta.atr(length=14, append=True)
    df.ta.adx(length=14, append=True)
    df.ta.bbands(length=20, std=2.0, append=True)
    df.ta.ema(length=20, append=True)
    df.ta.ema(length=200, append=True)

    latest = df.iloc[-1]

    def sf(col, default=0):
        try:
            v = latest.get(col, default)
            return default if pd.isna(v) else round(float(v), 4)
        except (TypeError, ValueError):
            return default

    atr_14 = sf("ATRr_14", 1)
    atr_short = df["ATRr_14"].iloc[-7:].mean() if "ATRr_14" in df.columns else atr_14
    atr_long = df["ATRr_14"].iloc[-30:].mean() if "ATRr_14" in df.columns else atr_14
    atr_ratio = round(float(atr_short / atr_long), 4) if atr_long > 0 else 1.0

    close = float(latest["close"])
    bb_upper = sf("BBU_20_2.0")
    bb_lower = sf("BBL_20_2.0")
    bb_width = round((bb_upper - bb_lower) / close * 100, 4) if close > 0 else 0

    vol_sma = df["volume"].rolling(20).mean().iloc[-1]
    vol_ratio = round(float(latest["volume"] / vol_sma), 2) if vol_sma > 0 else 1.0

    returns = df["close"].pct_change().dropna()
    recent_returns = returns.tail(20)
    return_std = round(float(recent_returns.std()), 6) if len(recent_returns) > 1 else 0

    return {
        "atr": atr_14,
        "atr_ratio": atr_ratio,
        "adx": sf("ADX_14"),
        "di_plus": sf("DMP_14"),
        "di_minus": sf("DMN_14"),
        "bb_width": bb_width,
        "vol_ratio": vol_ratio,
        "return_std": return_std,
        "ema20": sf("EMA_20"),
        "ema200": sf("EMA_200"),
        "close": close,
        "price_vs_ema200": round((close / sf("EMA_200", close) - 1) * 100, 2),
    }
