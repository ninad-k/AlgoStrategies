"""
Feature engineering for EMA200 Squeeze ML model.
Computes technical indicators used as input features for the ONNX model.
"""

import numpy as np
import pandas as pd


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period).mean()


def compute_supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                       period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    atr = compute_atr(high, low, close, period)
    mid = (high + low) / 2
    upper = mid + multiplier * atr
    lower = mid - multiplier * atr

    st_upper = np.full(len(close), np.nan)
    st_lower = np.full(len(close), np.nan)
    direction = np.full(len(close), np.nan)

    close_arr = close.values
    upper_arr = upper.values
    lower_arr = lower.values

    # Find first valid ATR index
    first_valid = int(atr.first_valid_index() if isinstance(atr.first_valid_index(), int)
                      else atr.reset_index(drop=True).first_valid_index())

    if first_valid is None:
        return pd.DataFrame({"st_value": np.nan, "st_direction": np.nan}, index=close.index)

    st_upper[first_valid] = upper_arr[first_valid]
    st_lower[first_valid] = lower_arr[first_valid]
    direction[first_valid] = 1 if close_arr[first_valid] > st_upper[first_valid] else -1

    for i in range(first_valid + 1, len(close_arr)):
        if np.isnan(upper_arr[i]):
            continue

        # Lower band
        if lower_arr[i] > st_lower[i - 1] or close_arr[i - 1] < st_lower[i - 1]:
            st_lower[i] = lower_arr[i]
        else:
            st_lower[i] = st_lower[i - 1]

        # Upper band
        if upper_arr[i] < st_upper[i - 1] or close_arr[i - 1] > st_upper[i - 1]:
            st_upper[i] = upper_arr[i]
        else:
            st_upper[i] = st_upper[i - 1]

        # Direction
        if direction[i - 1] == 1:
            direction[i] = -1 if close_arr[i] < st_lower[i] else 1
        else:
            direction[i] = 1 if close_arr[i] > st_upper[i] else -1

    st_value = np.where(direction == 1, st_lower, st_upper)
    return pd.DataFrame({"st_value": st_value, "st_direction": direction}, index=close.index)


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.DataFrame:
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr = compute_atr(high, low, close, period)
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)

    di_sum = plus_di + minus_di
    dx = 100 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, min_periods=period).mean()

    return pd.DataFrame({"adx": adx, "plus_di": plus_di, "minus_di": minus_di})


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "macd_signal": signal_line, "macd_hist": histogram})


def compute_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    bb_width = (upper - lower) / sma
    bb_pct = (close - lower) / (upper - lower)
    return pd.DataFrame({"bb_upper": upper, "bb_lower": lower, "bb_width": bb_width, "bb_pct": bb_pct})


# Feature names used by the model (must match training order)
FEATURE_NAMES = [
    "ema200_dist",          # Distance from EMA200 as % of price
    "ema_slope",            # EMA200 slope (5-bar change)
    "rsi_14",               # RSI 14
    "rsi_7",                # RSI 7 (fast)
    "atr_14_pct",           # ATR as % of price
    "adx",                  # ADX value
    "plus_di",              # +DI
    "minus_di",             # -DI
    "di_diff",              # +DI - -DI
    "st_direction",         # SuperTrend direction (1/-1)
    "st_dist",              # Distance from SuperTrend as % of price
    "macd",                 # MACD line
    "macd_signal",          # MACD signal line
    "macd_hist",            # MACD histogram
    "bb_width",             # Bollinger Band width
    "bb_pct",               # Price position in BB (0-1)
    "vol_ratio",            # Volume / 20-bar avg volume
    "price_change_1",       # 1-bar price change %
    "price_change_3",       # 3-bar price change %
    "price_change_5",       # 5-bar price change %
    "high_low_range",       # (High-Low)/Close as %
    "close_vs_open",        # (Close-Open)/Open as %
    "ema_touch",            # 1 if candle touches EMA200
    "candles_since_touch",  # Bars since last EMA touch
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build all features from OHLCV DataFrame.
    Expects columns: Open, High, Low, Close, Volume
    Returns DataFrame with feature columns + original data.
    """
    df = df.copy()

    # EMA 200
    df["ema200"] = compute_ema(df["Close"], 200)
    df["ema200_dist"] = (df["Close"] - df["ema200"]) / df["Close"] * 100

    # EMA slope (5-bar)
    df["ema_slope"] = (df["ema200"] - df["ema200"].shift(5)) / df["ema200"].shift(5) * 100

    # RSI
    df["rsi_14"] = compute_rsi(df["Close"], 14)
    df["rsi_7"] = compute_rsi(df["Close"], 7)

    # ATR
    atr = compute_atr(df["High"], df["Low"], df["Close"], 14)
    df["atr_14_pct"] = atr / df["Close"] * 100

    # ADX
    adx_df = compute_adx(df["High"], df["Low"], df["Close"], 14)
    df["adx"] = adx_df["adx"]
    df["plus_di"] = adx_df["plus_di"]
    df["minus_di"] = adx_df["minus_di"]
    df["di_diff"] = adx_df["plus_di"] - adx_df["minus_di"]

    # SuperTrend
    st_df = compute_supertrend(df["High"], df["Low"], df["Close"], 10, 3.0)
    df["st_direction"] = st_df["st_direction"]
    df["st_dist"] = (df["Close"] - st_df["st_value"]) / df["Close"] * 100

    # MACD
    macd_df = compute_macd(df["Close"])
    df["macd"] = macd_df["macd"]
    df["macd_signal"] = macd_df["macd_signal"]
    df["macd_hist"] = macd_df["macd_hist"]

    # Bollinger Bands
    bb_df = compute_bollinger(df["Close"])
    df["bb_width"] = bb_df["bb_width"]
    df["bb_pct"] = bb_df["bb_pct"]

    # Volume ratio
    df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

    # Price changes
    df["price_change_1"] = df["Close"].pct_change(1) * 100
    df["price_change_3"] = df["Close"].pct_change(3) * 100
    df["price_change_5"] = df["Close"].pct_change(5) * 100

    # Candle shape
    df["high_low_range"] = (df["High"] - df["Low"]) / df["Close"] * 100
    df["close_vs_open"] = (df["Close"] - df["Open"]) / df["Open"] * 100

    # EMA touch
    df["ema_touch"] = ((df["Low"] <= df["ema200"]) & (df["High"] >= df["ema200"])).astype(float)

    # Candles since last EMA touch
    touch_mask = df["ema_touch"] == 1
    df["candles_since_touch"] = (~touch_mask).groupby(touch_mask.cumsum()).cumsum()

    return df
