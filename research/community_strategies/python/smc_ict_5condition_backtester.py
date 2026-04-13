"""
SMC/ICT 5-Condition Checklist Backtester
1. HTF (1H) Bias via Break of Structure
2. LTF (15M) BOS alignment with HTF direction
3. Liquidity sweep (equal highs/lows swept)
4. 75% Fibonacci retracement entry zone
5. FVG confirmation near entry (optional)

Risk: fixed USD per trade. SL at 100% Fib, TP at 0% (or custom R:R).
Source: Edish1-glitch/mt5-smc-bot
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


@dataclass
class Trade:
    direction: int      # 1=long, -1=short
    entry: float
    sl: float
    tp: float
    lot_size: float
    entry_time: object  # datetime
    exit_time: object = None
    exit_price: float = 0
    pnl: float = 0
    result: str = ""    # win/loss

    def close(self, exit_price: float, exit_time, pip_size: float, pip_value: float):
        self.exit_price = exit_price
        self.exit_time = exit_time
        diff = (exit_price - self.entry) * self.direction
        self.pnl = (diff / pip_size) * pip_value * self.lot_size
        self.result = "win" if self.pnl > 0 else "loss"


@dataclass
class Config:
    symbol: str = "EURUSD"
    risk_usd: float = 500
    pip_size: float = 0.0001
    pip_value: float = 10.0   # USD per pip per lot
    swing_n: int = 3          # Fractal window for swings
    fvg_min_gap: float = 0.0002
    entry_buffer_pct: float = 0.75  # Fibonacci retracement level
    require_fvg: bool = False
    risk_reward: float = 2.0  # TP = SL * R:R
    max_daily_trades: int = 5
    liq_tolerance: float = 0.0005  # 0.05% for equal highs/lows
    commission_per_lot: float = 7.0


def detect_swings(highs: np.ndarray, lows: np.ndarray, n: int):
    """Fractal swing detection. Strict comparison."""
    sh, sl = [], []
    for i in range(n, len(highs) - n):
        is_sh = all(highs[i] > highs[i - j] for j in range(1, n + 1)) and \
                all(highs[i] > highs[i + j] for j in range(1, n + 1))
        is_sl = all(lows[i] < lows[i - j] for j in range(1, n + 1)) and \
                all(lows[i] < lows[i + j] for j in range(1, n + 1))
        if is_sh:
            sh.append((i, highs[i]))
        if is_sl:
            sl.append((i, lows[i]))
    return sh, sl


def detect_bos(closes: np.ndarray, swing_highs: list, swing_lows: list, bar_idx: int):
    """Detect BOS at bar_idx: close breaks previous swing."""
    last_sh = None
    last_sl = None

    for idx, level in swing_highs:
        if idx < bar_idx:
            last_sh = (idx, level)
    for idx, level in swing_lows:
        if idx < bar_idx:
            last_sl = (idx, level)

    if last_sh and closes[bar_idx] > last_sh[1]:
        return 1, last_sl, last_sh  # Bullish BOS
    if last_sl and closes[bar_idx] < last_sl[1]:
        return -1, last_sl, last_sh  # Bearish BOS
    return 0, None, None


def detect_fvg(highs: np.ndarray, lows: np.ndarray, bar_idx: int, direction: int,
               min_gap: float, lookback: int = 20) -> bool:
    """Check for FVG near bar_idx."""
    for i in range(max(1, bar_idx - lookback), bar_idx - 1):
        if direction == 1:
            gap = lows[i + 2] - highs[i]
            if gap > min_gap:
                return True
        else:
            gap = lows[i] - highs[i + 2]
            if gap > min_gap:
                return True
    return False


def detect_liquidity_sweep(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                           swing_highs: list, swing_lows: list,
                           bar_idx: int, direction: int, tolerance: float) -> bool:
    """Check if liquidity was swept before bar_idx."""
    # Equal lows sweep (bullish)
    if direction == 1:
        for i, lvl_i in swing_lows:
            if i >= bar_idx:
                continue
            for j, lvl_j in swing_lows:
                if j <= i or j >= bar_idx:
                    continue
                avg = (lvl_i + lvl_j) / 2
                if avg > 0 and abs(lvl_i - lvl_j) / avg <= tolerance:
                    level = min(lvl_i, lvl_j)
                    for k in range(j, bar_idx):
                        if lows[k] < level and closes[k] > level:
                            return True

    # Equal highs sweep (bearish)
    if direction == -1:
        for i, lvl_i in swing_highs:
            if i >= bar_idx:
                continue
            for j, lvl_j in swing_highs:
                if j <= i or j >= bar_idx:
                    continue
                avg = (lvl_i + lvl_j) / 2
                if avg > 0 and abs(lvl_i - lvl_j) / avg <= tolerance:
                    level = max(lvl_i, lvl_j)
                    for k in range(j, bar_idx):
                        if highs[k] > level and closes[k] < level:
                            return True
    return False


def run_backtest(df_h1: pd.DataFrame, df_m15: pd.DataFrame, cfg: Config) -> List[Trade]:
    """Walk-forward bar-by-bar backtester."""
    trades: List[Trade] = []

    h1_highs = df_h1["high"].values
    h1_lows = df_h1["low"].values
    h1_closes = df_h1["close"].values
    h1_sh, h1_sl = detect_swings(h1_highs, h1_lows, cfg.swing_n)

    m15_highs = df_m15["high"].values
    m15_lows = df_m15["low"].values
    m15_closes = df_m15["close"].values
    m15_sh, m15_sl = detect_swings(m15_highs, m15_lows, cfg.swing_n)

    open_trade: Optional[Trade] = None
    last_bos_bar = -1

    for i in range(50, len(df_m15)):
        # Check open trade SL/TP
        if open_trade is not None:
            high = m15_highs[i]
            low = m15_lows[i]
            if open_trade.direction == 1:
                if low <= open_trade.sl:
                    open_trade.close(open_trade.sl, df_m15["time"].iloc[i], cfg.pip_size, cfg.pip_value)
                    open_trade.pnl -= cfg.commission_per_lot * open_trade.lot_size
                    trades.append(open_trade)
                    open_trade = None
                elif high >= open_trade.tp:
                    open_trade.close(open_trade.tp, df_m15["time"].iloc[i], cfg.pip_size, cfg.pip_value)
                    open_trade.pnl -= cfg.commission_per_lot * open_trade.lot_size
                    trades.append(open_trade)
                    open_trade = None
            else:
                if high >= open_trade.sl:
                    open_trade.close(open_trade.sl, df_m15["time"].iloc[i], cfg.pip_size, cfg.pip_value)
                    open_trade.pnl -= cfg.commission_per_lot * open_trade.lot_size
                    trades.append(open_trade)
                    open_trade = None
                elif low <= open_trade.tp:
                    open_trade.close(open_trade.tp, df_m15["time"].iloc[i], cfg.pip_size, cfg.pip_value)
                    open_trade.pnl -= cfg.commission_per_lot * open_trade.lot_size
                    trades.append(open_trade)
                    open_trade = None
            continue

        # Condition 1: HTF bias (last H1 BOS before current M15 bar)
        m15_time = df_m15["time"].iloc[i]
        h1_bias = 0
        for hi in range(len(df_h1) - 1, 0, -1):
            if df_h1["time"].iloc[hi] <= m15_time:
                bos_dir, _, _ = detect_bos(h1_closes, h1_sh, h1_sl, hi)
                if bos_dir != 0:
                    h1_bias = bos_dir
                break
        if h1_bias == 0:
            continue

        # Condition 2: LTF BOS alignment
        m15_bos, m15_anchor_low, m15_anchor_high = detect_bos(m15_closes, m15_sh, m15_sl, i)
        if m15_bos != h1_bias:
            continue
        if i == last_bos_bar:  # One trade per BOS
            continue

        # Condition 3: Liquidity swept
        swept = detect_liquidity_sweep(m15_highs, m15_lows, m15_closes,
                                       m15_sh, m15_sl, i, h1_bias, cfg.liq_tolerance)
        if not swept:
            continue

        # Condition 4: Fibonacci 75% entry zone
        if m15_anchor_low is None or m15_anchor_high is None:
            continue
        swing_low = m15_anchor_low[1]
        swing_high = m15_anchor_high[1]
        span = swing_high - swing_low
        if span < cfg.fvg_min_gap:
            continue

        if h1_bias == 1:
            entry_level = swing_high - cfg.entry_buffer_pct * span
            sl_level = swing_low
            tp_level = swing_high + (entry_level - swing_low) * cfg.risk_reward
        else:
            entry_level = swing_low + cfg.entry_buffer_pct * span
            sl_level = swing_high
            tp_level = swing_low - (swing_high - entry_level) * cfg.risk_reward

        # Check price is near entry zone
        price = m15_closes[i]
        entry_dist = abs(price - entry_level)
        if entry_dist > span * 0.1:  # Within 10% of entry zone
            continue

        # Condition 5: FVG confirmation (optional)
        if cfg.require_fvg:
            has_fvg = detect_fvg(m15_highs, m15_lows, i, h1_bias, cfg.fvg_min_gap)
            if not has_fvg:
                continue

        # Calculate position size
        pips_at_risk = abs(entry_level - sl_level) / cfg.pip_size
        if pips_at_risk <= 0:
            continue
        lot_size = cfg.risk_usd / (pips_at_risk * cfg.pip_value)
        lot_size = round(lot_size, 2)

        open_trade = Trade(
            direction=h1_bias,
            entry=entry_level,
            sl=sl_level,
            tp=tp_level,
            lot_size=lot_size,
            entry_time=df_m15["time"].iloc[i],
        )
        last_bos_bar = i

    return trades


def print_results(trades: List[Trade]):
    """Print backtest statistics."""
    if not trades:
        log.info("No trades taken.")
        return

    wins = [t for t in trades if t.result == "win"]
    losses = [t for t in trades if t.result == "loss"]
    total_pnl = sum(t.pnl for t in trades)
    win_rate = len(wins) / len(trades) * 100

    avg_win = np.mean([t.pnl for t in wins]) if wins else 0
    avg_loss = np.mean([abs(t.pnl) for t in losses]) if losses else 0
    profit_factor = sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses)) if losses else float("inf")

    # Max drawdown
    equity = [0]
    for t in trades:
        equity.append(equity[-1] + t.pnl)
    peak = equity[0]
    max_dd = 0
    for e in equity:
        peak = max(peak, e)
        dd = peak - e
        max_dd = max(max_dd, dd)

    log.info(f"=== Backtest Results ===")
    log.info(f"Total trades: {len(trades)} | Wins: {len(wins)} | Losses: {len(losses)}")
    log.info(f"Win rate: {win_rate:.1f}%")
    log.info(f"Net P&L: ${total_pnl:.2f}")
    log.info(f"Avg win: ${avg_win:.2f} | Avg loss: ${avg_loss:.2f}")
    log.info(f"Profit factor: {profit_factor:.2f}")
    log.info(f"Max drawdown: ${max_dd:.2f}")


if __name__ == "__main__":
    # Example usage with CSV data
    # df_h1 = pd.read_csv("EURUSD_H1.csv", parse_dates=["time"])
    # df_m15 = pd.read_csv("EURUSD_M15.csv", parse_dates=["time"])
    # trades = run_backtest(df_h1, df_m15, Config())
    # print_results(trades)
    log.info("SMC/ICT 5-Condition Backtester ready. Provide H1 and M15 DataFrames to run_backtest().")
