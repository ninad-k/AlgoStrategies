"""Data access tools: OHLCV, indicators, strategy tester, quotes, Pine drawings."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import data as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:
    """Attach all data-related tools to *server*."""

    @server.tool(
        name="data_get_ohlcv",
        description="Get OHLCV bar data from the chart. Use summary=true for compact stats instead of all bars (saves context).",
    )
    async def data_get_ohlcv(count: int | None = None, summary: bool | None = None):
        try:
            return json_result(await core.get_ohlcv(count=count, summary=summary))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="data_get_indicator", description="Get indicator/study info and input values")
    async def data_get_indicator(entity_id: str):
        try:
            return json_result(await core.get_indicator(entity_id=entity_id))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="data_get_strategy_results", description="Get strategy performance metrics from Strategy Tester")
    async def data_get_strategy_results():
        try:
            return json_result(await core.get_strategy_results())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="data_get_trades", description="Get trade list from Strategy Tester")
    async def data_get_trades(max_trades: int | None = None):
        try:
            return json_result(await core.get_trades(max_trades=max_trades))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="data_get_equity", description="Get equity curve data from Strategy Tester")
    async def data_get_equity():
        try:
            return json_result(await core.get_equity())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="quote_get", description="Get real-time quote data for a symbol (price, OHLC, volume)")
    async def quote_get(symbol: str | None = None):
        try:
            return json_result(await core.get_quote(symbol=symbol))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(
        name="depth_get",
        description="Get order book / DOM (Depth of Market) data from the chart",
    )
    async def depth_get():
        try:
            return json_result(await core.get_depth())
        except Exception as exc:
            return error_result(str(exc), hint="Open the DOM panel in TradingView before using this tool.")

    @server.tool(
        name="data_get_pine_lines",
        description="Read horizontal price levels drawn by Pine Script indicators (line.new). Use study_filter to target a specific indicator.",
    )
    async def data_get_pine_lines(study_filter: str | None = None, verbose: bool | None = None):
        try:
            return json_result(await core.get_pine_lines(study_filter=study_filter, verbose=verbose))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(
        name="data_get_pine_labels",
        description="Read text labels drawn by Pine Script indicators (label.new). Use study_filter to target a specific indicator.",
    )
    async def data_get_pine_labels(
        study_filter: str | None = None,
        max_labels: int | None = None,
        verbose: bool | None = None,
    ):
        try:
            return json_result(
                await core.get_pine_labels(study_filter=study_filter, max_labels=max_labels, verbose=verbose)
            )
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(
        name="data_get_pine_tables",
        description="Read table data drawn by Pine Script indicators (table.new). Use study_filter to target a specific indicator.",
    )
    async def data_get_pine_tables(study_filter: str | None = None):
        try:
            return json_result(await core.get_pine_tables(study_filter=study_filter))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(
        name="data_get_pine_boxes",
        description="Read box/zone boundaries drawn by Pine Script indicators (box.new). Use study_filter to target a specific indicator.",
    )
    async def data_get_pine_boxes(study_filter: str | None = None, verbose: bool | None = None):
        try:
            return json_result(await core.get_pine_boxes(study_filter=study_filter, verbose=verbose))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(
        name="data_get_study_values",
        description="Get current indicator values from the data window for all visible studies (RSI, MACD, Bollinger Bands, EMAs, custom indicators with plot()).",
    )
    async def data_get_study_values():
        try:
            return json_result(await core.get_study_values())
        except Exception as exc:
            return error_result(str(exc))
