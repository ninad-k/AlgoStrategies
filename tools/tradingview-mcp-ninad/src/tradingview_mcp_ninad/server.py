"""FastMCP server bootstrap.

This is the only file the ``python -m tradingview_mcp_ninad`` entry point
imports directly. It builds a single :class:`FastMCP` instance, attaches the
embedded TOOL SELECTION GUIDE, and lets each tool module register its own
handlers. Keeping registration explicit (rather than auto-discovering files)
makes the dependency graph easy to read and gives a single chokepoint where
new tool groups are wired in.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .instructions import TOOL_SELECTION_GUIDE
from .logging_config import configure_logging
from .tools import chart as chart_tools
from .tools import data as data_tools
from .tools import health as health_tools

log = configure_logging()


def build_server() -> FastMCP:
    """Construct and return a fully configured MCP server.

    Tool registration is split out so the function can be reused by tests
    that need a fresh server instance per case.
    """
    server = FastMCP(
        name="tradingview-ninad",
        instructions=TOOL_SELECTION_GUIDE,
    )
    health_tools.register(server)
    chart_tools.register(server)
    data_tools.register(server)
    log.info("server.built", tool_groups=["health", "chart", "data"])
    return server


def run() -> None:
    """Start the MCP stdio transport.

    Any exception raised during startup is logged and re-raised so the
    process exits with a non-zero status — the parent (Claude Code) will
    surface the failure to the user.
    """
    server = build_server()
    try:
        server.run()
    except Exception as exc:  # noqa: BLE001
        log.error("server.crashed", error=str(exc))
        raise
