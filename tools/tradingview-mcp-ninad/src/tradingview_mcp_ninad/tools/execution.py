"""Trade execution MCP tools: place, close, modify, positions, orders, account, mode, broker status."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import execution as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(
        name="trade_execute",
        description="Place a trade (buy/sell). Supports market, limit, stop, stop_limit orders. Use trade_get_mode first to check current mode.",
    )
    async def trade_execute(
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        reason: str = "",
    ):
        try:
            return json_result(
                await core.execute_trade(
                    symbol=symbol, side=side, quantity=quantity,
                    order_type=order_type, price=price,
                    stop_loss=stop_loss, take_profit=take_profit, reason=reason,
                )
            )
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_close", description="Close a position by ticket number")
    async def trade_close(ticket: int, reason: str = ""):
        try:
            return json_result(await core.close_position(ticket=ticket, reason=reason))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_close_all", description="Close all open positions across all brokers")
    async def trade_close_all():
        try:
            return json_result(await core.close_all_positions())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_modify", description="Modify stop loss and/or take profit on an existing position")
    async def trade_modify(ticket: int, stop_loss: float | None = None, take_profit: float | None = None):
        try:
            return json_result(await core.modify_position(ticket=ticket, stop_loss=stop_loss, take_profit=take_profit))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_positions", description="List all open positions across all brokers")
    async def trade_positions():
        try:
            return json_result(await core.get_positions())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_orders", description="List all pending orders")
    async def trade_orders():
        try:
            return json_result(await core.get_orders())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_cancel_order", description="Cancel a pending order by order ID")
    async def trade_cancel_order(order_id: str):
        try:
            return json_result(await core.cancel_order(order_id=order_id))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_account", description="Get account balance, equity, and margin info")
    async def trade_account():
        try:
            return json_result(await core.get_account())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_history", description="Get trade history for the current session")
    async def trade_history():
        try:
            return json_result(await core.get_trade_history())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(
        name="trade_set_mode",
        description="Switch execution mode: 'paper' (built-in sim), 'paper_broker' (broker testnet/paper), 'live' (real money — requires confirm=true)",
    )
    async def trade_set_mode(mode: str, confirm: bool = False):
        try:
            return json_result(core.set_mode(mode=mode, confirm=confirm))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_get_mode", description="Show current execution mode (paper/paper_broker/live)")
    async def trade_get_mode():
        try:
            return json_result(core.get_mode())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="trade_broker_status", description="Check which brokers are configured and their connection status")
    async def trade_broker_status():
        try:
            return json_result(core.broker_status())
        except Exception as exc:
            return error_result(str(exc))
