# MT5 walk-forward backtest for ML SuperTrend (cluster K-Means or trained ML signals).
# Requires MetaTrader 5 running with a logged-in account; uses historical rates only.

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from core.ml_signal import MLSignalGenerator
from core.supertrend_bot import Config, SuperTrendBot

logger = logging.getLogger(__name__)

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}


def timeframe_from_string(name: str) -> int:
    key = (name or "M30").upper()
    if key not in TIMEFRAME_MAP:
        raise ValueError(f"Unknown timeframe {name!r}; use one of {list(TIMEFRAME_MAP)}")
    return TIMEFRAME_MAP[key]


@dataclass
class BacktestStats:
    symbol: str
    timeframe: str
    mode: str
    initial_balance: float
    final_balance: float
    total_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    bars: int
    trades: List[Dict[str, Any]] = field(default_factory=list)


def _profit_in_account_currency(
    direction: int,
    symbol: str,
    volume: float,
    price_open: float,
    price_close: float,
) -> float:
    """Hypothetical P/L for closing a position at ``price_close`` (account currency)."""
    if volume <= 0:
        return 0.0
    if direction == 1:
        p = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, symbol, volume, price_open, price_close)
    else:
        p = mt5.order_calc_profit(mt5.ORDER_TYPE_SELL, symbol, volume, price_open, price_close)
    if p is not None and not np.isnan(p):
        return float(p)
    info = mt5.symbol_info(symbol)
    if info is None:
        return 0.0
    tick_size = info.trade_tick_size or info.point
    tick_value = info.trade_tick_value
    if tick_size <= 0 or tick_value <= 0:
        return 0.0
    delta = (price_close - price_open) if direction == 1 else (price_open - price_close)
    ticks = delta / tick_size
    return ticks * tick_value * volume


def _exit_on_bar(
    direction: int,
    sl: float,
    tp: float,
    open_: float,
    high: float,
    low: float,
    conservative_sl_first: bool = True,
) -> Tuple[Optional[float], Optional[str]]:
    """Return (exit_price, reason) if SL/TP touched on this bar; else (None, None).

    If both levels trade through in one bar, ``conservative_sl_first`` assumes stop
    hits first for longs (bearish) and shorts (bullish), which is pessimistic for P/L.
    """
    if direction == 1:
        hit_sl = low <= sl
        hit_tp = high >= tp
        if hit_sl and hit_tp:
            if conservative_sl_first:
                return sl, "sl"
            return tp, "tp"
        if hit_sl:
            return sl, "sl"
        if hit_tp:
            return tp, "tp"
    else:
        hit_sl = high >= sl
        hit_tp = low <= tp
        if hit_sl and hit_tp:
            if conservative_sl_first:
                return sl, "sl"
            return tp, "tp"
        if hit_sl:
            return sl, "sl"
        if hit_tp:
            return tp, "tp"
    return None, None


def _fixed_volume(symbol: str, lot: Optional[float]) -> float:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Unknown symbol {symbol}")
    if not info.visible:
        mt5.symbol_select(symbol, True)
    v = float(lot) if lot is not None else float(info.volume_min)
    step = info.volume_step or 0.01
    v = max(info.volume_min, min(v, info.volume_max))
    steps = round((v - info.volume_min) / step)
    return round(info.volume_min + steps * step, 8)


def fetch_rates_range(
    symbol: str,
    timeframe: int,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Load OHLCV from MT5 as a DataFrame with a ``time`` column (UTC)."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    rates = mt5.copy_rates_range(symbol, timeframe, start, end)
    if rates is None or len(rates) == 0:
        raise RuntimeError(
            f"No rates for {symbol}: {mt5.last_error()} — check symbol name and history availability."
        )
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df


def run_cluster_backtest(
    symbol: str,
    timeframe: int,
    raw: pd.DataFrame,
    config: Config,
    initial_balance: float = 10_000.0,
    lot: Optional[float] = None,
    warmup: int = 200,
) -> BacktestStats:
    """Walk-forward backtest using ``SuperTrendBot.evaluate_signal`` (K-Means cluster path)."""
    bot = SuperTrendBot(config)
    vol = _fixed_volume(symbol, lot)
    n = len(raw)
    position: Optional[Dict[str, Any]] = None
    balance = initial_balance
    trades: List[Dict[str, Any]] = []
    equity: List[float] = []

    tf_name = next((k for k, v in TIMEFRAME_MAP.items() if v == timeframe), "M30")

    for i in range(warmup, n):
        row = raw.iloc[i]
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])

        if position is not None:
            ex, reason = _exit_on_bar(
                position["direction"], position["sl"], position["tp"], o, h, l, conservative_sl_first=True
            )
            if ex is not None:
                pnl = _profit_in_account_currency(
                    position["direction"], symbol, vol, position["entry"], ex
                )
                balance += pnl
                trades.append(
                    {
                        "entry_time": position["entry_time"],
                        "exit_time": row["time"],
                        "direction": position["direction"],
                        "entry": position["entry"],
                        "exit": ex,
                        "pnl": pnl,
                        "reason": reason,
                    }
                )
                position = None

        if position is None:
            window = raw.iloc[: i + 1].copy()
            df_prep = bot.prepare_dataframe(window)
            sig = bot.evaluate_signal(df_prep)
            d = int(sig.get("direction", 0))
            if d != 0:
                position = {
                    "direction": d,
                    "entry": c,
                    "sl": float(sig["sl"]),
                    "tp": float(sig["tp"]),
                    "entry_time": row["time"],
                    "entry_idx": i,
                }

        equity.append(balance)

    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    gross_win = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    wr = (100.0 * wins / len(trades)) if trades else 0.0

    max_dd = _max_drawdown_pct(equity, initial_balance)
    sharpe = _sharpe_ratio_from_equity(equity)

    return BacktestStats(
        symbol=symbol,
        timeframe=tf_name,
        mode="cluster",
        initial_balance=initial_balance,
        final_balance=balance,
        total_trades=len(trades),
        wins=wins,
        losses=losses,
        win_rate_pct=wr,
        profit_factor=float(pf) if np.isfinite(pf) else 0.0,
        max_drawdown_pct=max_dd,
        sharpe_ratio=sharpe,
        bars=n,
        trades=trades,
    )


def run_ml_backtest(
    symbol: str,
    timeframe: int,
    tf_name: str,
    raw: pd.DataFrame,
    config: Config,
    model_dir: str = "models",
    initial_balance: float = 10_000.0,
    lot: Optional[float] = None,
    warmup: int = 200,
    min_confidence: float = 0.0,
) -> BacktestStats:
    """Backtest using ``MLSignalGenerator`` (trained models). Higher-TF context omitted unless added later."""
    gen = MLSignalGenerator(symbol, model_dir=model_dir)
    if not gen.load_model(tf_name):
        raise FileNotFoundError(
            f"No trained model for {symbol} {tf_name} under {model_dir}. Run train.py first."
        )
    bot = SuperTrendBot(config)
    vol = _fixed_volume(symbol, lot)
    n = len(raw)
    position: Optional[Dict[str, Any]] = None
    balance = initial_balance
    trades: List[Dict[str, Any]] = []
    equity: List[float] = []

    for i in range(warmup, n):
        row = raw.iloc[i]
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])

        if position is not None:
            ex, reason = _exit_on_bar(
                position["direction"], position["sl"], position["tp"], o, h, l, conservative_sl_first=True
            )
            if ex is not None:
                pnl = _profit_in_account_currency(
                    position["direction"], symbol, vol, position["entry"], ex
                )
                balance += pnl
                trades.append(
                    {
                        "entry_time": position["entry_time"],
                        "exit_time": row["time"],
                        "direction": position["direction"],
                        "entry": position["entry"],
                        "exit": ex,
                        "pnl": pnl,
                        "reason": reason,
                    }
                )
                position = None

        if position is None:
            window = raw.iloc[: i + 1].copy()
            if "time" not in window.columns:
                window = window.reset_index()
            res = gen.predict(tf_name, window, higher_tf_data=None)
            sig = int(res.get("signal", 0))
            conf = float(res.get("confidence", 0.0))
            if sig != 0 and conf >= min_confidence:
                window_prep = bot.prepare_dataframe(window)
                atr = float(window_prep["atr"].iloc[-1])
                if not np.isnan(atr) and atr > 0:
                    if sig == 1:
                        sl = c - atr * config.sl_multiplier
                        tp = c + atr * config.tp_multiplier
                        direction = 1
                    else:
                        sl = c + atr * config.sl_multiplier
                        tp = c - atr * config.tp_multiplier
                        direction = -1
                    position = {
                        "direction": direction,
                        "entry": c,
                        "sl": sl,
                        "tp": tp,
                        "entry_time": row["time"],
                        "entry_idx": i,
                    }

        equity.append(balance)

    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    gross_win = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    wr = (100.0 * wins / len(trades)) if trades else 0.0

    return BacktestStats(
        symbol=symbol,
        timeframe=tf_name,
        mode="ml",
        initial_balance=initial_balance,
        final_balance=balance,
        total_trades=len(trades),
        wins=wins,
        losses=losses,
        win_rate_pct=wr,
        profit_factor=float(pf) if np.isfinite(pf) else 0.0,
        max_drawdown_pct=_max_drawdown_pct(equity, initial_balance),
        sharpe_ratio=_sharpe_ratio_from_equity(equity),
        bars=n,
        trades=trades,
    )


def _max_drawdown_pct(equity: List[float], initial: float) -> float:
    if not equity:
        return 0.0
    peak = initial
    max_dd = 0.0
    for x in equity:
        if x > peak:
            peak = x
        dd = (peak - x) / peak * 100.0 if peak else 0.0
        if dd > max_dd:
            max_dd = dd
    return float(max_dd)


def _sharpe_ratio_from_equity(equity: List[float], risk_free: float = 0.02) -> float:
    if len(equity) < 3:
        return 0.0
    s = pd.Series(equity).pct_change().dropna()
    if s.std() == 0 or s.empty:
        return 0.0
    excess = s - risk_free / 252
    return float(np.sqrt(252) * excess.mean() / s.std())


def ensure_mt5(terminal_path: str | None = None) -> None:
    """Attach to a running MT5 terminal. Set env ``MT5_TERMINAL_PATH`` if auto-detect fails."""
    path = terminal_path or os.environ.get("MT5_TERMINAL_PATH") or None
    kwargs = {"path": path} if path else {}
    if not mt5.initialize(**kwargs):
        raise RuntimeError(
            "MetaTrader5.initialize() failed: start MetaTrader 5, allow Python API / Algo Trading, "
            "or set MT5_TERMINAL_PATH to terminal64.exe."
        )
