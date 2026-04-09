"""ExecutionManager — routes orders to brokers, enforces safety limits.

The manager is the single entry point for all trade execution. It decides
which broker receives an order based on the symbol's asset class, enforces
position limits, and gates live trading behind explicit mode switching.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from .config import ExecutionConfig, load_execution_config
from .paper_broker import PaperBroker
from .protocol import (
    Account,
    BrokerProtocol,
    CloseResult,
    ExecutionMode,
    FillResult,
    OrderIntent,
    Position,
)

log = structlog.get_logger(__name__)

# Symbol classification patterns — used to route to the correct broker.
_CRYPTO_PATTERN = re.compile(
    r"^(BTC|ETH|SOL|BNB|XRP|ADA|DOGE|DOT|AVAX|LINK|MATIC|UNI|ATOM|LTC)"
    r"(USD|USDT|USDC|BUSD|EUR|GBP)?$",
    re.IGNORECASE,
)
_FOREX_PATTERN = re.compile(
    r"^(EUR|GBP|USD|JPY|CHF|AUD|NZD|CAD){2}$",
    re.IGNORECASE,
)
_FUTURES_PATTERN = re.compile(r".*[!]$")  # ES1!, NQ1!, CL1!, etc.


def _classify_symbol(symbol: str) -> str:
    """Return the asset class for a symbol: crypto, forex, futures, or stocks."""
    clean = symbol.replace("/", "").replace("-", "").strip().upper()
    if _CRYPTO_PATTERN.match(clean):
        return "crypto"
    if _FOREX_PATTERN.match(clean):
        return "forex"
    if _FUTURES_PATTERN.match(clean):
        return "futures"
    return "stocks"


class ExecutionManager:
    """Central coordinator for all trade execution."""

    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self._config = config or load_execution_config()
        self._mode: ExecutionMode = self._config.mode  # type: ignore[assignment]
        self._paper = PaperBroker(
            starting_balance=self._config.paper_balance,
            currency=self._config.paper_currency,
        )
        self._brokers: dict[str, BrokerProtocol] = {}
        self._initialized = False

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: ExecutionMode) -> dict[str, Any]:
        """Switch execution mode with safety checks."""
        if mode == "live" and self._config.require_confirmation_for_live:
            return {
                "success": False,
                "error": "Live trading requires explicit confirmation. Set require_confirmation_for_live=false in execution_config.json, or call trade_set_mode with confirm=true.",
                "current_mode": self._mode,
            }
        old = self._mode
        self._mode = mode
        log.info("execution.mode_changed", old=old, new=mode)
        return {"success": True, "previous_mode": old, "current_mode": mode}

    def set_mode_confirmed(self, mode: ExecutionMode) -> dict[str, Any]:
        """Switch mode bypassing the confirmation gate (for explicit user confirmation)."""
        old = self._mode
        self._mode = mode
        log.info("execution.mode_changed", old=old, new=mode, confirmed=True)
        return {"success": True, "previous_mode": old, "current_mode": mode}

    async def execute(self, intent: OrderIntent) -> FillResult:
        """Route an order to the appropriate broker."""
        # Enforce position limits
        if self._mode == "paper":
            positions = await self._paper.get_positions()
        else:
            positions = await self._get_all_positions()

        if len(positions) >= self._config.max_open_positions:
            return FillResult(
                ok=False,
                error=f"Max open positions ({self._config.max_open_positions}) reached. Close a position first.",
            )

        notional = intent.quantity * (intent.price or 0)
        if notional > self._config.max_position_size and intent.price:
            return FillResult(
                ok=False,
                error=f"Position size {notional:.2f} exceeds limit of {self._config.max_position_size:.2f}",
            )

        if self._mode == "paper":
            return await self._paper.place_order(intent)

        broker = self._get_broker_for_symbol(intent.symbol)
        if broker is None:
            return FillResult(
                ok=False,
                error=f"No broker configured for {intent.symbol} (class: {_classify_symbol(intent.symbol)})",
            )
        return await broker.place_order(intent)

    async def close_position(self, ticket: int, reason: str = "") -> CloseResult:
        if self._mode == "paper":
            return await self._paper.close_position(ticket, reason)

        for broker in self._brokers.values():
            positions = await broker.get_positions()
            if any(p.ticket == ticket for p in positions):
                return await broker.close_position(ticket, reason)
        return CloseResult(ok=False, ticket=ticket, error=f"Position {ticket} not found on any broker")

    async def close_all(self) -> dict[str, Any]:
        """Close every open position across all brokers."""
        results = []
        positions = await self.get_positions()
        for pos in positions:
            result = await self.close_position(pos.ticket, reason="close_all")
            results.append({"ticket": pos.ticket, "symbol": pos.symbol, **result.__dict__})
        return {"success": True, "closed": len(results), "results": results}

    async def get_positions(self) -> list[Position]:
        if self._mode == "paper":
            return await self._paper.get_positions()
        return await self._get_all_positions()

    async def get_account(self) -> Account | dict[str, Any]:
        if self._mode == "paper":
            return await self._paper.get_account()

        accounts = {}
        for name, broker in self._brokers.items():
            try:
                acc = await broker.get_account()
                accounts[name] = acc.__dict__ if hasattr(acc, "__dict__") else acc
            except Exception as exc:
                accounts[name] = {"error": str(exc)}

        if not accounts:
            return await self._paper.get_account()
        return {"success": True, "mode": self._mode, "accounts": accounts}  # type: ignore[return-value]

    async def get_orders(self) -> list[dict]:
        if self._mode == "paper":
            return await self._paper.get_orders()
        all_orders = []
        for broker in self._brokers.values():
            try:
                orders = await broker.get_orders()
                all_orders.extend(orders)
            except Exception:
                pass
        return all_orders

    async def cancel_order(self, order_id: str) -> dict:
        if self._mode == "paper":
            return await self._paper.cancel_order(order_id)
        for broker in self._brokers.values():
            try:
                result = await broker.cancel_order(order_id)
                if result.get("ok"):
                    return result
            except Exception:
                pass
        return {"ok": False, "error": f"Order {order_id} not found on any broker"}

    def get_trade_history(self) -> list[dict]:
        return self._paper.get_trade_history()

    def update_price(self, symbol: str, price: float) -> None:
        """Feed a price into the paper broker so it can fill market orders."""
        self._paper.update_price(symbol, price)

    def broker_status(self) -> dict[str, Any]:
        """Report which brokers are configured and their connection state."""
        status: dict[str, Any] = {
            "mode": self._mode,
            "paper": {"connected": True, "type": "built-in"},
        }
        cfg = self._config.brokers
        status["alpaca"] = {
            "configured": bool(cfg.alpaca.api_key),
            "paper_mode": cfg.alpaca.paper,
            "connected": "alpaca" in self._brokers,
        }
        status["binance"] = {
            "configured": bool(cfg.binance.api_key),
            "testnet": cfg.binance.testnet,
            "connected": "binance" in self._brokers,
        }
        status["mt5"] = {
            "configured": bool(cfg.mt5.login),
            "connected": "mt5" in self._brokers,
        }
        status["ibkr"] = {
            "configured": True,
            "port": cfg.ibkr.port,
            "connected": "ibkr" in self._brokers,
        }
        return status

    def register_broker(self, name: str, broker: BrokerProtocol) -> None:
        """Add a broker adapter. Called during startup or on-demand."""
        self._brokers[name] = broker
        log.info("execution.broker_registered", broker=name)

    def _get_broker_for_symbol(self, symbol: str) -> BrokerProtocol | None:
        asset_class = _classify_symbol(symbol)
        routing = self._config.symbol_routing
        broker_name = getattr(routing, asset_class, None)
        if broker_name and broker_name in self._brokers:
            return self._brokers[broker_name]
        # Fall back to any connected broker
        if self._brokers:
            return next(iter(self._brokers.values()))
        return None

    async def _get_all_positions(self) -> list[Position]:
        all_positions = []
        for broker in self._brokers.values():
            try:
                positions = await broker.get_positions()
                all_positions.extend(positions)
            except Exception:
                pass
        return all_positions


# Module-level singleton — initialized lazily on first use.
_manager: ExecutionManager | None = None


def get_manager() -> ExecutionManager:
    """Return the singleton ExecutionManager, creating it on first call."""
    global _manager
    if _manager is None:
        _manager = ExecutionManager()
    return _manager
