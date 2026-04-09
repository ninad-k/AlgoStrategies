"""CDP plumbing — singleton connection, target discovery, API path resolution.

Public surface intentionally narrow: callers should depend on the high-level
helpers (:func:`get_client`, :func:`evaluate`, :func:`evaluate_async`) and on
the path constants in :mod:`tradingview_mcp_ninad.connection.api_resolver`.
Direct ``pychrome`` access is reserved for the connection module itself so
TradingView's brittle internals stay isolated to one place.
"""

from __future__ import annotations

from .api_resolver import (
    KNOWN_PATHS,
    get_bottom_bar,
    get_chart_api,
    get_chart_collection,
    get_main_series_bars,
    get_replay_api,
)
from .cdp_connection import (
    connect,
    disconnect,
    evaluate,
    evaluate_async,
    get_client,
    get_target_info,
)

__all__ = [
    "KNOWN_PATHS",
    "connect",
    "disconnect",
    "evaluate",
    "evaluate_async",
    "get_bottom_bar",
    "get_chart_api",
    "get_chart_collection",
    "get_client",
    "get_main_series_bars",
    "get_replay_api",
    "get_target_info",
]
