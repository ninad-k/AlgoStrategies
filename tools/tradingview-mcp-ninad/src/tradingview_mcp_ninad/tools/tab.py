"""Tab management tools: list, new, close, switch."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import tab as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="tab_list", description="List all open TradingView chart tabs")
    async def tab_list():
        try:
            return json_result(await core.list_tabs())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="tab_new", description="Open a new chart tab")
    async def tab_new():
        try:
            return json_result(await core.new_tab())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="tab_close", description="Close the current chart tab")
    async def tab_close():
        try:
            return json_result(await core.close_tab())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="tab_switch", description="Switch to a chart tab by index (0-based)")
    async def tab_switch(index: int):
        try:
            return json_result(await core.switch_tab(index=index))
        except Exception as exc:
            return error_result(str(exc))
