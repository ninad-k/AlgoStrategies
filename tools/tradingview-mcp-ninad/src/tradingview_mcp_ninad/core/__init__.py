"""Pure-logic core modules.

Tool wrappers in :mod:`tradingview_mcp_ninad.tools` are deliberately thin —
all the business logic that talks to TradingView lives here so it can be
unit-tested without spinning up an MCP server.
"""

from __future__ import annotations
