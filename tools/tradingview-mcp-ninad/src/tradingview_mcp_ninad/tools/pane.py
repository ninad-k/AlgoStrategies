"""Multi-pane layout management tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import pane as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="pane_list", description="List all chart panes in the current layout with their symbols and active state")
    async def pane_list():
        try:
            return json_result(await core.list_panes())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pane_set_layout", description="Change the chart grid layout (s, 2h, 2v, 2x2, 4, 6, 8)")
    async def pane_set_layout(layout: str):
        try:
            return json_result(await core.set_layout(layout=layout))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pane_focus", description="Focus a specific chart pane by index (0-based)")
    async def pane_focus(index: int):
        try:
            return json_result(await core.focus(index=index))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pane_set_symbol", description="Set the symbol on a specific pane by index")
    async def pane_set_symbol(index: int, symbol: str):
        try:
            return json_result(await core.set_symbol(index=index, symbol=symbol))
        except Exception as exc:
            return error_result(str(exc))
