"""Screenshot capture tool."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import capture as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="capture_screenshot", description="Take a screenshot of the TradingView chart")
    async def capture_screenshot(
        region: str | None = None,
        filename: str | None = None,
        method: str | None = None,
    ):
        try:
            return json_result(await core.capture_screenshot(region=region, filename=filename, method=method))
        except Exception as exc:
            return error_result(str(exc))
