"""Binance broker adapter — crypto spot and futures.

Requires ``pip install python-binance``. Supports testnet mode via the
``testnet`` flag in execution config.
"""

from __future__ import annotations

from typing import Any

import structlog

from ..protocol import Account, CloseResult, FillResult, OrderIntent, Position

log = structlog.get_logger(__name__)


def _binance_client(api_key: str, api_secret: str, *, testnet: bool = True):
    """Lazy import and create a Binance async client."""
    try:
        from binance import AsyncClient
    except ImportError:
        raise ImportError(
            "python-binance is not installed. Run: pip install 'tradingview-mcp-ninad[brokers]'"
        ) from None
    return AsyncClient(api_key, api_secret, testnet=testnet)


class BinanceBroker:
    """Binance adapter implementing BrokerProtocol."""

    def __init__(self, api_key: str, api_secret: str, *, testnet: bool = True) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._testnet = testnet
        self._client: Any = None

    @property
    def name(self) -> str:
        return "binance"

    async def _get_client(self):
        if self._client is None:
            self._client = _binance_client(self._api_key, self._api_secret, testnet=self._testnet)
        return self._client

    async def place_order(self, intent: OrderIntent) -> FillResult:
        try:
            client = await self._get_client()
            side = "BUY" if intent.side == "buy" else "SELL"
            params: dict[str, Any] = {
                "symbol": intent.symbol.upper().replace("/", ""),
                "side": side,
                "quantity": intent.quantity,
            }
            if intent.order_type == "market":
                params["type"] = "MARKET"
            elif intent.order_type == "limit":
                params["type"] = "LIMIT"
                params["price"] = str(intent.price)
                params["timeInForce"] = "GTC"
            elif intent.order_type == "stop":
                params["type"] = "STOP_MARKET" if not intent.price else "STOP_LOSS_LIMIT"
                params["stopPrice"] = str(intent.stop_loss or intent.price)
                if intent.price:
                    params["price"] = str(intent.price)
                    params["timeInForce"] = "GTC"
            else:
                return FillResult(ok=False, error=f"Unsupported order type: {intent.order_type}", broker=self.name)

            result = await client.create_order(**params)
            fill_price = None
            if result.get("fills"):
                prices = [float(f["price"]) for f in result["fills"]]
                fill_price = sum(prices) / len(prices) if prices else None

            return FillResult(
                ok=True,
                order_id=str(result.get("orderId")),
                price=fill_price,
                quantity=float(result.get("executedQty", intent.quantity)),
                broker=self.name,
            )
        except Exception as exc:
            return FillResult(ok=False, error=str(exc), broker=self.name)

    async def close_position(self, ticket: int, reason: str = "") -> CloseResult:
        # Binance doesn't have position "tickets" — close by placing an opposite order.
        # This is a simplified approach; production code should track positions internally.
        return CloseResult(
            ok=False,
            ticket=ticket,
            error="Use trade_execute with opposite side to close Binance positions. Binance does not have position tickets.",
            broker=self.name,
        )

    async def get_positions(self) -> list[Position]:
        try:
            client = await self._get_client()
            account = await client.get_account()
            positions = []
            for balance in account.get("balances", []):
                free = float(balance.get("free", 0))
                locked = float(balance.get("locked", 0))
                total = free + locked
                if total > 0 and balance["asset"] not in ("USDT", "USDC", "BUSD", "USD"):
                    positions.append(Position(
                        ticket=hash(balance["asset"]) & 0x7FFFFFFF,
                        symbol=balance["asset"],
                        side="buy",
                        quantity=total,
                        entry_price=0.0,
                        broker=self.name,
                    ))
            return positions
        except Exception:
            return []

    async def get_account(self) -> Account:
        try:
            client = await self._get_client()
            account = await client.get_account()
            usdt = next(
                (float(b["free"]) + float(b["locked"]) for b in account.get("balances", []) if b["asset"] == "USDT"),
                0.0,
            )
            return Account(
                balance=usdt,
                equity=usdt,
                free_margin=usdt,
                currency="USDT",
                broker=self.name,
                mode="testnet" if self._testnet else "live",
            )
        except Exception:
            return Account(balance=0, equity=0, free_margin=0, broker=self.name, mode="error")

    async def get_orders(self) -> list[dict]:
        try:
            client = await self._get_client()
            orders = await client.get_open_orders()
            return [
                {
                    "order_id": str(o.get("orderId")),
                    "symbol": o.get("symbol"),
                    "side": o.get("side"),
                    "type": o.get("type"),
                    "qty": o.get("origQty"),
                    "price": o.get("price"),
                    "status": o.get("status"),
                    "broker": self.name,
                }
                for o in orders
            ]
        except Exception:
            return []

    async def cancel_order(self, order_id: str) -> dict:
        try:
            client = await self._get_client()
            await client.cancel_order(orderId=int(order_id))
            return {"ok": True, "order_id": order_id, "broker": self.name}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "broker": self.name}
