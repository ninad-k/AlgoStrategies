"""Interactive Brokers adapter — stocks, options, futures, forex.

Requires ``pip install ib_insync``. Connects to TWS or IB Gateway.
Paper trading uses port 7497 (vs 7496 for live).
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from ..protocol import Account, CloseResult, FillResult, OrderIntent, Position

log = structlog.get_logger(__name__)


def _ib():
    """Lazy import of ib_insync."""
    try:
        import ib_insync
        return ib_insync
    except ImportError:
        raise ImportError(
            "ib_insync is not installed. Run: pip install 'tradingview-mcp-ninad[brokers]'"
        ) from None


class IBKRBroker:
    """Interactive Brokers adapter implementing BrokerProtocol."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1) -> None:
        self._host = host
        self._port = port
        self._client_id = client_id
        self._ib: Any = None

    @property
    def name(self) -> str:
        return "ibkr"

    async def _ensure_connected(self) -> None:
        if self._ib is not None and self._ib.isConnected():
            return
        ib_mod = _ib()
        self._ib = ib_mod.IB()
        await self._ib.connectAsync(self._host, self._port, clientId=self._client_id)

    def _make_contract(self, symbol: str):
        """Build an IB contract from a symbol string.

        Handles common patterns:
        - ES1!, NQ1! → Futures
        - AAPL, TSLA → Stocks
        - EURUSD → Forex
        """
        ib_mod = _ib()
        clean = symbol.strip().upper()

        if clean.endswith("!"):
            # Futures: ES1!, NQ1!, CL1!
            base = clean.rstrip("!").rstrip("0123456789")
            return ib_mod.Future(base, exchange="CME")

        if len(clean) == 6 and clean[:3].isalpha() and clean[3:].isalpha():
            # Forex: EURUSD, GBPJPY
            return ib_mod.Forex(clean[:3] + clean[3:])

        # Default: stock
        return ib_mod.Stock(clean, "SMART", "USD")

    async def place_order(self, intent: OrderIntent) -> FillResult:
        try:
            await self._ensure_connected()
            ib_mod = _ib()

            contract = self._make_contract(intent.symbol)
            action = "BUY" if intent.side == "buy" else "SELL"

            if intent.order_type == "market":
                order = ib_mod.MarketOrder(action, intent.quantity)
            elif intent.order_type == "limit":
                order = ib_mod.LimitOrder(action, intent.quantity, intent.price)
            elif intent.order_type == "stop":
                order = ib_mod.StopOrder(action, intent.quantity, intent.price)
            elif intent.order_type == "stop_limit":
                order = ib_mod.StopLimitOrder(action, intent.quantity, intent.price, intent.stop_loss)
            else:
                return FillResult(ok=False, error=f"Unsupported order type: {intent.order_type}", broker=self.name)

            trade = self._ib.placeOrder(contract, order)
            # Wait briefly for fill (market orders typically fill quickly)
            await asyncio.sleep(2.0)

            fill_price = None
            if trade.fills:
                fill_price = trade.fills[-1].execution.avgPrice

            return FillResult(
                ok=True,
                order_id=str(trade.order.orderId),
                price=fill_price,
                quantity=intent.quantity,
                broker=self.name,
            )
        except Exception as exc:
            return FillResult(ok=False, error=str(exc), broker=self.name)

    async def close_position(self, ticket: int, reason: str = "") -> CloseResult:
        try:
            await self._ensure_connected()
            positions = self._ib.positions()
            # Find position matching this ticket (we use hash of contract as ticket)
            for pos in positions:
                if hash(pos.contract.conId) & 0x7FFFFFFF == ticket:
                    ib_mod = _ib()
                    action = "SELL" if pos.position > 0 else "BUY"
                    order = ib_mod.MarketOrder(action, abs(pos.position))
                    self._ib.placeOrder(pos.contract, order)
                    await asyncio.sleep(2.0)
                    return CloseResult(ok=True, ticket=ticket, broker=self.name)
            return CloseResult(ok=False, ticket=ticket, error="Position not found", broker=self.name)
        except Exception as exc:
            return CloseResult(ok=False, ticket=ticket, error=str(exc), broker=self.name)

    async def get_positions(self) -> list[Position]:
        try:
            await self._ensure_connected()
            raw = self._ib.positions()
            return [
                Position(
                    ticket=hash(p.contract.conId) & 0x7FFFFFFF,
                    symbol=p.contract.symbol,
                    side="buy" if p.position > 0 else "sell",
                    quantity=abs(p.position),
                    entry_price=p.avgCost,
                    current_price=None,
                    unrealized_pnl=None,
                    broker=self.name,
                )
                for p in raw
                if p.position != 0
            ]
        except Exception:
            return []

    async def get_account(self) -> Account:
        try:
            await self._ensure_connected()
            summary = self._ib.accountSummary()
            values = {s.tag: float(s.value) for s in summary if s.tag in ("TotalCashValue", "NetLiquidation", "AvailableFunds")}
            return Account(
                balance=values.get("TotalCashValue", 0),
                equity=values.get("NetLiquidation", 0),
                free_margin=values.get("AvailableFunds", 0),
                currency="USD",
                broker=self.name,
                mode="paper" if self._port == 7497 else "live",
            )
        except Exception:
            return Account(balance=0, equity=0, free_margin=0, broker=self.name, mode="error")

    async def get_orders(self) -> list[dict]:
        try:
            await self._ensure_connected()
            trades = self._ib.openTrades()
            return [
                {
                    "order_id": str(t.order.orderId),
                    "symbol": t.contract.symbol,
                    "action": t.order.action,
                    "type": t.order.orderType,
                    "qty": t.order.totalQuantity,
                    "status": t.orderStatus.status,
                    "broker": self.name,
                }
                for t in trades
            ]
        except Exception:
            return []

    async def cancel_order(self, order_id: str) -> dict:
        try:
            await self._ensure_connected()
            trades = self._ib.openTrades()
            for t in trades:
                if str(t.order.orderId) == order_id:
                    self._ib.cancelOrder(t.order)
                    return {"ok": True, "order_id": order_id, "broker": self.name}
            return {"ok": False, "error": "Order not found", "broker": self.name}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "broker": self.name}
