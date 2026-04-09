"""UI interaction tools: click, keyboard, type, panels, layouts, scroll, find, evaluate."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import ui as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="ui_click", description="Click a UI element by aria-label, data-name, text, or CSS selector")
    async def ui_click(selector: str):
        try:
            return json_result(await core.click(selector=selector))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="ui_keyboard", description="Press a keyboard key with optional modifiers (ctrl, alt, shift, meta)")
    async def ui_keyboard(key: str, modifiers: str | None = None):
        try:
            return json_result(await core.keyboard(key=key, modifiers=modifiers))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="ui_type_text", description="Type text into the currently focused input element")
    async def ui_type_text(text: str):
        try:
            return json_result(await core.type_text(text=text))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="ui_hover", description="Move cursor over an element to trigger hover states")
    async def ui_hover(selector: str):
        try:
            return json_result(await core.hover(selector=selector))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="ui_mouse_click", description="Click at exact pixel coordinates")
    async def ui_mouse_click(x: int, y: int, button: str = "left"):
        try:
            return json_result(await core.mouse_click(x=x, y=y, button=button))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="ui_open_panel", description="Open/toggle a TradingView panel (pine-editor, strategy-tester, watchlist, alerts, trading)")
    async def ui_open_panel(panel: str):
        try:
            return json_result(await core.open_panel(panel=panel))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="ui_fullscreen", description="Toggle fullscreen mode")
    async def ui_fullscreen():
        try:
            return json_result(await core.fullscreen())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="layout_list", description="List saved chart layouts")
    async def layout_list():
        try:
            return json_result(await core.layout_list())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="layout_switch", description="Load a saved chart layout by name or ID")
    async def layout_switch(name: str):
        try:
            return json_result(await core.layout_switch(name=name))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="ui_scroll", description="Scroll the chart viewport in a direction (up, down, left, right)")
    async def ui_scroll(direction: str, amount: int = 3):
        try:
            return json_result(await core.scroll(direction=direction, amount=amount))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="ui_find_element", description="Search for UI elements by text, aria-label, or CSS selector")
    async def ui_find_element(query: str):
        try:
            return json_result(await core.find_element(query=query))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="ui_evaluate", description="Execute arbitrary JavaScript in the page context")
    async def ui_evaluate(expression: str):
        try:
            return json_result(await core.js_evaluate(expression=expression))
        except Exception as exc:
            return error_result(str(exc))
