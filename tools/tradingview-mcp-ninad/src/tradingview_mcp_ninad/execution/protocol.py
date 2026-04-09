"""Broker protocol and shared data models for the execution layer.

Every broker adapter (paper, Alpaca, Binance, MT5, IBKR) implements
:class:`BrokerProtocol` so the :class:`ExecutionManager` can route orders
without knowing which broker sits behind the interface. The data models
use ``dataclass(frozen=True)`` for immutability — once a fill is reported,
it never changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop", "stop_limit"]
ExecutionMode = Literal["paper", "paper_broker", "live"]


@dataclass(frozen=True)
class OrderIntent:
    """What the caller wants to trade — broker-agnostic."""

    symbol: str
    side: Side
    quantity: float
    order_type: OrderType = "market"
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class FillResult:
    """What actually happened when the order hit the broker."""

    ok: bool
    order_id: str | None = None
    ticket: int | None = None
    price: float | None = None
    quantity: float | None = None
    error: str | None = None
    broker: str = ""


@dataclass
class Position:
    """An open position held at a broker."""

    ticket: int
    symbol: str
    side: Side
    quantity: float
    entry_price: float
    current_price: float | None = None
    unrealized_pnl: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    broker: str = ""
    opened_at: str = ""


@dataclass(frozen=True)
class CloseResult:
    """Outcome of closing a position."""

    ok: bool
    ticket: int = 0
    exit_price: float | None = None
    pnl: float | None = None
    error: str | None = None
    broker: str = ""


@dataclass(frozen=True)
class Account:
    """Snapshot of account balances."""

    balance: float
    equity: float
    free_margin: float
    currency: str = "USD"
    broker: str = ""
    mode: str = "paper"


@dataclass(frozen=True)
class TradeRecord:
    """Persisted log entry for every order attempt."""

    timestamp: str
    intent: dict
    result: dict
    mode: str
    broker: str


@runtime_checkable
class BrokerProtocol(Protocol):
    """Interface that every broker adapter must implement.

    The execution manager calls these methods without knowing the
    concrete broker type. ``on_new_bar`` is optional — only the paper
    broker uses it for mark-to-market and SL/TP simulation.
    """

    async def place_order(self, intent: OrderIntent) -> FillResult: ...

    async def close_position(self, ticket: int, reason: str = "") -> CloseResult: ...

    async def get_positions(self) -> list[Position]: ...

    async def get_account(self) -> Account: ...

    async def get_orders(self) -> list[dict]: ...

    async def cancel_order(self, order_id: str) -> dict: ...

    @property
    def name(self) -> str: ...
