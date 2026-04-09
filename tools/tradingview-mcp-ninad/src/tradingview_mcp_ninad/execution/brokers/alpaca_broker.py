"""Alpaca Markets broker adapter — US stocks and crypto.

Requires ``pip install alpaca-py``. Supports both paper and live modes
via the ``paper`` flag in execution config.
"""

from __future__ import annotations

import structlog

from ..protocol import Account, CloseResult, FillResult, OrderIntent, Position

log = structlog.get_logger(__name__)


def _alpaca():
    """Lazy import so the package isn't required unless this broker is used."""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
        from alpaca.trading.requests import (
            LimitOrderRequest,
            MarketOrderRequest,
            StopLimitOrderRequest,
            StopOrderRequest,
        )
        return {
            "TradingClient": TradingClient,
            "OrderSide": OrderSide,
            "OrderType": OrderType,
            "TimeInForce": TimeInForce,
            "MarketOrderRequest": MarketOrderRequest,
            "LimitOrderRequest": LimitOrderRequest,
            "StopOrderRequest": StopOrderRequest,
            "StopLimitOrderRequest": StopLimitOrderRequest,
        }
    except ImportError:
        raise ImportError(
            "alpaca-py is not installed. Run: pip install 'tradingview-mcp-ninad[brokers]'"
        ) from None


class AlpacaBroker:
    """Alpaca Markets adapter implementing BrokerProtocol."""

    def __init__(self, api_key: str, api_secret: str, *, paper: bool = True) -> None:
        sdk = _alpaca()
        self._client = sdk["TradingClient"](api_key, api_secret, paper=paper)
        self._sdk = sdk
        self._paper = paper

    @property
    def name(self) -> str:
        return "alpaca"

    async def place_order(self, intent: OrderIntent) -> FillResult:
        import asyncio
        try:
            sdk = self._sdk
            side = sdk["OrderSide"].BUY if intent.side == "buy" else sdk["OrderSide"].SELL
            tif = sdk["TimeInForce"].GTC

            if intent.order_type == "market":
                req = sdk["MarketOrderRequest"](symbol=intent.symbol, qty=intent.quantity, side=side, time_in_force=tif)
            elif intent.order_type == "limit":
                req = sdk["LimitOrderRequest"](symbol=intent.symbol, qty=intent.quantity, side=side, time_in_force=tif, limit_price=intent.price)
            elif intent.order_type == "stop":
                req = sdk["StopOrderRequest"](symbol=intent.symbol, qty=intent.quantity, side=side, time_in_force=tif, stop_price=intent.price)
            elif intent.order_type == "stop_limit":
                req = sdk["StopLimitOrderRequest"](symbol=intent.symbol, qty=intent.quantity, side=side, time_in_force=tif, stop_price=intent.stop_loss, limit_price=intent.price)
            else:
                return FillResult(ok=False, error=f"Unsupported order type: {intent.order_type}", broker=self.name)

            order = await asyncio.to_thread(self._client.submit_order, req)
            return FillResult(
                ok=True,
                order_id=str(order.id),
                price=float(order.filled_avg_price) if order.filled_avg_price else None,
                quantity=float(order.filled_qty) if order.filled_qty else intent.quantity,
                broker=self.name,
            )
        except Exception as exc:
            return FillResult(ok=False, error=str(exc), broker=self.name)

    async def close_position(self, ticket: int, reason: str = "") -> CloseResult:
        import asyncio
        try:
            # Alpaca closes by symbol, not ticket. Find the position first.
            positions = await self.get_positions()
            pos = next((p for p in positions if p.ticket == ticket), None)
            if pos is None:
                return CloseResult(ok=False, ticket=ticket, error="Position not found", broker=self.name)
            await asyncio.to_thread(self._client.close_position, pos.symbol)
            return CloseResult(ok=True, ticket=ticket, broker=self.name)
        except Exception as exc:
            return CloseResult(ok=False, ticket=ticket, error=str(exc), broker=self.name)

    async def get_positions(self) -> list[Position]:
        import asyncio
        try:
            raw = await asyncio.to_thread(self._client.get_all_positions)
            return [
                Position(
                    ticket=hash(p.asset_id) & 0x7FFFFFFF,
                    symbol=p.symbol,
                    side="buy" if float(p.qty) > 0 else "sell",
                    quantity=abs(float(p.qty)),
                    entry_price=float(p.avg_entry_price),
                    current_price=float(p.current_price) if p.current_price else None,
                    unrealized_pnl=float(p.unrealized_pl) if p.unrealized_pl else None,
                    broker=self.name,
                )
                for p in raw
            ]
        except Exception:
            return []

    async def get_account(self) -> Account:
        import asyncio
        acc = await asyncio.to_thread(self._client.get_account)
        return Account(
            balance=float(acc.cash),
            equity=float(acc.equity),
            free_margin=float(acc.buying_power),
            currency=acc.currency or "USD",
            broker=self.name,
            mode="paper" if self._paper else "live",
        )

    async def get_orders(self) -> list[dict]:
        import asyncio
        try:
            orders = await asyncio.to_thread(self._client.get_orders)
            return [
                {
                    "order_id": str(o.id),
                    "symbol": o.symbol,
                    "side": str(o.side),
                    "type": str(o.type),
                    "qty": str(o.qty),
                    "status": str(o.status),
                    "broker": self.name,
                }
                for o in orders
            ]
        except Exception:
            return []

    async def cancel_order(self, order_id: str) -> dict:
        import asyncio
        try:
            await asyncio.to_thread(self._client.cancel_order_by_id, order_id)
            return {"ok": True, "order_id": order_id, "broker": self.name}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "broker": self.name}
