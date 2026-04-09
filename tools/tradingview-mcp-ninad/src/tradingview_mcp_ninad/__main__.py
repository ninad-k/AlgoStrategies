"""Module entry point.

Run with ``python -m tradingview_mcp_ninad`` to start the MCP stdio server.
This file is intentionally tiny: it delegates to :func:`tradingview_mcp_ninad.server.run`
so the heavy imports stay isolated to one place that the test suite can patch.
"""

from __future__ import annotations

from .server import run

if __name__ == "__main__":
    run()
