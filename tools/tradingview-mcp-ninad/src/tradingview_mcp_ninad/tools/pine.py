"""Pine Script development tools: source editing, compile, errors, console, static analysis."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import pine as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(name="pine_get_source", description="Get the current Pine Script source code from the editor")
    async def pine_get_source():
        try:
            return json_result(await core.get_source())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pine_set_source", description="Inject Pine Script code into the editor")
    async def pine_set_source(source: str):
        try:
            return json_result(await core.set_source(source=source))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pine_compile", description="Compile the current Pine Script and add/update on chart")
    async def pine_compile():
        try:
            return json_result(await core.compile_script())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pine_smart_compile", description="Intelligent compile: detects button, compiles, checks errors, reports study changes")
    async def pine_smart_compile():
        try:
            return json_result(await core.smart_compile())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pine_get_errors", description="Read compilation errors from the Pine Script editor")
    async def pine_get_errors():
        try:
            return json_result(await core.get_errors())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pine_get_console", description="Read Pine Script console/log output")
    async def pine_get_console():
        try:
            return json_result(await core.get_console())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pine_save", description="Save the current Pine Script (Ctrl+S)")
    async def pine_save():
        try:
            return json_result(await core.save_script())
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pine_analyze", description="Run static analysis on Pine Script code WITHOUT compiling")
    async def pine_analyze(source: str):
        try:
            return json_result(core.analyze(source=source))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="pine_check", description="Compile Pine Script via TradingView's server API without needing the chart open")
    async def pine_check(source: str):
        try:
            return json_result(await core.check(source=source))
        except Exception as exc:
            return error_result(str(exc))
