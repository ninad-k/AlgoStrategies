"""
ReySentinel — Risk Manager
====================================
Validates trades, tracks outcomes, manages cooldowns,
and dynamically adjusts confidence thresholds.
Adapted from execution/gemma_trader/risk_manager.py.
"""

import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, config: dict):
        self.config = config
        self.trading_cfg = config["trading"]
        self.risk_cfg = config["risk_management"]
        self.adaptive_cfg = config.get("adaptive", {})
        self.daily_pnl = 0.0
        self.open_trades = []
        self.trade_date = date.today()

        self.last_trade_time = {}
        self.symbol_streaks = {}
        self.cooled_down_symbols = {}

        self.original_threshold = self.trading_cfg["confidence_threshold"]
        self.current_threshold = self.original_threshold

        log_cfg = config.get("logging", {})
        self.trade_log_path = Path(log_cfg.get("trade_log", "logs/trades.json"))
        self.outcome_log_path = Path(log_cfg.get("outcome_log", "logs/trade_outcomes.json"))
        self.param_adj_path = Path(log_cfg.get("parameter_adjustments", "logs/parameter_adjustments.json"))
        self.trade_log_path.parent.mkdir(parents=True, exist_ok=True)

    def can_trade(self, decision: dict, market_data: dict) -> tuple[bool, str]:
        if date.today() != self.trade_date:
            self.daily_pnl = 0.0
            self.trade_date = date.today()

        symbol = decision.get("symbol", "UNKNOWN")

        if symbol not in self.trading_cfg["allowed_symbols"]:
            return False, f"{symbol} not in allowed symbols"
        if decision["confidence"] < self.current_threshold:
            return False, f"Confidence {decision['confidence']:.2f} < threshold {self.current_threshold:.2f}"
        if len(self.open_trades) >= self.trading_cfg["max_open_trades"]:
            return False, f"Max open trades ({self.trading_cfg['max_open_trades']})"
        if any(t["symbol"] == symbol for t in self.open_trades):
            return False, f"Already in trade for {symbol}"
        if self.daily_pnl <= -self.risk_cfg["max_daily_loss_pct"]:
            return False, f"Daily loss limit: {self.daily_pnl:.2f}%"

        cooldown_min = self.trading_cfg.get("cooldown_minutes", 5)
        last_time = self.last_trade_time.get(symbol)
        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds() / 60
            if elapsed < cooldown_min:
                return False, f"Cooldown: {cooldown_min - elapsed:.1f}min remaining"

        if symbol in self.cooled_down_symbols:
            if datetime.now() < self.cooled_down_symbols[symbol]:
                remaining = (self.cooled_down_symbols[symbol] - datetime.now()).total_seconds() / 60
                return False, f"Streak cooldown: {remaining:.0f}min"
            else:
                del self.cooled_down_symbols[symbol]

        return True, "approved"

    def calculate_position_size(self, account_balance: float, atr: float,
                                sl_atr_mult: float, symbol: str = "") -> dict:
        risk_pct = self.trading_cfg["max_position_size_pct"] / 100
        risk_amount = account_balance * risk_pct
        sl_distance = atr * sl_atr_mult

        if sl_distance <= 0:
            return {"qty": 0, "risk_amount": 0, "sl_distance": 0}

        lot_size = self._calc_mt5_lots(symbol, risk_amount, sl_distance)
        if lot_size <= 0:
            lot_size = round(risk_amount / sl_distance, 6)

        return {
            "qty": lot_size,
            "risk_amount": round(risk_amount, 2),
            "sl_distance": round(sl_distance, 2),
        }

    def _calc_mt5_lots(self, symbol: str, risk_amount: float,
                       sl_distance: float) -> float:
        if not symbol:
            return 0
        try:
            import MetaTrader5 as mt5
            info = mt5.symbol_info(symbol)
            if not info:
                return 0
            tick_size = info.trade_tick_size
            tick_value = info.trade_tick_value
            if tick_size <= 0 or tick_value <= 0:
                return 0
            ticks_in_sl = sl_distance / tick_size
            sl_value_per_lot = ticks_in_sl * tick_value
            if sl_value_per_lot <= 0:
                return 0
            lots = risk_amount / sl_value_per_lot
            lots = max(info.volume_min, min(info.volume_max, lots))
            lots = round(lots / info.volume_step) * info.volume_step
            return round(lots, 3)
        except ImportError:
            return 0
        except Exception as e:
            logger.warning(f"MT5 lot calc failed for {symbol}: {e}")
            return 0

    def register_trade(self, trade: dict):
        self.open_trades.append(trade)
        self.last_trade_time[trade["symbol"]] = datetime.now()
        self._log_trade(trade)

    def close_trade(self, symbol: str, pnl: float):
        self.open_trades = [t for t in self.open_trades if t["symbol"] != symbol]
        self.daily_pnl += pnl

    def record_outcome(self, trade: dict, close_price: float, profit: float) -> dict:
        outcome = {
            "symbol": trade.get("symbol"),
            "action": trade.get("action"),
            "entry_price": trade.get("entry_price"),
            "close_price": close_price,
            "sl": trade.get("sl"), "tp": trade.get("tp"),
            "qty": trade.get("qty"),
            "profit": round(profit, 2),
            "result": "WIN" if profit > 0 else "LOSS",
            "confidence": trade.get("confidence"),
            "reason": trade.get("reason"),
            "entry_time": trade.get("timestamp"),
            "close_time": datetime.now().isoformat(),
            "duration_minutes": self._calc_duration(trade.get("timestamp", "")),
        }
        try:
            outcomes = []
            if self.outcome_log_path.exists():
                text = self.outcome_log_path.read_text(encoding="utf-8-sig").strip()
                if text:
                    outcomes = json.loads(text)
            outcomes.append(outcome)
            self.outcome_log_path.write_text(json.dumps(outcomes[-500:], indent=2))
        except Exception as e:
            logger.error(f"Failed to log outcome: {e}")

        self._update_streak(trade["symbol"], profit > 0)
        self.daily_pnl += profit
        return outcome

    def _update_streak(self, symbol: str, is_win: bool):
        if symbol not in self.symbol_streaks:
            self.symbol_streaks[symbol] = {"type": "win" if is_win else "loss", "count": 0}
        streak = self.symbol_streaks[symbol]
        current_type = "win" if is_win else "loss"
        if streak["type"] == current_type:
            streak["count"] += 1
        else:
            streak["type"] = current_type
            streak["count"] = 1

        trigger = self.adaptive_cfg.get("cooldown_on_streak_loss", 3)
        duration = self.adaptive_cfg.get("cooldown_duration_minutes", 30)
        if streak["type"] == "loss" and streak["count"] >= trigger:
            self.cooled_down_symbols[symbol] = datetime.now() + timedelta(minutes=duration)
            logger.warning(f"{symbol}: {streak['count']} losses — cooldown {duration}min")

    def adjust_threshold(self, win_rate: float, total_trades: int):
        if not self.adaptive_cfg.get("enabled", False):
            return
        if total_trades < self.adaptive_cfg.get("min_trades_for_adaptation", 5):
            return

        max_t = self.adaptive_cfg.get("max_confidence_threshold", 0.85)
        min_t = self.adaptive_cfg.get("min_confidence_threshold", 0.50)
        old = self.current_threshold

        if win_rate < 40:
            self.current_threshold = min(self.current_threshold + 0.05, max_t)
        elif win_rate > 60:
            self.current_threshold = max(self.current_threshold - 0.02, min_t)

        if self.current_threshold != old:
            adj = {
                "timestamp": datetime.now().isoformat(),
                "old_value": round(old, 3),
                "new_value": round(self.current_threshold, 3),
                "win_rate": round(win_rate, 1),
            }
            try:
                adjs = []
                if self.param_adj_path.exists():
                    text = self.param_adj_path.read_text(encoding="utf-8-sig").strip()
                    if text:
                        adjs = json.loads(text)
                adjs.append(adj)
                self.param_adj_path.write_text(json.dumps(adjs[-100:], indent=2))
            except Exception:
                pass

    def _calc_duration(self, entry_time_str: str) -> float:
        try:
            return round((datetime.now() - datetime.fromisoformat(entry_time_str)).total_seconds() / 60, 1)
        except Exception:
            return 0

    def _log_trade(self, trade: dict):
        try:
            trades = []
            if self.trade_log_path.exists():
                text = self.trade_log_path.read_text(encoding="utf-8-sig").strip()
                if text:
                    trades = json.loads(text)
            trades.append(trade)
            self.trade_log_path.write_text(json.dumps(trades, indent=2))
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")
