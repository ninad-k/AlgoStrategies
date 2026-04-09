"""Replay mode tools: step, autoplay, trade, status."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import replay as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="replay_start", description="Start replay mode at a historical date (YYYY-MM-DD)")
    async def replay_start(date: str | None = None):
        try:
            return json_result(await core.start(date=date))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="replay_step", description="Step one bar forward in replay mode")
    async def replay_step():
        try:
            return json_result(await core.step())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="replay_autoplay", description="Toggle auto-advance in replay mode")
    async def replay_autoplay(speed: int | None = None):
        try:
            return json_result(await core.autoplay(speed=speed))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="replay_stop", description="Stop replay and return to live mode")
    async def replay_stop():
        try:
            return json_result(await core.stop())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="replay_trade", description="Execute a simulated trade in replay mode (buy, sell, or close)")
    async def replay_trade(action: str):
        try:
            return json_result(await core.trade(action=action))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="replay_status", description="Get current replay mode status, position, and P&L")
    async def replay_status():
        try:
            return json_result(await core.status())
        except Exception as exc:
            return error_result(str(exc))
