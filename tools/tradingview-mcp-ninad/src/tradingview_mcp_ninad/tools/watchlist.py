"""Watchlist management tools: read and add symbols."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import watchlist as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="watchlist_get", description="Get all symbols in the current watchlist with price data")
    async def watchlist_get():
        try:
            return json_result(await core.get_watchlist())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="watchlist_add", description="Add a symbol to the watchlist")
    async def watchlist_add(symbol: str):
        try:
            return json_result(await core.add_symbol(symbol=symbol))
        except Exception as exc:
            return error_result(str(exc))
