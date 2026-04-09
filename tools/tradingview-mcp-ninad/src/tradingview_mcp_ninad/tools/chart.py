"""Chart state, symbol/timeframe/type control, indicator management, and navigation tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import chart as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:
    """Attach all chart-related tools to *server*."""

    @server.tool(name="chart_get_state", description="Get current chart state (symbol, timeframe, chart type, indicators)")
    async def chart_get_state():
        try:
            return json_result(await core.get_state())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="chart_set_symbol", description="Change the chart symbol")
    async def chart_set_symbol(symbol: str):
        try:
            return json_result(await core.set_symbol(symbol=symbol))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="chart_set_timeframe", description="Change the chart timeframe/resolution")
    async def chart_set_timeframe(timeframe: str):
        try:
            return json_result(await core.set_timeframe(timeframe=timeframe))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(
        name="chart_set_type",
        description="Change chart type: Bars(0), Candles(1), Line(2), Area(3), Renko(4), Kagi(5), PointAndFigure(6), LineBreak(7), HeikinAshi(8), HollowCandles(9) — pass name or number",
    )
    async def chart_set_type(chart_type: str):
        try:
            return json_result(await core.set_type(chart_type=chart_type))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(
        name="chart_manage_indicator",
        description='Add or remove an indicator/study on the chart. Use full indicator names: "Relative Strength Index" not "RSI".',
    )
    async def chart_manage_indicator(
        action: str,
        indicator: str,
        entity_id: str | None = None,
        inputs: str | None = None,
    ):
        try:
            return json_result(
                await core.manage_indicator(
                    action=action, indicator=indicator,
                    entity_id=entity_id, inputs=inputs,
                )
            )
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="chart_get_visible_range", description="Get the visible date range (unix timestamps) and bars range on the chart")
    async def chart_get_visible_range():
        try:
            return json_result(await core.get_visible_range())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="chart_set_visible_range", description="Zoom the chart to a specific date range (unix timestamps)")
    async def chart_set_visible_range(from_ts: float, to_ts: float):
        try:
            return json_result(await core.set_visible_range(from_ts=from_ts, to_ts=to_ts))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="chart_scroll_to_date", description="Jump the chart view to center on a specific date")
    async def chart_scroll_to_date(date: str):
        try:
            return json_result(await core.scroll_to_date(date=date))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="symbol_info", description="Get detailed metadata about the current symbol (name, exchange, type, description)")
    async def symbol_info():
        try:
            return json_result(await core.symbol_info())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="symbol_search", description="Search for symbols by name or keyword")
    async def symbol_search(query: str, type: str | None = None):
        try:
            return json_result(await core.symbol_search(query=query, type=type))
        except Exception as exc:
            return error_result(str(exc))
