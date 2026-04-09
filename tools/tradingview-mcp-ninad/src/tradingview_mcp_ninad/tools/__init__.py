"""MCP tool modules.

Each submodule mirrors one file in the original Node project's ``src/tools/``
directory and exposes a single ``register(server)`` function that the central
:mod:`tradingview_mcp_ninad.server` module calls during startup. Tool *names*
are stable contracts — they must match the JS originals so prompts and
external automation keep working.
"""

from __future__ import annotations
