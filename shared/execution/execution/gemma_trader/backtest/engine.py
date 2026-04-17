"""
backtest/engine.py — deterministic bar-replay engine for v1 filter/threshold tuning.

The engine applies a fixed multi-confluence entry rule modulated by the filters
and thresholds in strategy_rules.yaml. Entries, exits, and position sizing are
deterministic — only the rules file changes between runs. This is the
falsifiable surface that proposer.py / validator.py operate on.

Entry rule (long):
  trend ∈ {BULLISH, STRONG_BULLISH}
  AND ichimoku_signal ∈ {BULLISH, STRONG_BULLISH}
  AND rsi < rsi_overbought
  AND adx >= min_adx
  AND vol_ratio >= min_vol_ratio
  AND (required_structure is None OR structure == required_structure)
  AND (block_when_bb_width_below is None OR bb_width >= block_when_bb_width_below)

Entry rule (short): mirror of above with bearish flavors and rsi > rsi_oversold.

Exit: SL at entry ± atr * sl_atr; TP at entry ± atr * tp_atr. Within one bar,
if both levels are inside [low, high], SL is assumed hit first (conservative).

Cooldown: after any exit, wait cooldown_min bars before re-entering the symbol.

Sizing: 1 unit per trade (R-based metrics are position-size independent).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd

# Local imports — we reuse the live-trader feature pipeline so IS/live parity holds.
from local_trader import calculate_indicators


BULLISH_SET = {"BULLISH", "STRONG_BULLISH"}
BEARISH_SET = {"BEARISH", "STRONG_BEARISH"}


@dataclass
class Trade:
    symbol: str
    side: str           # "LONG" or "SHORT"
    entry_idx: int
    entry_price: float
    exit_idx: int
    exit_price: float
    sl: float
    tp: float
    r_multiple: float   # (exit - entry) / (entry - sl) for LONG, mirrored for SHORT
    outcome: str        # "TP" | "SL" | "EOD"


def _passes_long(ind: dict, filters: dict, thresholds: dict) -> bool:
    if ind.get("trend") not in BULLISH_SET:
        return False
    if ind.get("ichimoku_signal") not in BULLISH_SET:
        return False
    if ind.get("rsi", 50) >= thresholds.get("rsi_overbought", 70):
        return False
    if ind.get("adx", 0) < filters.get("min_adx", 0):
        return False
    if ind.get("vol_ratio", 0) < filters.get("min_vol_ratio", 0):
        return False
    required = filters.get("required_structure")
    if required and ind.get("structure") != required:
        return False
    bb_floor = filters.get("block_when_bb_width_below")
    if bb_floor is not None and ind.get("bb_width", 0) < bb_floor:
        return False
    return True


def _passes_short(ind: dict, filters: dict, thresholds: dict) -> bool:
    if ind.get("trend") not in BEARISH_SET:
        return False
    if ind.get("ichimoku_signal") not in BEARISH_SET:
        return False
    if ind.get("rsi", 50) <= thresholds.get("rsi_oversold", 30):
        return False
    if ind.get("adx", 0) < filters.get("min_adx", 0):
        return False
    if ind.get("vol_ratio", 0) < filters.get("min_vol_ratio", 0):
        return False
    required = filters.get("required_structure")
    if required and ind.get("structure") != required:
        return False
    bb_floor = filters.get("block_when_bb_width_below")
    if bb_floor is not None and ind.get("bb_width", 0) < bb_floor:
        return False
    return True


def _simulate_exit(side: str, entry_price: float, sl: float, tp: float,
                   bars: pd.DataFrame, entry_idx: int) -> Tuple[int, float, str]:
    """
    Walk bars forward from entry_idx+1. Return (exit_idx, exit_price, outcome).
    On the same bar, if both SL and TP are in [low, high], SL wins (conservative).
    """
    for j in range(entry_idx + 1, len(bars)):
        hi = float(bars["high"].iloc[j])
        lo = float(bars["low"].iloc[j])
        if side == "LONG":
            sl_hit = lo <= sl
            tp_hit = hi >= tp
            if sl_hit and tp_hit:
                return j, sl, "SL"
            if sl_hit:
                return j, sl, "SL"
            if tp_hit:
                return j, tp, "TP"
        else:  # SHORT
            sl_hit = hi >= sl
            tp_hit = lo <= tp
            if sl_hit and tp_hit:
                return j, sl, "SL"
            if sl_hit:
                return j, sl, "SL"
            if tp_hit:
                return j, tp, "TP"
    # Never hit either — close at final bar.
    return len(bars) - 1, float(bars["close"].iloc[-1]), "EOD"


def run_backtest(df: pd.DataFrame, symbol: str, rules: dict,
                 warmup_bars: int = 200) -> dict:
    """
    Replay bars through the deterministic engine and return a metrics dict plus
    the full trade list. `rules` is the per-symbol block from strategy_rules.yaml:
        {"filters": {...}, "thresholds": {...}}
    """
    if df is None or len(df) < warmup_bars + 50:
        return _empty_result()

    filters = rules.get("filters", {}) or {}
    thresholds = rules.get("thresholds", {}) or {}
    sl_atr = float(thresholds.get("sl_atr", 1.0))
    tp_atr = float(thresholds.get("tp_atr", 1.5))
    cooldown = int(thresholds.get("cooldown_min", 3))

    trades: List[Trade] = []
    cooldown_until = 0
    in_position = False

    # We need indicator snapshots at each step. Rolling-recompute every bar is
    # expensive; instead, compute once over a rolling slice [:i+1] at each step.
    # For 1-min BTCUSD at ~60 days (~86k bars) this is slow but still tractable
    # (~2-5 min per symbol). If this becomes the bottleneck, cache the common
    # indicator columns and only recompute the enriched features block.
    for i in range(warmup_bars, len(df) - 1):
        if in_position:
            continue  # exit logic is applied inline below once a trade opens
        if i < cooldown_until:
            continue

        window = df.iloc[: i + 1]
        ind = calculate_indicators(window, symbol)
        if not ind:
            continue

        atr = float(ind.get("atr", 0) or 0)
        if atr <= 0:
            continue
        entry_price = float(ind.get("close", 0) or 0)
        if entry_price <= 0:
            continue

        side = None
        if _passes_long(ind, filters, thresholds):
            side = "LONG"
        elif _passes_short(ind, filters, thresholds):
            side = "SHORT"
        if side is None:
            continue

        if side == "LONG":
            sl = entry_price - atr * sl_atr
            tp = entry_price + atr * tp_atr
        else:
            sl = entry_price + atr * sl_atr
            tp = entry_price - atr * tp_atr

        in_position = True
        exit_idx, exit_price, outcome = _simulate_exit(side, entry_price, sl, tp, df, i)
        risk = abs(entry_price - sl) or 1e-9
        reward = (exit_price - entry_price) if side == "LONG" else (entry_price - exit_price)
        r_mult = reward / risk

        trades.append(Trade(
            symbol=symbol, side=side,
            entry_idx=i, entry_price=entry_price,
            exit_idx=exit_idx, exit_price=exit_price,
            sl=sl, tp=tp, r_multiple=r_mult, outcome=outcome,
        ))

        in_position = False
        cooldown_until = exit_idx + cooldown

    return _metrics(trades)


def _empty_result() -> dict:
    return {
        "trades": 0,
        "win_rate": 0.0,
        "expectancy_r": 0.0,
        "profit_factor": 0.0,
        "max_dd_r": 0.0,
        "sharpe": 0.0,
        "trade_log": [],
    }


def _metrics(trades: List[Trade]) -> dict:
    if not trades:
        return _empty_result()

    r_values = np.array([t.r_multiple for t in trades], dtype=float)
    wins = r_values[r_values > 0]
    losses = r_values[r_values <= 0]

    win_rate = float(len(wins) / len(r_values))
    expectancy_r = float(r_values.mean())
    profit_factor = float(wins.sum() / abs(losses.sum())) if losses.size and losses.sum() < 0 else float("inf") if wins.size else 0.0

    # Max drawdown in R-multiples on cumulative equity curve.
    equity = np.cumsum(r_values)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd_r = float(dd.max()) if len(dd) else 0.0

    # Sharpe on per-trade R (not annualized — useful as a relative signal only).
    sharpe = float(r_values.mean() / r_values.std()) if r_values.std() > 0 else 0.0

    trade_log = [
        {
            "symbol": t.symbol,
            "side": t.side,
            "entry_idx": t.entry_idx,
            "entry_price": round(t.entry_price, 4),
            "exit_idx": t.exit_idx,
            "exit_price": round(t.exit_price, 4),
            "sl": round(t.sl, 4),
            "tp": round(t.tp, 4),
            "r_multiple": round(t.r_multiple, 4),
            "outcome": t.outcome,
        }
        for t in trades
    ]

    return {
        "trades": len(trades),
        "win_rate": round(win_rate, 4),
        "expectancy_r": round(expectancy_r, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else None,
        "max_dd_r": round(max_dd_r, 4),
        "sharpe": round(sharpe, 4),
        "trade_log": trade_log,
    }
