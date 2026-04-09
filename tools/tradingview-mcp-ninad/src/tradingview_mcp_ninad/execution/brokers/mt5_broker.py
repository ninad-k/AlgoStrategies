"""MetaTrader 5 broker adapter — forex, CFDs, indices.

Requires the ``MetaTrader5`` package (Windows only; macOS/Linux via Wine).
The MT5 library is imported lazily so the package installs on any platform.
Adapted from the gemma-agent mt5_broker.py pattern.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from ..protocol import Account, CloseResult, FillResult, OrderIntent, Position

log = structlog.get_logger(__name__)


def _mt5():
    """Lazy import — fails gracefully if MT5 is not installed."""
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        raise ImportError(
            "MetaTrader5 is not installed. Run: pip install 'tradingview-mcp-ninad[mt5]' (Windows only)"
        ) from None


class MT5Broker:
    """MetaTrader 5 adapter implementing BrokerProtocol."""

    def __init__(self, login: int, password: str, server: str, path: str = "", magic: int = 20260409) -> None:
        self._login = login
        self._password = password
        self._server = server
        self._path = path
        self._magic = magic
        self._connected = False

    @property
    def name(self) -> str:
        return "mt5"

    async def _ensure_connected(self) -> None:
        if self._connected:
            return
        mt5 = _mt5()
        kwargs: dict[str, Any] = {
            "login": self._login,
            "password": self._password,
            "server": self._server,
        }
        if self._path:
            kwargs["path"] = self._path
        ok = await asyncio.to_thread(mt5.initialize, **kwargs)
        if not ok:
            raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
        self._connected = True

    async def place_order(self, intent: OrderIntent) -> FillResult:
        try:
            await self._ensure_connected()
            mt5 = _mt5()

            tick = await asyncio.to_thread(mt5.symbol_info_tick, intent.symbol)
            if tick is None:
                return FillResult(ok=False, error=f"No tick data for {intent.symbol}", broker=self.name)

            price = tick.ask if intent.side == "buy" else tick.bid
            order_type = mt5.ORDER_TYPE_BUY if intent.side == "buy" else mt5.ORDER_TYPE_SELL

            request: dict[str, Any] = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": intent.symbol,
                "volume": intent.quantity,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": self._magic,
                "comment": (intent.reason or "mcp-ninad")[:31],
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            if intent.stop_loss:
                request["sl"] = intent.stop_loss
            if intent.take_profit:
                request["tp"] = intent.take_profit

            result = await asyncio.to_thread(mt5.order_send, request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                error_msg = f"MT5 order failed: {result.comment if result else 'No response'}"
                return FillResult(ok=False, error=error_msg, broker=self.name)

            return FillResult(
                ok=True,
                ticket=result.order,
                price=result.price,
                quantity=intent.quantity,
                broker=self.name,
            )
        except Exception as exc:
            return FillResult(ok=False, error=str(exc), broker=self.name)

    async def close_position(self, ticket: int, reason: str = "") -> CloseResult:
        try:
            await self._ensure_connected()
            mt5 = _mt5()

            positions = await asyncio.to_thread(mt5.positions_get, ticket=ticket)
            if not positions:
                return CloseResult(ok=False, ticket=ticket, error="Position not found", broker=self.name)

            pos = positions[0]
            close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = await asyncio.to_thread(mt5.symbol_info_tick, pos.symbol)
            price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": self._magic,
                "comment": (reason or "close")[:31],
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = await asyncio.to_thread(mt5.order_send, request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                return CloseResult(ok=False, ticket=ticket, error=f"Close failed: {result.comment if result else 'No response'}", broker=self.name)

            pnl = pos.profit
            return CloseResult(ok=True, ticket=ticket, exit_price=result.price, pnl=pnl, broker=self.name)
        except Exception as exc:
            return CloseResult(ok=False, ticket=ticket, error=str(exc), broker=self.name)

    async def get_positions(self) -> list[Position]:
        try:
            await self._ensure_connected()
            mt5 = _mt5()
            raw = await asyncio.to_thread(mt5.positions_get)
            if not raw:
                return []
            return [
                Position(
                    ticket=p.ticket,
                    symbol=p.symbol,
                    side="buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
                    quantity=p.volume,
                    entry_price=p.price_open,
                    current_price=p.price_current,
                    unrealized_pnl=p.profit,
                    stop_loss=p.sl if p.sl > 0 else None,
                    take_profit=p.tp if p.tp > 0 else None,
                    broker=self.name,
                )
                for p in raw
            ]
        except Exception:
            return []

    async def get_account(self) -> Account:
        try:
            await self._ensure_connected()
            mt5 = _mt5()
            info = await asyncio.to_thread(mt5.account_info)
            return Account(
                balance=info.balance,
                equity=info.equity,
                free_margin=info.margin_free,
                currency=info.currency,
                broker=self.name,
                mode="live",
            )
        except Exception:
            return Account(balance=0, equity=0, free_margin=0, broker=self.name, mode="error")

    async def get_orders(self) -> list[dict]:
        try:
            await self._ensure_connected()
            mt5 = _mt5()
            orders = await asyncio.to_thread(mt5.orders_get)
            if not orders:
                return []
            return [
                {
                    "order_id": str(o.ticket),
                    "symbol": o.symbol,
                    "type": str(o.type),
                    "volume": o.volume_current,
                    "price": o.price_open,
                    "broker": self.name,
                }
                for o in orders
            ]
        except Exception:
            return []

    async def cancel_order(self, order_id: str) -> dict:
        try:
            await self._ensure_connected()
            mt5 = _mt5()
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": int(order_id),
            }
            result = await asyncio.to_thread(mt5.order_send, request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                return {"ok": True, "order_id": order_id, "broker": self.name}
            return {"ok": False, "error": f"Cancel failed: {result.comment if result else 'No response'}", "broker": self.name}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "broker": self.name}
