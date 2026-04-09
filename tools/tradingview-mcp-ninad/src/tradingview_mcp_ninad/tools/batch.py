"""Batch execution tool: run an action across multiple symbols/timeframes."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import batch as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(
        name="batch_run",
        description="Execute an action (screenshot, get_ohlcv, get_strategy_results) across multiple symbols and timeframes",
    )
    async def batch_run(
        symbols: list[str],
        action: str,
        timeframes: list[str] | None = None,
        delay_ms: int | None = None,
        ohlcv_count: int | None = None,
    ):
        try:
            return json_result(
                await core.batch_run(
                    symbols=symbols, action=action, timeframes=timeframes,
                    delay_ms=delay_ms, ohlcv_count=ohlcv_count,
                )
            )
        except Exception as exc:
            return error_result(str(exc))
