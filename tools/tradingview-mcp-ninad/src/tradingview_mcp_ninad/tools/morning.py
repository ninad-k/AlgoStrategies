"""Morning brief workflow tools: scan, save, and retrieve session briefs."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import morning as core
from ._format import error_result, json_result


def register(server: FastMCP) -> None:

    @server.tool(
        name="morning_brief",
        description="Scan watchlist symbols, read indicators, and apply rules.json to generate a daily session bias assessment",
    )
    async def morning_brief(rules_path: str | None = None):
        try:
            return json_result(await core.run_brief(rules_path=rules_path))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="session_save", description="Save today's morning brief to a session file")
    async def session_save(brief: str, date: str | None = None):
        try:
            return json_result(core.save_session(brief=brief, date=date))
        except Exception as exc:
            return error_result(str(exc))

    @server.tool(name="session_get", description="Retrieve a saved session brief (defaults to today or yesterday)")
    async def session_get(date: str | None = None):
        try:
            return json_result(core.get_session(date=date))
        except Exception as exc:
            return error_result(str(exc))
