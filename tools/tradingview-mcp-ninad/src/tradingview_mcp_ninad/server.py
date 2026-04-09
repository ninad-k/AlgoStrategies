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
from .tools import alerts as alerts_tools
from .tools import batch as batch_tools
from .tools import capture as capture_tools
from .tools import chart as chart_tools
from .tools import data as data_tools
from .tools import drawing as drawing_tools
from .tools import execution as execution_tools
from .tools import health as health_tools
from .tools import indicators as indicators_tools
from .tools import morning as morning_tools
from .tools import pane as pane_tools
from .tools import pine as pine_tools
from .tools import replay as replay_tools
from .tools import tab as tab_tools
from .tools import ui as ui_tools
from .tools import watchlist as watchlist_tools

log = configure_logging()

_TOOL_GROUPS = [
    ("health", health_tools),
    ("chart", chart_tools),
    ("data", data_tools),
    ("indicators", indicators_tools),
    ("pine", pine_tools),
    ("replay", replay_tools),
    ("morning", morning_tools),
    ("watchlist", watchlist_tools),
    ("batch", batch_tools),
    ("capture", capture_tools),
    ("drawing", drawing_tools),
    ("alerts", alerts_tools),
    ("pane", pane_tools),
    ("tab", tab_tools),
    ("ui", ui_tools),
    ("execution", execution_tools),
]


def build_server() -> FastMCP:
    """Construct and return a fully configured MCP server.

    Tool registration is split out so the function can be reused by tests
    that need a fresh server instance per case.
    """
    server = FastMCP(
        name="tradingview-ninad",
        instructions=TOOL_SELECTION_GUIDE,
    )
    for name, module in _TOOL_GROUPS:
        module.register(server)
    log.info("server.built", tool_groups=[n for n, _ in _TOOL_GROUPS])
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
