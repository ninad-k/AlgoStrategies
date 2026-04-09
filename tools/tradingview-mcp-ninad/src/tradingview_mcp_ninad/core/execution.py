"""Core execution logic — bridges MCP tool calls to the ExecutionManager.

Each function maps directly to one MCP tool. The functions handle parameter
conversion, call the singleton ExecutionManager, and return plain dicts that
the tool layer wraps with ``json_result``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..execution.manager import get_manager
from ..execution.protocol import OrderIntent


async def execute_trade(
    *,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market",
    price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """Place a trade through the configured broker."""
    mgr = get_manager()
    intent = OrderIntent(
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        quantity=quantity,
        order_type=order_type,  # type: ignore[arg-type]
        price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason=reason,
    )
    result = await mgr.execute(intent)
    return {"success": result.ok, **asdict(result)}


async def close_position(*, ticket: int, reason: str = "") -> dict[str, Any]:
    """Close a specific position by ticket."""
    mgr = get_manager()
    result = await mgr.close_position(ticket, reason)
    return {"success": result.ok, **asdict(result)}


async def close_all_positions() -> dict[str, Any]:
    """Close every open position across all brokers."""
    mgr = get_manager()
    return await mgr.close_all()


async def modify_position(
    *,
    ticket: int,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> dict[str, Any]:
    """Modify SL/TP on a paper broker position.

    For live brokers, modification requires broker-specific logic which
    varies significantly. This currently supports the paper broker only.
    """
    mgr = get_manager()
    if mgr.mode == "paper":
        pos = mgr._paper._positions.get(ticket)
        if pos is None:
            return {"success": False, "error": f"Position {ticket} not found"}
        if stop_loss is not None:
            pos.stop_loss = stop_loss
        if take_profit is not None:
            pos.take_profit = take_profit
        return {
            "success": True,
            "ticket": ticket,
            "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit,
        }
    return {"success": False, "error": "Position modification on live brokers is not yet supported. Close and re-enter instead."}


async def get_positions() -> dict[str, Any]:
    """List all open positions across brokers."""
    mgr = get_manager()
    positions = await mgr.get_positions()
    return {
        "success": True,
        "mode": mgr.mode,
        "count": len(positions),
        "positions": [asdict(p) for p in positions],
    }


async def get_orders() -> dict[str, Any]:
    """List pending orders."""
    mgr = get_manager()
    orders = await mgr.get_orders()
    return {"success": True, "mode": mgr.mode, "count": len(orders), "orders": orders}


async def cancel_order(*, order_id: str) -> dict[str, Any]:
    """Cancel a pending order."""
    mgr = get_manager()
    return await mgr.cancel_order(order_id)


async def get_account() -> dict[str, Any]:
    """Get account balance, equity, and margin."""
    mgr = get_manager()
    account = await mgr.get_account()
    if isinstance(account, dict):
        return account
    return {"success": True, **asdict(account)}


async def get_trade_history() -> dict[str, Any]:
    """Return closed trades from the current session."""
    mgr = get_manager()
    history = mgr.get_trade_history()
    return {"success": True, "count": len(history), "trades": history}


def set_mode(*, mode: str, confirm: bool = False) -> dict[str, Any]:
    """Switch execution mode (paper / paper_broker / live)."""
    mgr = get_manager()
    if confirm:
        return mgr.set_mode_confirmed(mode)  # type: ignore[arg-type]
    return mgr.set_mode(mode)  # type: ignore[arg-type]


def get_mode() -> dict[str, Any]:
    """Return the current execution mode."""
    mgr = get_manager()
    return {"success": True, "mode": mgr.mode}


def broker_status() -> dict[str, Any]:
    """Check which brokers are configured and connected."""
    mgr = get_manager()
    return {"success": True, **mgr.broker_status()}
