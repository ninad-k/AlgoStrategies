"""Drawing tools: create shapes, list, inspect properties, remove."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..core import drawing as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="draw_shape", description="Create a drawing on the chart (horizontal_line, trend_line, rectangle, text)")
    async def draw_shape(
        shape: str,
        point: dict[str, Any],
        point2: dict[str, Any] | None = None,
        overrides: str | None = None,
        text: str | None = None,
    ):
        try:
            return json_result(await core.draw_shape(shape=shape, point=point, point2=point2, overrides=overrides, text=text))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="draw_list", description="List all drawings on the chart")
    async def draw_list():
        try:
            return json_result(await core.list_drawings())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="draw_get_properties", description="Get properties and coordinate points of a drawing by entity ID")
    async def draw_get_properties(entity_id: str):
        try:
            return json_result(await core.get_properties(entity_id=entity_id))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="draw_remove_one", description="Remove a specific drawing by entity ID")
    async def draw_remove_one(entity_id: str):
        try:
            return json_result(await core.remove_one(entity_id=entity_id))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="draw_clear", description="Remove all drawings from the chart")
    async def draw_clear():
        try:
            return json_result(await core.clear_all())
        except Exception as exc:
            return error_result(str(exc))
