"""
ICT Silver Bullet Strategy Bot — MT5 Python
Multi-timeframe bias (W1/D1/H4) + liquidity sweep + displacement candle +
FVG detection + market structure shift + OTE Fibonacci entry.
Scoring system: 14-point checklist, min 6 to trade.
ML layer: SVM/DT/RF ensemble for signal confirmation.
New York session Silver Bullet window (7-11 AM NY).
"""

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from typing import Optional, Tuple
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MAGIC = 20260419
RISK_PCT = 1.0
SB_START = 7   # Silver Bullet window start (NY hour)
SB_END = 11


def get_candles(symbol: str, tf: int, count: int) -> Optional[pd.DataFrame]:
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def calc_bias(df: pd.DataFrame) -> float:
    """Directional bias from price change, structure, and EMA cross."""
    if df is None or len(df) < 20:
        return 0

    close = df["close"].values
    # Price change component (40%)
    pct_change = (close[-1] - close[0]) / close[0] if close[0] != 0 else 0
    price_score = np.clip(pct_change * 100, -1, 1)

    # Structure score (40%): recent higher highs / lower lows
    highs = df["high"].values
    lows = df["low"].values
    hh = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i - 1])
    ll = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i - 1])
    struct_score = (hh - ll) / max(len(highs) - 1, 1)

    # EMA cross (20%)
    ema8 = pd.Series(close).ewm(span=8).mean().iloc[-1]
    ema21 = pd.Series(close).ewm(span=21).mean().iloc[-1]
    ema_score = 1 if ema8 > ema21 else -1

    return 0.4 * price_score + 0.4 * struct_score + 0.2 * ema_score


def get_mtf_bias(symbol: str) -> Tuple[float, str]:
    """Multi-timeframe bias from W1, D1, H4."""
    w1 = calc_bias(get_candles(symbol, mt5.TIMEFRAME_W1, 20))
    d1 = calc_bias(get_candles(symbol, mt5.TIMEFRAME_D1, 20))
    h4 = calc_bias(get_candles(symbol, mt5.TIMEFRAME_H4, 50))

    combined = w1 * 0.4 + d1 * 0.4 + h4 * 0.2
    direction = "BULL" if combined > 0.1 else ("BEAR" if combined < -0.1 else "NEUTRAL")
    return combined, direction


def detect_swing_points(highs: np.ndarray, lows: np.ndarray, lookback: int = 5):
    """Find swing highs and lows."""
    swing_highs, swing_lows = [], []
    for i in range(lookback, len(highs) - lookback):
        if all(highs[i] > highs[i - j] for j in range(1, lookback + 1)) and \
           all(highs[i] > highs[i + j] for j in range(1, lookback + 1)):
            swing_highs.append((i, highs[i]))
        if all(lows[i] < lows[i - j] for j in range(1, lookback + 1)) and \
           all(lows[i] < lows[i + j] for j in range(1, lookback + 1)):
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows


def detect_liquidity_sweep(df: pd.DataFrame, swing_highs, swing_lows, bias: float) -> bool:
    """Check if recent candles swept liquidity pools."""
    if len(df) < 5:
        return False

    for idx, level in swing_lows[-5:]:
        if bias > 0:  # Bullish: sell-side sweep
            for i in range(max(0, len(df) - 5), len(df)):
                if df["low"].iloc[i] < level and df["close"].iloc[i] > level:
                    return True

    for idx, level in swing_highs[-5:]:
        if bias < 0:  # Bearish: buy-side sweep
            for i in range(max(0, len(df) - 5), len(df)):
                if df["high"].iloc[i] > level and df["close"].iloc[i] < level:
                    return True
    return False


def detect_displacement(df: pd.DataFrame) -> bool:
    """Detect displacement candle (strong momentum)."""
    if len(df) < 21:
        return False
    bodies = (df["close"] - df["open"]).abs()
    avg_body = bodies.rolling(20).mean().iloc[-1]
    atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
    latest_body = bodies.iloc[-1]
    return latest_body > 2 * avg_body and latest_body > atr


def detect_fvg(df: pd.DataFrame, direction: int) -> Optional[Tuple[float, float]]:
    """Detect Fair Value Gap in last 20 bars."""
    for i in range(len(df) - 3, max(len(df) - 20, 2), -1):
        if direction > 0:
            gap = df["low"].iloc[i + 2] - df["high"].iloc[i]
            if gap > 0:
                return (df["high"].iloc[i], df["low"].iloc[i + 2])
        else:
            gap = df["low"].iloc[i] - df["high"].iloc[i + 2]
            if gap > 0:
                return (df["high"].iloc[i + 2], df["low"].iloc[i])
    return None


def detect_mss(df: pd.DataFrame, direction: int) -> bool:
    """Market structure shift: new HH (bull) or LL (bear) in last 10 bars."""
    recent = df.tail(10)
    if direction > 0:
        return recent["high"].iloc[-1] > recent["high"].iloc[:-1].max()
    return recent["low"].iloc[-1] < recent["low"].iloc[:-1].min()


def calc_ote_zone(swing_low: float, swing_high: float, direction: int):
    """0.618-0.786 Fibonacci retracement zone."""
    span = swing_high - swing_low
    if direction > 0:
        return swing_high - 0.786 * span, swing_high - 0.618 * span
    return swing_low + 0.618 * span, swing_low + 0.786 * span


def score_setup(bias_score: float, has_sweep: bool, has_displacement: bool,
                has_fvg: bool, has_mss: bool, in_ote: bool, ml_confirms: bool) -> int:
    """Score setup out of 14 points."""
    score = 0
    if abs(bias_score) > 0.1: score += 2
    if has_sweep: score += 3
    if has_displacement: score += 2
    if has_fvg: score += 2
    if has_mss: score += 2
    if in_ote: score += 1
    if ml_confirms: score += 1
    return score


def train_ml_ensemble(df: pd.DataFrame):
    """Train SVM + DT + RF ensemble on features."""
    close = df["close"].values
    features = pd.DataFrame({
        "pct_change": pd.Series(close).pct_change(),
        "hl_ratio": (df["high"] - df["low"]) / df["close"],
        "body_size": (df["close"] - df["open"]).abs() / df["close"],
        "sma8": pd.Series(close).rolling(8).mean(),
        "sma21": pd.Series(close).rolling(21).mean(),
        "sma50": pd.Series(close).rolling(50).mean(),
        "atr": (df["high"] - df["low"]).rolling(14).mean(),
    }).dropna()

    # Label: price rises > 0.1% over next 10 bars
    labels = (pd.Series(close).shift(-10) / pd.Series(close) - 1 > 0.001).astype(int)
    labels = labels.loc[features.index].dropna()
    features = features.loc[labels.index]

    if len(features) < 100:
        return None, None

    X = features.values
    y = labels.values.astype(int)
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    split = int(len(X) * 0.8)
    models = [
        SVC(probability=True, kernel="rbf"),
        DecisionTreeClassifier(max_depth=5),
        RandomForestClassifier(n_estimators=50, max_depth=5),
    ]
    for m in models:
        m.fit(X[:split], y[:split])

    return models, scaler


def ml_predict(models, scaler, features: np.ndarray) -> float:
    """Ensemble average probability."""
    if models is None:
        return 0.5
    X = scaler.transform(features.reshape(1, -1))
    probs = [m.predict_proba(X)[0][1] for m in models]
    return np.mean(probs)


def run_bot(symbol: str = "XAUUSD"):
    if not mt5.initialize():
        log.error("MT5 init failed")
        return

    mt5.symbol_select(symbol, True)
    log.info(f"ICT Silver Bullet bot started: {symbol}")

    models, scaler = None, None

    try:
        while True:
            # Check NY session window
            import datetime
            import pytz
            ny_tz = pytz.timezone("America/New_York")
            now_ny = datetime.datetime.now(ny_tz)
            if not (SB_START <= now_ny.hour < SB_END):
                time.sleep(60)
                continue

            # Check no existing position
            positions = mt5.positions_get(symbol=symbol)
            if positions and any(p.magic == MAGIC for p in positions):
                time.sleep(30)
                continue

            # Multi-timeframe bias
            bias_score, bias_dir = get_mtf_bias(symbol)
            if bias_dir == "NEUTRAL":
                time.sleep(60)
                continue

            direction = 1 if bias_score > 0 else -1

            # Entry timeframe analysis (M15)
            df = get_candles(symbol, mt5.TIMEFRAME_M15, 200)
            if df is None or len(df) < 100:
                time.sleep(60)
                continue

            # Train ML ensemble periodically
            if models is None:
                h1 = get_candles(symbol, mt5.TIMEFRAME_H1, 500)
                if h1 is not None and len(h1) > 100:
                    models, scaler = train_ml_ensemble(h1)

            # Detect setup components
            sh, sl = detect_swing_points(df["high"].values, df["low"].values)
            has_sweep = detect_liquidity_sweep(df, sh, sl, bias_score)
            has_disp = detect_displacement(df)
            fvg = detect_fvg(df, direction)
            has_fvg = fvg is not None
            has_mss = detect_mss(df, direction)

            # OTE zone check
            in_ote = False
            if len(sh) > 0 and len(sl) > 0:
                sw_high = sh[-1][1]
                sw_low = sl[-1][1]
                ote_low, ote_high = calc_ote_zone(sw_low, sw_high, direction)
                price = df["close"].iloc[-1]
                in_ote = ote_low <= price <= ote_high

            # ML confirmation
            ml_conf = False
            if models and scaler:
                close = df["close"].values
                feat = np.array([
                    (close[-1] - close[-2]) / close[-2] if close[-2] != 0 else 0,
                    (df["high"].iloc[-1] - df["low"].iloc[-1]) / close[-1],
                    abs(close[-1] - df["open"].iloc[-1]) / close[-1],
                    pd.Series(close).rolling(8).mean().iloc[-1],
                    pd.Series(close).rolling(21).mean().iloc[-1],
                    pd.Series(close).rolling(50).mean().iloc[-1],
                    (df["high"] - df["low"]).rolling(14).mean().iloc[-1],
                ])
                prob = ml_predict(models, scaler, feat)
                ml_conf = (direction == 1 and prob > 0.65) or (direction == -1 and prob < 0.35)

            score = score_setup(bias_score, has_sweep, has_disp, has_fvg, has_mss, in_ote, ml_conf)
            log.info(f"Setup score: {score}/14 bias={bias_dir} sweep={has_sweep} disp={has_disp} fvg={has_fvg} mss={has_mss} ote={in_ote} ml={ml_conf}")

            if score < 6:
                time.sleep(60)
                continue

            # Execute trade
            atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
            tick = mt5.symbol_info_tick(symbol)
            sym = mt5.symbol_info(symbol)

            rr = 1.5 + (score - 6) * 0.25  # Higher score = better R:R
            rr = min(rr, 3.0)

            if direction == 1:
                price = tick.ask
                sl_dist = atr * 1.2
                sl = round(price - sl_dist, sym.digits)
                tp = round(price + sl_dist * rr, sym.digits)
                order_type = mt5.ORDER_TYPE_BUY
            else:
                price = tick.bid
                sl_dist = atr * 1.2
                sl = round(price + sl_dist, sym.digits)
                tp = round(price - sl_dist * rr, sym.digits)
                order_type = mt5.ORDER_TYPE_SELL

            balance = mt5.account_info().balance
            risk_money = balance * RISK_PCT / 100
            sl_money = (sl_dist / sym.trade_tick_size) * sym.trade_tick_value if sym.trade_tick_size > 0 else 1
            lot = risk_money / sl_money if sl_money > 0 else 0.01
            lot = max(sym.volume_min, min(lot, sym.volume_max))
            lot = round(lot / sym.volume_step) * sym.volume_step

            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": round(lot, 2),
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": MAGIC,
                "type_filling": mt5.ORDER_FILLING_IOC,
                "type_time": mt5.ORDER_TIME_GTC,
            })

            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"{'BUY' if direction == 1 else 'SELL'} score={score} @ {price} SL={sl} TP={tp} lot={lot:.2f} R:R={rr:.1f}")
            else:
                log.warning(f"Order failed: {result}")

            time.sleep(300)

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    run_bot("XAUUSD")
