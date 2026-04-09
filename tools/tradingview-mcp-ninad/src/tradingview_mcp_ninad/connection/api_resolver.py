"""Verified accessors for TradingView's undocumented internal APIs.

The desktop app exposes a handful of globals that the server pokes at to read
chart state, drive replay, manage alerts, etc. Those globals move around
between TradingView releases, so every accessor checks that the JS path is
actually defined before returning it. The result is cached so subsequent
calls within a session pay the cost exactly once.

When TradingView moves a path, only the strings in :data:`KNOWN_PATHS` need
to change — every tool keeps working without edits.
"""

from __future__ import annotations

from .cdp_connection import evaluate

# Known JS paths into TradingView's internals. Update this dict when TV
# rearranges its globals; the rest of the codebase reads through helpers
# below so any rename ripples automatically.
KNOWN_PATHS: dict[str, str] = {
    "chart_api": "window.TradingViewApi._activeChartWidgetWV.value()",
    "chart_widget_collection": "window.TradingViewApi._chartWidgetCollection",
    "bottom_widget_bar": "window.TradingView.bottomWidgetBar",
    "replay_api": "window.TradingViewApi._replayApi",
    "alert_service": "window.TradingViewApi._alertService",
    "chart_api_instance": "window.ChartApiInstance",
    "main_series_bars": (
        "window.TradingViewApi._activeChartWidgetWV.value()"
        "._chartWidget.model().mainSeries().bars()"
    ),
    "strategy_study": "chart._chartWidget.model().model().dataSources()",
    "layout_manager": "window.TradingViewApi.getSavedCharts",
    "symbol_search_api": "window.TradingViewApi.searchSymbols",
    "pine_facade_api": "https://pine-facade.tradingview.com/pine-facade",
}

# Cache of paths that have been verified during this process. ``None`` means
# unverified, a string means verified-and-good, and a missing key means we
# have not tried yet.
_verified: dict[str, str] = {}


async def _verify_and_return(path: str, name: str) -> str:
    """Confirm ``path`` is reachable in the page and memoize the result."""
    if path in _verified:
        return _verified[path]
    exists = await evaluate(f"typeof ({path}) !== 'undefined' && ({path}) !== null")
    if not exists:
        raise RuntimeError(f"{name} not available at {path}")
    _verified[path] = path
    return path


async def get_chart_api() -> str:
    """Return the JS path for the active chart widget API."""
    return await _verify_and_return(KNOWN_PATHS["chart_api"], "Chart API")


async def get_chart_collection() -> str:
    """Return the JS path for the multi-chart widget collection."""
    return await _verify_and_return(
        KNOWN_PATHS["chart_widget_collection"], "Chart Widget Collection"
    )


async def get_bottom_bar() -> str:
    """Return the JS path for the bottom widget bar (Pine editor, console, …)."""
    return await _verify_and_return(KNOWN_PATHS["bottom_widget_bar"], "Bottom Widget Bar")


async def get_replay_api() -> str:
    """Return the JS path for the replay-mode controller."""
    return await _verify_and_return(KNOWN_PATHS["replay_api"], "Replay API")


async def get_main_series_bars() -> str:
    """Return the JS path for the main symbol's underlying bar buffer."""
    return await _verify_and_return(KNOWN_PATHS["main_series_bars"], "Main Series Bars")


def reset_cache() -> None:
    """Forget every previously verified path.

    Tests use this to start each scenario from a clean slate. Production code
    has no reason to call it; the resolver is happy to keep its cache for the
    lifetime of the process.
    """
    _verified.clear()
