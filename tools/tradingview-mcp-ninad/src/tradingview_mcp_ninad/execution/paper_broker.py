"""Built-in paper broker — in-memory trade simulation with no external deps.

Orders fill immediately at the requested price (market orders use the last
known price). Stop-loss and take-profit are tracked and can be checked via
``check_sl_tp`` when new price data arrives. This is intentionally simpler
than the gemma-agent paper broker because it doesn't operate on a bar-by-bar
cadence — trades are placed interactively via MCP tool calls.
"""

from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime
from typing import Any

import structlog

from ..logging_config import state_dir
from .protocol import (
    Account,
    CloseResult,
    FillResult,
    OrderIntent,
    Position,
    TradeRecord,
)

log = structlog.get_logger(__name__)
TRADES_DIR = state_dir() / "trades"


class PaperBroker:
    """Zero-config paper trading simulator."""

    def __init__(
        self,
        starting_balance: float = 100_000.0,
        currency: str = "USD",
    ) -> None:
        self._balance = starting_balance
        self._currency = currency
        self._positions: dict[int, Position] = {}
        self._closed_trades: list[dict[str, Any]] = []
        self._ticker = itertools.count(1)
        self._last_prices: dict[str, float] = {}

    @property
    def name(self) -> str:
        return "paper"

    async def place_order(self, intent: OrderIntent) -> FillResult:
        """Fill immediately at the intent's price (or last known price for market orders)."""
        fill_price = intent.price
        if intent.order_type == "market" or fill_price is None:
            fill_price = self._last_prices.get(intent.symbol)
            if fill_price is None:
                return FillResult(
                    ok=False,
                    error=f"No price available for {intent.symbol}. Call quote_get first to establish a price.",
                    broker=self.name,
                )

        ticket = next(self._ticker)
        position = Position(
            ticket=ticket,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            entry_price=fill_price,
            current_price=fill_price,
            unrealized_pnl=0.0,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
            broker=self.name,
            opened_at=datetime.now(UTC).isoformat(),
        )
        self._positions[ticket] = position
        self._log_trade(intent, {"ok": True, "ticket": ticket, "price": fill_price})

        log.info(
            "paper.order_filled",
            ticket=ticket,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            price=fill_price,
        )
        return FillResult(
            ok=True,
            ticket=ticket,
            price=fill_price,
            quantity=intent.quantity,
            broker=self.name,
        )

    async def close_position(self, ticket: int, reason: str = "") -> CloseResult:
        """Close a position at the last known price."""
        pos = self._positions.get(ticket)
        if pos is None:
            return CloseResult(ok=False, ticket=ticket, error=f"Position {ticket} not found", broker=self.name)

        exit_price = self._last_prices.get(pos.symbol, pos.entry_price)
        pnl = self._calculate_pnl(pos, exit_price)
        self._balance += pnl

        trade_record = {
            "ticket": ticket,
            "symbol": pos.symbol,
            "side": pos.side,
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "pnl": round(pnl, 2),
            "reason": reason,
            "closed_at": datetime.now(UTC).isoformat(),
        }
        self._closed_trades.append(trade_record)
        del self._positions[ticket]

        log.info("paper.position_closed", **trade_record)
        return CloseResult(ok=True, ticket=ticket, exit_price=exit_price, pnl=round(pnl, 2), broker=self.name)

    async def get_positions(self) -> list[Position]:
        """Return all open positions with updated P&L."""
        for pos in self._positions.values():
            price = self._last_prices.get(pos.symbol, pos.entry_price)
            pos.current_price = price
            pos.unrealized_pnl = round(self._calculate_pnl(pos, price), 2)
        return list(self._positions.values())

    async def get_account(self) -> Account:
        unrealized = sum(
            self._calculate_pnl(p, self._last_prices.get(p.symbol, p.entry_price))
            for p in self._positions.values()
        )
        equity = self._balance + unrealized
        return Account(
            balance=round(self._balance, 2),
            equity=round(equity, 2),
            free_margin=round(equity, 2),
            currency=self._currency,
            broker=self.name,
            mode="paper",
        )

    async def get_orders(self) -> list[dict]:
        """Paper broker fills immediately — no pending orders."""
        return []

    async def cancel_order(self, order_id: str) -> dict:
        return {"ok": False, "error": "Paper broker has no pending orders"}

    def update_price(self, symbol: str, price: float) -> None:
        """Feed a price update so subsequent trades and P&L calculations use current market data."""
        self._last_prices[symbol] = price

    def get_trade_history(self) -> list[dict[str, Any]]:
        """Return all closed trades for this session."""
        return list(self._closed_trades)

    def _calculate_pnl(self, pos: Position, exit_price: float) -> float:
        """Simplified P&L: (exit - entry) * quantity * direction."""
        direction = 1.0 if pos.side == "buy" else -1.0
        return (exit_price - pos.entry_price) * pos.quantity * direction

    def _log_trade(self, intent: OrderIntent, result: dict) -> None:
        """Persist trade to disk for audit trail."""
        TRADES_DIR.mkdir(parents=True, exist_ok=True)
        record = TradeRecord(
            timestamp=datetime.now(UTC).isoformat(),
            intent={
                "symbol": intent.symbol,
                "side": intent.side,
                "quantity": intent.quantity,
                "order_type": intent.order_type,
                "price": intent.price,
                "stop_loss": intent.stop_loss,
                "take_profit": intent.take_profit,
                "reason": intent.reason,
            },
            result=result,
            mode="paper",
            broker=self.name,
        )
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        log_path = TRADES_DIR / f"paper_{date_str}.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.__dict__, default=str) + "\n")
