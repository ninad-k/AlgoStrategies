"""
features.py — Enriched feature computation for Gemma's decision prompt.

Pure functions. Each takes an OHLCV DataFrame indexed by time (same shape as
local_trader.calculate_indicators expects) and returns a dict of scalar
values or short lists. All returns are None-safe: insufficient data yields
neutral defaults rather than raising.

Groups:
  compute_market_structure  → swings, structure, BOS, CHoCH, inside/outside bar
  compute_pivots            → classic + Camarilla pivot levels from prior-24h H/L/C
  compute_sr_strength       → touch-scored support/resistance levels (top 5)
  compute_advanced_candles  → pin bar, tweezer, three-inside
  compute_modern_indicators → supertrend dir, chandelier exits, CMF, AO

All numeric outputs are rounded to 4 decimals for prices, 2 for oscillators,
to match the rounding convention already used by calculate_indicators.
"""

from __future__ import annotations

import pandas as pd

try:
    import pandas_ta as ta
except Exception:
    ta = None


# ─── helpers ────────────────────────────────────────────────────

def _safe_float(x, default=0.0) -> float:
    try:
        if pd.isna(x):
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _round_price(x, default=0.0) -> float:
    return round(_safe_float(x, default), 4)


def _find_swings(df: pd.DataFrame, lookback: int = 2):
    """
    Return (swing_high_idxs, swing_low_idxs). A bar i is a swing high iff
    its high is strictly greater than the `lookback` bars on each side.
    """
    n = len(df)
    highs = df["high"].values
    lows = df["low"].values
    sh, sl = [], []
    for i in range(lookback, n - lookback):
        if all(highs[i] > highs[i - k] for k in range(1, lookback + 1)) and \
           all(highs[i] > highs[i + k] for k in range(1, lookback + 1)):
            sh.append(i)
        if all(lows[i] < lows[i - k] for k in range(1, lookback + 1)) and \
           all(lows[i] < lows[i + k] for k in range(1, lookback + 1)):
            sl.append(i)
    return sh, sl


# ─── 1. Market structure ────────────────────────────────────────

def compute_market_structure(df: pd.DataFrame, n_swings: int = 5) -> dict:
    """Higher highs / lower lows sequence, BOS, CHoCH, inside/outside bar."""
    defaults = {
        "swing_highs": [],
        "swing_lows": [],
        "structure": "INDECISIVE",
        "bos": "NONE",
        "choch": "NONE",
        "inside_bar": False,
        "outside_bar": False,
    }
    if df is None or len(df) < 10:
        return defaults

    sh_idx, sl_idx = _find_swings(df, lookback=2)
    last_highs = [_round_price(df["high"].iloc[i]) for i in sh_idx[-n_swings:]]
    last_lows = [_round_price(df["low"].iloc[i]) for i in sl_idx[-n_swings:]]

    # Structure from the last two swings of each kind.
    structure = "INDECISIVE"
    if len(last_highs) >= 2 and len(last_lows) >= 2:
        hh = last_highs[-1] > last_highs[-2]
        hl = last_lows[-1] > last_lows[-2]
        if hh and hl:
            structure = "HH_HL"
        elif (not hh) and (not hl):
            structure = "LH_LL"
        elif hh and not hl:
            structure = "HH_LL"
        elif (not hh) and hl:
            structure = "LH_HL"

    # BOS: close breaks most recent confirmed swing high / low.
    close = _safe_float(df["close"].iloc[-1])
    bos = "NONE"
    if last_highs and close > last_highs[-1]:
        bos = "BULLISH_BOS"
    elif last_lows and close < last_lows[-1]:
        bos = "BEARISH_BOS"

    # CHoCH: flip in the prevailing structure signalled by the latest swing.
    # Bull CHoCH = was LH_LL and a new HH forms; Bear CHoCH = was HH_HL and a new LL forms.
    choch = "NONE"
    if len(last_highs) >= 3 and len(last_lows) >= 3:
        prior_structure_bear = (last_highs[-3] > last_highs[-2]) and (last_lows[-3] > last_lows[-2])
        prior_structure_bull = (last_highs[-3] < last_highs[-2]) and (last_lows[-3] < last_lows[-2])
        if prior_structure_bear and last_highs[-1] > last_highs[-2]:
            choch = "BULL_CHOCH"
        elif prior_structure_bull and last_lows[-1] < last_lows[-2]:
            choch = "BEAR_CHOCH"

    # Inside / outside bar (current vs previous).
    inside_bar = outside_bar = False
    if len(df) >= 2:
        cur_h = _safe_float(df["high"].iloc[-1])
        cur_l = _safe_float(df["low"].iloc[-1])
        prev_h = _safe_float(df["high"].iloc[-2])
        prev_l = _safe_float(df["low"].iloc[-2])
        inside_bar = (cur_h < prev_h) and (cur_l > prev_l)
        outside_bar = (cur_h > prev_h) and (cur_l < prev_l)

    return {
        "swing_highs": last_highs,
        "swing_lows": last_lows,
        "structure": structure,
        "bos": bos,
        "choch": choch,
        "inside_bar": inside_bar,
        "outside_bar": outside_bar,
    }


# ─── 2. Pivot levels ────────────────────────────────────────────

def compute_pivots(df: pd.DataFrame, session_bars: int = 1440) -> dict:
    """
    Classic floor pivots + Camarilla, computed from the high/low/close of the
    prior "session" window. For 1-min bars this defaults to the prior 1440
    bars (~24h); adjust session_bars for higher timeframes.
    """
    defaults = {
        "pivot_pp": 0.0,
        "pivot_r1": 0.0, "pivot_r2": 0.0, "pivot_r3": 0.0,
        "pivot_s1": 0.0, "pivot_s2": 0.0, "pivot_s3": 0.0,
        "cam_r3": 0.0, "cam_r4": 0.0,
        "cam_s3": 0.0, "cam_s4": 0.0,
    }
    if df is None or len(df) < max(50, session_bars // 10):
        return defaults

    # Use the most recent completed `session_bars` window before the current
    # bar — if not enough history, fall back to the full range excluding
    # the current bar.
    end = len(df) - 1  # exclude the forming bar
    start = max(0, end - session_bars)
    window = df.iloc[start:end]
    if len(window) < 10:
        return defaults

    high = _safe_float(window["high"].max())
    low = _safe_float(window["low"].min())
    close = _safe_float(window["close"].iloc[-1])
    if high <= 0 or low <= 0 or close <= 0:
        return defaults

    pp = (high + low + close) / 3.0
    r1 = 2 * pp - low
    s1 = 2 * pp - high
    r2 = pp + (high - low)
    s2 = pp - (high - low)
    r3 = high + 2 * (pp - low)
    s3 = low - 2 * (high - pp)

    rng = high - low
    cam_r3 = close + rng * 1.1 / 4
    cam_r4 = close + rng * 1.1 / 2
    cam_s3 = close - rng * 1.1 / 4
    cam_s4 = close - rng * 1.1 / 2

    return {
        "pivot_pp": _round_price(pp),
        "pivot_r1": _round_price(r1),
        "pivot_r2": _round_price(r2),
        "pivot_r3": _round_price(r3),
        "pivot_s1": _round_price(s1),
        "pivot_s2": _round_price(s2),
        "pivot_s3": _round_price(s3),
        "cam_r3": _round_price(cam_r3),
        "cam_r4": _round_price(cam_r4),
        "cam_s3": _round_price(cam_s3),
        "cam_s4": _round_price(cam_s4),
    }


# ─── 3. S/R strength (touch scoring) ───────────────────────────

def compute_sr_strength(df: pd.DataFrame, top_n: int = 5) -> dict:
    """
    Cluster swing highs and lows into S/R levels and score each by touch count.
    A "touch" = any bar whose high or low came within 0.5×ATR of the level.
    Returns top_n clusters by touch score.
    """
    default = {"sr_touch_scores": {}}
    if df is None or len(df) < 30:
        return default

    sh_idx, sl_idx = _find_swings(df, lookback=2)
    swing_prices = (
        [float(df["high"].iloc[i]) for i in sh_idx]
        + [float(df["low"].iloc[i]) for i in sl_idx]
    )
    if not swing_prices:
        return default

    # Tolerance = 0.5 × ATR-like range proxy.
    atr_proxy = float((df["high"] - df["low"]).tail(14).mean()) or 1.0
    tol = atr_proxy * 0.5

    # Agglomerate: sort and merge levels within tolerance.
    swing_prices.sort()
    clusters = []
    for p in swing_prices:
        if clusters and abs(p - clusters[-1][-1]) <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])

    # Score each cluster by counting bars whose high or low is within tol
    # of the cluster mean.
    highs = df["high"].values
    lows = df["low"].values
    scored = []
    for grp in clusters:
        level = sum(grp) / len(grp)
        touches = int(
            ((abs(highs - level) <= tol) | (abs(lows - level) <= tol)).sum()
        )
        scored.append((level, touches))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:top_n]
    return {
        "sr_touch_scores": {
            _round_price(level): int(touches) for level, touches in top
        }
    }


# ─── 4. Advanced candlestick patterns ──────────────────────────

def compute_advanced_candles(df: pd.DataFrame) -> dict:
    """Pin bar, tweezer top/bottom, three-inside-up/down."""
    defaults = {
        "pin_bar": "NONE",
        "tweezer": "NONE",
        "three_inside": "NONE",
    }
    if df is None or len(df) < 3:
        return defaults

    c = df.iloc[-1]
    p = df.iloc[-2]
    pp = df.iloc[-3]

    # Pin bar: one wick ≥ 2× body, other wick small, close in opposite 1/3
    body = abs(float(c["close"]) - float(c["open"]))
    upper = float(c["high"]) - max(float(c["close"]), float(c["open"]))
    lower = min(float(c["close"]), float(c["open"])) - float(c["low"])
    rng = float(c["high"]) - float(c["low"])
    pin = "NONE"
    if rng > 0 and body > 0:
        if lower >= 2 * body and upper <= body and (float(c["close"]) - float(c["low"])) / rng > 0.66:
            pin = "BULL"
        elif upper >= 2 * body and lower <= body and (float(c["high"]) - float(c["close"])) / rng > 0.66:
            pin = "BEAR"

    # Tweezer: two consecutive bars with near-identical extreme on the
    # opposite side of the trend.
    tweezer = "NONE"
    eps = max(rng * 0.05, 1e-6)
    if abs(float(c["high"]) - float(p["high"])) <= eps and \
       float(c["close"]) < float(c["open"]) and float(p["close"]) > float(p["open"]):
        tweezer = "TOP"
    elif abs(float(c["low"]) - float(p["low"])) <= eps and \
         float(c["close"]) > float(c["open"]) and float(p["close"]) < float(p["open"]):
        tweezer = "BOTTOM"

    # Three-inside-up/down: prior big bar, middle bar inside it, current bar
    # closes beyond the prior bar's open.
    three_inside = "NONE"
    pp_body = abs(float(pp["close"]) - float(pp["open"]))
    if pp_body > 0:
        inside_middle = (
            float(p["high"]) <= float(pp["high"])
            and float(p["low"]) >= float(pp["low"])
        )
        if inside_middle:
            if float(pp["close"]) < float(pp["open"]) and float(c["close"]) > float(pp["open"]):
                three_inside = "UP"
            elif float(pp["close"]) > float(pp["open"]) and float(c["close"]) < float(pp["open"]):
                three_inside = "DOWN"

    return {
        "pin_bar": pin,
        "tweezer": tweezer,
        "three_inside": three_inside,
    }


# ─── 5. Modern indicators ───────────────────────────────────────

def compute_modern_indicators(df: pd.DataFrame) -> dict:
    """Supertrend direction, Chandelier exits, CMF, Awesome Oscillator."""
    defaults = {
        "supertrend_dir": "NONE",
        "chandelier_exit_long": 0.0,
        "chandelier_exit_short": 0.0,
        "cmf": 0.0,
        "awesome_osc": 0.0,
        "ao_signal": "NONE",
    }
    if df is None or len(df) < 40:
        return defaults

    out = dict(defaults)
    close = _safe_float(df["close"].iloc[-1])

    # Supertrend direction — recompute here so features.py is self-contained;
    # calculate_indicators may already have appended SUPERT_* columns.
    st_col = [c for c in df.columns if c.startswith("SUPERT_") and "d" not in c]
    if st_col:
        st_val = _safe_float(df[st_col[0]].iloc[-1])
        if st_val:
            out["supertrend_dir"] = "UP" if close > st_val else "DOWN"
    elif ta is not None:
        try:
            st = ta.supertrend(df["high"], df["low"], df["close"], length=10, multiplier=3.0)
            if st is not None and len(st):
                col = [c for c in st.columns if c.startswith("SUPERT_") and "d" not in c]
                if col:
                    out["supertrend_dir"] = "UP" if close > _safe_float(st[col[0]].iloc[-1]) else "DOWN"
        except Exception:
            pass

    # Chandelier Exit — ATR-based trailing stops.
    # long  = rolling_high(22) - ATR(22) * 3
    # short = rolling_low(22)  + ATR(22) * 3
    length = 22
    mult = 3.0
    if len(df) >= length and ta is not None:
        try:
            atr = ta.atr(df["high"], df["low"], df["close"], length=length)
            if atr is not None:
                atr_val = _safe_float(atr.iloc[-1])
                rh = _safe_float(df["high"].tail(length).max())
                rl = _safe_float(df["low"].tail(length).min())
                out["chandelier_exit_long"] = _round_price(rh - atr_val * mult)
                out["chandelier_exit_short"] = _round_price(rl + atr_val * mult)
        except Exception:
            pass

    # CMF — Chaikin Money Flow (20).
    if ta is not None:
        try:
            cmf = ta.cmf(df["high"], df["low"], df["close"], df["volume"], length=20)
            if cmf is not None and len(cmf):
                out["cmf"] = round(_safe_float(cmf.iloc[-1]), 4)
        except Exception:
            pass

    # Awesome Oscillator (5-SMA − 34-SMA of median price).
    median = (df["high"] + df["low"]) / 2.0
    if len(median) >= 34:
        ao_series = median.rolling(5).mean() - median.rolling(34).mean()
        ao = _safe_float(ao_series.iloc[-1])
        out["awesome_osc"] = round(ao, 4)

        # Signal classification.
        prev_ao = _safe_float(ao_series.iloc[-2]) if len(ao_series) >= 2 else 0.0
        if prev_ao < 0 and ao >= 0:
            out["ao_signal"] = "ZERO_CROSS_UP"
        elif prev_ao > 0 and ao <= 0:
            out["ao_signal"] = "ZERO_CROSS_DOWN"
        else:
            # Twin peaks: look for two peaks of same sign where the second is
            # smaller (bearish divergence) or larger-absolute (bullish).
            window = ao_series.tail(20).dropna().values
            if len(window) >= 6:
                peaks = [
                    (i, window[i]) for i in range(1, len(window) - 1)
                    if window[i] > window[i - 1] and window[i] > window[i + 1]
                ]
                troughs = [
                    (i, window[i]) for i in range(1, len(window) - 1)
                    if window[i] < window[i - 1] and window[i] < window[i + 1]
                ]
                if len(peaks) >= 2 and peaks[-1][1] > 0 and peaks[-2][1] > 0 \
                        and peaks[-1][1] < peaks[-2][1]:
                    out["ao_signal"] = "BEAR_TWIN_PEAKS"
                elif len(troughs) >= 2 and troughs[-1][1] < 0 and troughs[-2][1] < 0 \
                        and troughs[-1][1] > troughs[-2][1]:
                    out["ao_signal"] = "BULL_TWIN_PEAKS"

    return out


# ─── top-level orchestrator ─────────────────────────────────────

def compute_all(df: pd.DataFrame) -> dict:
    """Convenience: run every feature block and merge results into one dict."""
    out = {}
    out.update(compute_market_structure(df))
    out.update(compute_pivots(df))
    out.update(compute_sr_strength(df))
    out.update(compute_advanced_candles(df))
    out.update(compute_modern_indicators(df))
    return out
