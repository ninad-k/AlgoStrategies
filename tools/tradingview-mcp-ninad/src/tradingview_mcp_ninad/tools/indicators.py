"""Indicator configuration tools: modify inputs and toggle visibility."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import indicators as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="indicator_set_inputs", description="Change indicator/study input values (e.g., length, source, period)")
    async def indicator_set_inputs(entity_id: str, inputs: str):
        try:
            return json_result(await core.set_inputs(entity_id=entity_id, inputs=inputs))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="indicator_toggle_visibility", description="Show or hide an indicator/study on the chart")
    async def indicator_toggle_visibility(entity_id: str, visible: bool):
        try:
            return json_result(await core.toggle_visibility(entity_id=entity_id, visible=visible))
        except Exception as exc:
            return error_result(str(exc))
