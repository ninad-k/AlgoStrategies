"""
ML SuperTrend with K-Means Clustering — MT5 Trading Bot
Computes multiple SuperTrend variants across ATR factor range (1.0-5.0),
clusters them by performance using KMeans, trades the best cluster's signal.
Volume confirmation filter. ATR-based SL/TP with trailing stop.
Source: xPOURY4/ML-SuperTrend-MT5
"""

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from dataclasses import dataclass, field
from typing import Optional
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


@dataclass
class Config:
    symbol: str = "EURUSD"
    timeframe: int = mt5.TIMEFRAME_M30
    magic_number: int = 20260413
    risk_percent: float = 1.0
    # SuperTrend range
    atr_period: int = 10
    factor_start: float = 1.0
    factor_end: float = 5.0
    factor_step: float = 0.5
    # KMeans
    n_clusters: int = 3
    cluster_choice: str = "best"  # best, average, worst
    lookback: int = 100
    # Volume filter
    volume_ma_period: int = 20
    volume_multiplier: float = 1.0
    # SL/TP
    sl_multiplier: float = 2.0
    tp_multiplier: float = 3.0
    # Trailing
    trail_activation: float = 1.5
    trailing_sl_mult: float = 1.0


def calc_supertrend(df: pd.DataFrame, period: int, factor: float):
    """Calculate SuperTrend indicator. Returns direction series (+1/-1)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    atr = pd.Series(dtype=float, index=df.index)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    mid = (high + low) / 2
    upper = mid + factor * atr
    lower = mid - factor * atr

    direction = pd.Series(1, index=df.index)
    st_upper = upper.copy()
    st_lower = lower.copy()

    for i in range(1, len(df)):
        # Sticky bands
        if lower.iloc[i] > st_lower.iloc[i - 1] or close.iloc[i - 1] < st_lower.iloc[i - 1]:
            st_lower.iloc[i] = lower.iloc[i]
        else:
            st_lower.iloc[i] = st_lower.iloc[i - 1]

        if upper.iloc[i] < st_upper.iloc[i - 1] or close.iloc[i - 1] > st_upper.iloc[i - 1]:
            st_upper.iloc[i] = upper.iloc[i]
        else:
            st_upper.iloc[i] = st_upper.iloc[i - 1]

        # Direction flip
        prev_dir = direction.iloc[i - 1]
        if prev_dir == 1:
            direction.iloc[i] = -1 if close.iloc[i] < st_lower.iloc[i] else 1
        else:
            direction.iloc[i] = 1 if close.iloc[i] > st_upper.iloc[i] else -1

    return direction


def calc_performance_scores(df: pd.DataFrame, factors: list, cfg: Config):
    """Compute volatility-adjusted exponential performance score per factor."""
    returns = df["close"].pct_change()
    scores = {}
    for f in factors:
        direction = calc_supertrend(df, cfg.atr_period, f)
        # Position returns: direction[i-1] * return[i]
        strat_returns = direction.shift(1) * returns
        # Exponential weighted score over lookback
        score = strat_returns.tail(cfg.lookback).ewm(span=cfg.lookback).mean().iloc[-1]
        vol = strat_returns.tail(cfg.lookback).std()
        scores[f] = score / vol if vol > 0 else 0
    return scores


def select_optimal_factor(scores: dict, cfg: Config) -> float:
    """Use KMeans to cluster factors by performance, return avg factor from chosen cluster."""
    factors = np.array(list(scores.keys())).reshape(-1, 1)
    perf = np.array(list(scores.values())).reshape(-1, 1)

    km = KMeans(n_clusters=cfg.n_clusters, n_init=10, random_state=42)
    labels = km.fit_predict(perf)

    # Sort clusters by mean performance
    cluster_means = {}
    for c in range(cfg.n_clusters):
        mask = labels == c
        cluster_means[c] = perf[mask].mean()

    sorted_clusters = sorted(cluster_means.items(), key=lambda x: x[1])
    choice_map = {"worst": 0, "average": 1, "best": 2}
    idx = choice_map.get(cfg.cluster_choice, 2)
    idx = min(idx, len(sorted_clusters) - 1)
    chosen_cluster = sorted_clusters[idx][0]

    # Average factor in chosen cluster
    mask = labels == chosen_cluster
    return float(factors[mask].mean())


def calc_lot_size(cfg: Config, sl_distance: float) -> float:
    """Risk-based position sizing."""
    account = mt5.account_info()
    if not account or sl_distance <= 0:
        return 0.01

    risk_money = account.balance * cfg.risk_percent / 100
    symbol_info = mt5.symbol_info(cfg.symbol)
    if not symbol_info:
        return 0.01

    tick_value = symbol_info.trade_tick_value
    tick_size = symbol_info.trade_tick_size
    if tick_value <= 0 or tick_size <= 0:
        return 0.01

    sl_money = (sl_distance / tick_size) * tick_value
    lot = risk_money / sl_money if sl_money > 0 else 0.01
    lot = max(symbol_info.volume_min, min(lot, symbol_info.volume_max))
    lot = round(lot / symbol_info.volume_step) * symbol_info.volume_step
    return round(lot, 2)


def get_data(cfg: Config, bars: int = 200) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from MT5."""
    rates = mt5.copy_rates_from_pos(cfg.symbol, cfg.timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def check_volume_filter(df: pd.DataFrame, cfg: Config) -> bool:
    """Volume must exceed moving average threshold."""
    if "tick_volume" not in df.columns:
        return True
    vol = df["tick_volume"]
    vol_ma = vol.rolling(cfg.volume_ma_period).mean()
    return vol.iloc[-1] >= cfg.volume_multiplier * vol_ma.iloc[-1]


def run_bot(cfg: Config):
    """Main trading loop."""
    if not mt5.initialize():
        log.error("MT5 initialization failed")
        return

    if not mt5.symbol_select(cfg.symbol, True):
        log.error(f"Symbol {cfg.symbol} not available")
        return

    factors = np.arange(cfg.factor_start, cfg.factor_end + cfg.factor_step, cfg.factor_step).tolist()
    prev_direction = 0
    log.info(f"ML-SuperTrend bot started: {cfg.symbol} factors={factors}")

    try:
        while True:
            df = get_data(cfg)
            if df is None or len(df) < cfg.lookback + 50:
                time.sleep(60)
                continue

            # Calculate performance and select optimal factor via KMeans
            scores = calc_performance_scores(df, factors, cfg)
            optimal_factor = select_optimal_factor(scores, cfg)
            log.info(f"Optimal factor: {optimal_factor:.1f}")

            # Get signal from optimal SuperTrend
            direction = calc_supertrend(df, cfg.atr_period, optimal_factor)
            current_dir = int(direction.iloc[-2])  # Use completed bar

            # Volume filter
            if not check_volume_filter(df, cfg):
                time.sleep(60)
                continue

            # Direction flip = signal
            if current_dir != prev_direction and prev_direction != 0:
                # Close existing positions
                positions = mt5.positions_get(symbol=cfg.symbol)
                if positions:
                    for pos in positions:
                        if pos.magic == cfg.magic_number:
                            close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
                            price = mt5.symbol_info_tick(cfg.symbol).bid if pos.type == 0 else mt5.symbol_info_tick(cfg.symbol).ask
                            mt5.order_send({
                                "action": mt5.TRADE_ACTION_DEAL,
                                "symbol": cfg.symbol,
                                "volume": pos.volume,
                                "type": close_type,
                                "position": pos.ticket,
                                "price": price,
                                "deviation": 20,
                                "magic": cfg.magic_number,
                                "type_filling": mt5.ORDER_FILLING_IOC,
                                "type_time": mt5.ORDER_TIME_GTC,
                            })

                # ATR for SL/TP
                tr = pd.concat([
                    df["high"] - df["low"],
                    (df["high"] - df["close"].shift(1)).abs(),
                    (df["low"] - df["close"].shift(1)).abs()
                ], axis=1).max(axis=1)
                atr = tr.ewm(alpha=1.0 / cfg.atr_period, min_periods=cfg.atr_period, adjust=False).mean().iloc[-1]

                tick = mt5.symbol_info_tick(cfg.symbol)
                if current_dir == 1:
                    price = tick.ask
                    sl = round(price - cfg.sl_multiplier * atr, mt5.symbol_info(cfg.symbol).digits)
                    tp = round(price + cfg.tp_multiplier * atr, mt5.symbol_info(cfg.symbol).digits)
                    lot = calc_lot_size(cfg, cfg.sl_multiplier * atr)
                    order_type = mt5.ORDER_TYPE_BUY
                else:
                    price = tick.bid
                    sl = round(price + cfg.sl_multiplier * atr, mt5.symbol_info(cfg.symbol).digits)
                    tp = round(price - cfg.tp_multiplier * atr, mt5.symbol_info(cfg.symbol).digits)
                    lot = calc_lot_size(cfg, cfg.sl_multiplier * atr)
                    order_type = mt5.ORDER_TYPE_SELL

                result = mt5.order_send({
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": cfg.symbol,
                    "volume": lot,
                    "type": order_type,
                    "price": price,
                    "sl": sl,
                    "tp": tp,
                    "deviation": 20,
                    "magic": cfg.magic_number,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                    "type_time": mt5.ORDER_TIME_GTC,
                })
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    log.info(f"{'BUY' if current_dir == 1 else 'SELL'} @ {price} SL={sl} TP={tp} lot={lot} factor={optimal_factor:.1f}")
                else:
                    log.warning(f"Order failed: {result}")

            prev_direction = current_dir
            time.sleep(60)

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    cfg = Config(symbol="EURUSD", timeframe=mt5.TIMEFRAME_M30)
    run_bot(cfg)
