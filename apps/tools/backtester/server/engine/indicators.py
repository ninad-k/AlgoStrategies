import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> dict:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def vwap(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series
) -> pd.Series:
    typical_price = (high + low + close) / 3
    cum_tp_vol = (typical_price * volume).cumsum()
    cum_vol = volume.cumsum()
    return cum_tp_vol / cum_vol


def bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2
) -> dict:
    middle = sma(series, period)
    rolling_std = series.rolling(window=period).std()
    upper = middle + std_dev * rolling_std
    lower = middle - std_dev * rolling_std
    return {"upper": upper, "middle": middle, "lower": lower}


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> dict:
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = sma(k, d_period)
    return {"k": k, "d": d}


def pivot_points(
    high: pd.Series, low: pd.Series, close: pd.Series
) -> dict:
    pp = (high + low + close) / 3
    r1 = 2 * pp - low
    s1 = 2 * pp - high
    r2 = pp + (high - low)
    s2 = pp - (high - low)
    r3 = high + 2 * (pp - low)
    s3 = low - 2 * (high - pp)
    return {"pp": pp, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}


def crossover(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    prev_a = series_a.shift(1)
    prev_b = series_b.shift(1)
    return (prev_a <= prev_b) & (series_a > series_b)


def crossunder(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    prev_a = series_a.shift(1)
    prev_b = series_b.shift(1)
    return (prev_a >= prev_b) & (series_a < series_b)


def highest(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).max()


def lowest(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).min()


def supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int,
    multiplier: float,
) -> dict:
    """ATR-based SuperTrend (common TradingView-style bands). Returns line and direction (+1 / -1)."""
    atr_s = atr(high, low, close, period).bfill()
    hl2 = (high + low) / 2.0
    upper = (hl2 + multiplier * atr_s).to_numpy(dtype=float)
    lower = (hl2 - multiplier * atr_s).to_numpy(dtype=float)
    c = close.to_numpy(dtype=float)

    n = len(close)
    if n == 0:
        return {
            "supertrend": pd.Series(dtype="float64"),
            "direction": pd.Series(dtype="float64"),
        }

    f_up = np.copy(upper)
    f_lo = np.copy(lower)
    for i in range(1, n):
        if upper[i] < f_up[i - 1] or c[i - 1] > f_up[i - 1]:
            f_up[i] = upper[i]
        else:
            f_up[i] = f_up[i - 1]
        if lower[i] > f_lo[i - 1] or c[i - 1] < f_lo[i - 1]:
            f_lo[i] = lower[i]
        else:
            f_lo[i] = f_lo[i - 1]

    st = np.zeros(n)
    direction = np.ones(n)
    for i in range(n):
        if i == 0:
            st[i] = f_lo[i]
            direction[i] = 1.0
            continue
        if c[i] <= f_up[i]:
            st[i] = f_up[i]
            direction[i] = -1.0
        else:
            st[i] = f_lo[i]
            direction[i] = 1.0

    idx = close.index
    return {
        "supertrend": pd.Series(st, index=idx),
        "direction": pd.Series(direction, index=idx),
        "final_upper": pd.Series(f_up, index=idx),
        "final_lower": pd.Series(f_lo, index=idx),
    }


def dmi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
    smoothing: int = 14,
) -> dict:
    """Directional Movement Index: returns DI+, DI-, and ADX."""
    high = high.astype(float)
    low = low.astype(float)
    close = close.astype(float)

    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=close.index)
    minus_dm = pd.Series(minus_dm, index=close.index)

    alpha = 1.0 / float(period)
    atr_smooth = tr.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    safe_atr = atr_smooth.replace(0, np.nan)
    plus_di = 100.0 * (plus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / safe_atr)
    minus_di = 100.0 * (minus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / safe_atr)

    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    s_alpha = 1.0 / float(smoothing)
    adx_s = dx.ewm(alpha=s_alpha, adjust=False, min_periods=smoothing).mean()

    return {
        "plus": plus_di.fillna(0.0),
        "minus": minus_di.fillna(0.0),
        "adx": adx_s.fillna(0.0),
    }


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average Directional Index (Wilder smoothing)."""
    high = high.astype(float)
    low = low.astype(float)
    close = close.astype(float)

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=close.index)
    minus_dm = pd.Series(minus_dm, index=close.index)

    alpha = 1.0 / float(period)
    atr_smooth = tr.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    plus_di = 100.0 * (
        plus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / atr_smooth.replace(0, np.nan)
    )
    minus_di = 100.0 * (
        minus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / atr_smooth.replace(0, np.nan)
    )
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_s = dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    return adx_s.fillna(0.0)
