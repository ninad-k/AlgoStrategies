"""In-memory risk management engine. All checks complete in <5ms."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import deque
from pathlib import Path
from typing import Optional

import yaml

from .models import SignalAction, WebhookAlert

log = logging.getLogger(__name__)


class RiskConfig:
    """Risk parameters loaded from configs/risk.yaml or defaults."""

    def __init__(self) -> None:
        self.max_lot_size: float = 1.0
        self.max_trades_per_day: int = 20
        self.max_open_per_symbol: int = 3
        self.max_total_open: int = 10
        self.cooldown_seconds: float = 5.0
        self.max_daily_loss_usd: float = 500.0
        self.max_daily_loss_percent: float = 5.0
        self.max_spread_points: int = 30
        self.equity_stop_percent: float = 10.0
        self.dedup_window_seconds: float = 5.0
        self.dedup_buffer_size: int = 100
        self.daily_reset_hour_utc: int = 0

        self._load_yaml()

    def _load_yaml(self) -> None:
        path = Path(__file__).parent.parent / "configs" / "risk.yaml"
        if not path.exists():
            log.warning("No risk.yaml found, using defaults")
            return
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        for key, val in data.items():
            if hasattr(self, key):
                setattr(self, key, type(getattr(self, key))(val))
        log.info("Risk config loaded from %s", path)


class RiskState:
    """Mutable in-memory risk state, reset daily."""

    def __init__(self) -> None:
        self.trades_today: int = 0
        self.open_trades: dict[str, int] = {}  # symbol -> count
        self.total_open: int = 0
        self.daily_pnl: float = 0.0
        self.equity: float = 0.0
        self.last_trade_time: dict[str, float] = {}  # symbol -> unix timestamp
        self.recent_hashes: deque[tuple[str, float]] = deque()  # (hash, timestamp)

    def reset_daily(self) -> None:
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.last_trade_time.clear()
        log.info("Risk state daily reset")


class RiskManager:
    """Fast, in-memory risk gate for incoming signals."""

    def __init__(self) -> None:
        self.config = RiskConfig()
        self.state = RiskState()
        self._lock = asyncio.Lock()

    async def check(self, alert: WebhookAlert, mt5_symbol: str) -> tuple[bool, str]:
        """Run all risk checks. Returns (passed, reason)."""
        async with self._lock:
            return self._check_sync(alert, mt5_symbol)

    def _check_sync(self, alert: WebhookAlert, mt5_symbol: str) -> tuple[bool, str]:
        # Close commands bypass most risk checks
        if alert.action in (
            SignalAction.closebuy,
            SignalAction.closesell,
            SignalAction.closeall,
            SignalAction.cancel_buylimit,
            SignalAction.cancel_selllimit,
        ):
            return True, ""

        now = time.time()

        # 1. Dedup check
        sig_hash = self._signal_hash(alert, mt5_symbol)
        self._prune_old_hashes(now)
        for h, t in self.state.recent_hashes:
            if h == sig_hash:
                return False, f"Duplicate signal within {self.config.dedup_window_seconds}s"
        self.state.recent_hashes.append((sig_hash, now))
        if len(self.state.recent_hashes) > self.config.dedup_buffer_size:
            self.state.recent_hashes.popleft()

        # 2. Max lot size
        if alert.lot > self.config.max_lot_size:
            return False, f"Lot {alert.lot} exceeds max {self.config.max_lot_size}"

        # 3. Max daily trades
        if self.state.trades_today >= self.config.max_trades_per_day:
            return False, f"Daily trade limit reached ({self.config.max_trades_per_day})"

        # 4. Max open per symbol
        open_count = self.state.open_trades.get(mt5_symbol, 0)
        if open_count >= self.config.max_open_per_symbol:
            return False, f"Max open trades for {mt5_symbol} ({self.config.max_open_per_symbol})"

        # 5. Max total open
        if self.state.total_open >= self.config.max_total_open:
            return False, f"Max total open trades ({self.config.max_total_open})"

        # 6. Cooldown
        last_time = self.state.last_trade_time.get(mt5_symbol, 0)
        elapsed = now - last_time
        if elapsed < self.config.cooldown_seconds:
            return False, f"Cooldown: {self.config.cooldown_seconds - elapsed:.1f}s remaining for {mt5_symbol}"

        # 7. Equity protection (only if equity is known)
        if self.state.equity > 0:
            if abs(self.state.daily_pnl) >= self.config.max_daily_loss_usd:
                return False, f"Daily loss limit ${self.config.max_daily_loss_usd} reached"
            loss_pct = abs(self.state.daily_pnl) / self.state.equity * 100
            if loss_pct >= self.config.max_daily_loss_percent:
                return False, f"Daily loss {loss_pct:.1f}% exceeds {self.config.max_daily_loss_percent}%"

        # All checks passed — record the trade
        self.state.trades_today += 1
        self.state.last_trade_time[mt5_symbol] = now

        return True, ""

    def record_open(self, symbol: str) -> None:
        """Called when a trade is confirmed open."""
        self.state.open_trades[symbol] = self.state.open_trades.get(symbol, 0) + 1
        self.state.total_open += 1

    def record_close(self, symbol: str, profit: float) -> None:
        """Called when a trade is confirmed closed."""
        if symbol in self.state.open_trades:
            self.state.open_trades[symbol] = max(0, self.state.open_trades[symbol] - 1)
            if self.state.open_trades[symbol] == 0:
                del self.state.open_trades[symbol]
        self.state.total_open = max(0, self.state.total_open - 1)
        self.state.daily_pnl += profit

    def update_equity(self, equity: float) -> None:
        self.state.equity = equity

    def _signal_hash(self, alert: WebhookAlert, mt5_symbol: str) -> str:
        raw = f"{alert.action.value}:{mt5_symbol}:{alert.lot}:{alert.sl}:{alert.tp}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _prune_old_hashes(self, now: float) -> None:
        cutoff = now - self.config.dedup_window_seconds
        while self.state.recent_hashes and self.state.recent_hashes[0][1] < cutoff:
            self.state.recent_hashes.popleft()
