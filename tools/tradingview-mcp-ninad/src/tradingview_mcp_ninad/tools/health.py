"""Health, discovery, UI introspection, and launch tools.

These four tools are the model's "is everything plugged in?" surface and the
only ones that can run before a chart is open. ``tv_launch`` in particular is
the canonical way to bootstrap a fresh session: it locates and starts the
TradingView Desktop binary with the Chrome DevTools port enabled.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import health as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:
    """Attach all health-related tools to the given FastMCP server."""

    @server.tool(
        name="tv_health_check",
        description=(
            "Check CDP connection to TradingView and return current chart state"
        ),
    )
    async def tv_health_check():
        try:
            return json_result(await core.health_check())
        except Exception as exc:  # noqa: BLE001 — surface every failure as MCP error
            return error_result(
                str(exc),
                hint=(
                    "TradingView is not running with CDP enabled. "
                    "Use the tv_launch tool to start it automatically."
                ),
            )

    @server.tool(
        name="tv_discover",
        description=(
            "Report which known TradingView API paths are available and their methods"
        ),
    )
    async def tv_discover():
        try:
            return json_result(await core.discover())
        except Exception as exc:  # noqa: BLE001
            return error_result(str(exc))

    @server.tool(
        name="tv_ui_state",
        description=(
            "Get current UI state: which panels are open, what buttons are "
            "visible/enabled/disabled"
        ),
    )
    async def tv_ui_state():
        try:
            return json_result(await core.ui_state())
        except Exception as exc:  # noqa: BLE001
            return error_result(str(exc))

    @server.tool(
        name="tv_launch",
        description=(
            "Launch TradingView Desktop with Chrome DevTools Protocol "
            "(remote debugging) enabled. Auto-detects install location on "
            "Mac, Windows, and Linux."
        ),
    )
    async def tv_launch(port: int | None = None, kill_existing: bool | None = None):
        try:
            return json_result(await core.launch(port=port, kill_existing=kill_existing))
        except Exception as exc:  # noqa: BLE001
            return error_result(str(exc))
