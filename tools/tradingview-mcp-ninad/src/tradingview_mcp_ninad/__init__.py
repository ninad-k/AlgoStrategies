"""Top-level package for the TradingView MCP server.

This package exposes a Model Context Protocol server that drives a locally
running TradingView Desktop window through the Chrome DevTools Protocol on
``localhost:9222``. Tool implementations live under :mod:`tradingview_mcp_ninad.tools`,
the CDP plumbing under :mod:`tradingview_mcp_ninad.connection`, and the strict
`rules.json` schema under :mod:`tradingview_mcp_ninad.rules`.
"""

from __future__ import annotations

__version__ = "0.1.0"
