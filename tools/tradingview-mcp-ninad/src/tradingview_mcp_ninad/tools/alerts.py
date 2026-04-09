"""Alert management tools: create, list, delete."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import alerts as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="alert_create", description="Create a price alert with condition, price level, and optional message")
    async def alert_create(price: float, condition: str | None = None, message: str | None = None):
        try:
            return json_result(await core.create(condition=condition, price=price, message=message))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="alert_list", description="List all active alerts")
    async def alert_list():
        try:
            return json_result(await core.list_alerts())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="alert_delete", description="Delete alerts (set delete_all=true to remove all)")
    async def alert_delete(delete_all: bool = False):
        try:
            return json_result(await core.delete_alerts(delete_all=delete_all))
        except Exception as exc:
            return error_result(str(exc))
