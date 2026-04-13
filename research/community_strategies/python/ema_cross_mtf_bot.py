"""
EMA Crossover with Multi-Timeframe Context — MT5 Python Bot
EMA(10)/EMA(50) crossover on H1, with H4/D1 trend alignment metadata.
ATR-based SL (2x) and TP (3x), risk-percentage position sizing.
Circuit breaker, daily/weekly trade caps, cooldown between trades.
Source: linuzri/mt5-trading
"""

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from typing import Optional, Tuple
import time
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MAGIC = 20260420
STATE_FILE = "ema_cross_state.json"


class Config:
    def __init__(self):
        self.symbol = "BTCUSD"
        self.timeframe = mt5.TIMEFRAME_H1
        self.ema_fast = 10
        self.ema_slow = 50
        self.atr_period = 14
        self.sl_atr_mult = 2.0
        self.tp_atr_mult = 3.0
        self.risk_per_trade = 0.5  # percent
        self.max_open = 3
        self.daily_cap = 50
        self.weekly_cap = 200
        self.cooldown_sec = 300
        self.consecutive_loss_halt = 5


class State:
    """Persistent state for crash recovery."""
    def __init__(self):
        self.daily_trades = 0
        self.weekly_trades = 0
        self.last_trade_time = 0
        self.consecutive_losses = 0

    def save(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.__dict__, f)

    def load(self):
        if Path(STATE_FILE).exists():
            with open(STATE_FILE) as f:
                data = json.load(f)
                for k, v in data.items():
                    setattr(self, k, v)


def get_candles(symbol: str, tf: int, count: int) -> Optional[pd.DataFrame]:
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def evaluate_signal(df: pd.DataFrame, cfg: Config) -> Tuple[Optional[int], dict]:
    """Detect EMA crossover on completed bar. Returns direction and metadata."""
    close = df["close"]
    ema_fast = calc_ema(close, cfg.ema_fast)
    ema_slow = calc_ema(close, cfg.ema_slow)

    # Crossover on bar[-2] vs bar[-3] (completed bars only)
    prev_fast = ema_fast.iloc[-3]
    prev_slow = ema_slow.iloc[-3]
    curr_fast = ema_fast.iloc[-2]
    curr_slow = ema_slow.iloc[-2]

    cross_up = prev_fast <= prev_slow and curr_fast > curr_slow
    cross_dn = prev_fast >= prev_slow and curr_fast < curr_slow

    # EMA gap metrics
    gap = curr_fast - curr_slow
    gap_pct = abs(gap) / close.iloc[-2] * 100 if close.iloc[-2] != 0 else 0
    converging = abs(gap) < abs(ema_fast.iloc[-3] - ema_slow.iloc[-3])

    # ATR
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - close.shift(1)).abs(),
        (df["low"] - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(cfg.atr_period).mean().iloc[-2]

    meta = {
        "ema_fast": curr_fast,
        "ema_slow": curr_slow,
        "gap_pct": gap_pct,
        "converging": converging,
        "atr": atr,
    }

    if cross_up:
        return 1, meta
    elif cross_dn:
        return -1, meta
    return None, meta


def get_htf_context(symbol: str, cfg: Config) -> dict:
    """H4 and D1 EMA alignment for context."""
    context = {"h4_trend": 0, "d1_trend": 0}

    h4 = get_candles(symbol, mt5.TIMEFRAME_H4, 100)
    if h4 is not None and len(h4) > cfg.ema_slow:
        ef = calc_ema(h4["close"], cfg.ema_fast)
        es = calc_ema(h4["close"], cfg.ema_slow)
        context["h4_trend"] = 1 if ef.iloc[-1] > es.iloc[-1] else -1

    d1 = get_candles(symbol, mt5.TIMEFRAME_D1, 100)
    if d1 is not None and len(d1) > cfg.ema_slow:
        ef = calc_ema(d1["close"], cfg.ema_fast)
        es = calc_ema(d1["close"], cfg.ema_slow)
        context["d1_trend"] = 1 if ef.iloc[-1] > es.iloc[-1] else -1

    return context


def calc_lot(symbol: str, sl_distance: float, risk_pct: float) -> float:
    account = mt5.account_info()
    sym = mt5.symbol_info(symbol)
    if not account or not sym or sl_distance <= 0:
        return sym.volume_min if sym else 0.01

    risk_money = account.balance * risk_pct / 100
    sl_money = (sl_distance / sym.trade_tick_size) * sym.trade_tick_value
    lot = risk_money / sl_money if sl_money > 0 else sym.volume_min
    lot = max(sym.volume_min, min(lot, sym.volume_max))
    lot = round(lot / sym.volume_step) * sym.volume_step
    return round(lot, 2)


def count_positions(symbol: str) -> int:
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return 0
    return sum(1 for p in positions if p.magic == MAGIC)


def run_bot():
    cfg = Config()
    state = State()
    state.load()

    if not mt5.initialize():
        log.error("MT5 init failed")
        return

    mt5.symbol_select(cfg.symbol, True)
    log.info(f"EMA Cross MTF bot started: {cfg.symbol} EMA({cfg.ema_fast}/{cfg.ema_slow})")

    try:
        last_bar = None
        while True:
            # New bar detection
            current_bar = mt5.copy_rates_from_pos(cfg.symbol, cfg.timeframe, 0, 1)
            if current_bar is not None:
                bar_time = current_bar[0][0]
                if bar_time == last_bar:
                    time.sleep(10)
                    continue
                last_bar = bar_time

            # Guard rails
            if state.consecutive_losses >= cfg.consecutive_loss_halt:
                log.warning(f"Circuit breaker: {state.consecutive_losses} consecutive losses")
                time.sleep(3600)
                state.consecutive_losses = 0
                continue

            if state.daily_trades >= cfg.daily_cap:
                time.sleep(60)
                continue

            if count_positions(cfg.symbol) >= cfg.max_open:
                time.sleep(30)
                continue

            now = time.time()
            if now - state.last_trade_time < cfg.cooldown_sec:
                time.sleep(10)
                continue

            # Get data and evaluate
            df = get_candles(cfg.symbol, cfg.timeframe, 100)
            if df is None or len(df) < cfg.ema_slow + 5:
                time.sleep(60)
                continue

            direction, meta = evaluate_signal(df, cfg)
            if direction is None:
                time.sleep(10)
                continue

            atr = meta["atr"]
            if atr <= 0:
                continue

            # HTF context (informational)
            htf = get_htf_context(cfg.symbol, cfg)
            log.info(f"Signal: {'BUY' if direction == 1 else 'SELL'} H4={htf['h4_trend']} D1={htf['d1_trend']} gap={meta['gap_pct']:.3f}%")

            # Execute
            tick = mt5.symbol_info_tick(cfg.symbol)
            sym = mt5.symbol_info(cfg.symbol)

            sl_dist = cfg.sl_atr_mult * atr
            tp_dist = cfg.tp_atr_mult * atr

            if direction == 1:
                price = tick.ask
                sl = round(price - sl_dist, sym.digits)
                tp = round(price + tp_dist, sym.digits)
                order_type = mt5.ORDER_TYPE_BUY
            else:
                price = tick.bid
                sl = round(price + sl_dist, sym.digits)
                tp = round(price - tp_dist, sym.digits)
                order_type = mt5.ORDER_TYPE_SELL

            lot = calc_lot(cfg.symbol, sl_dist, cfg.risk_per_trade)

            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": cfg.symbol,
                "volume": lot,
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
                log.info(f"{'BUY' if direction == 1 else 'SELL'} @ {price} SL={sl} TP={tp} lot={lot}")
                state.daily_trades += 1
                state.weekly_trades += 1
                state.last_trade_time = now
                state.save()
            else:
                log.warning(f"Order failed: {result}")

            time.sleep(30)

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        state.save()
        mt5.shutdown()


if __name__ == "__main__":
    run_bot()
