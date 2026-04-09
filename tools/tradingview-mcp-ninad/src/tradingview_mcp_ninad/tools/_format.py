"""MCP response formatting helpers.

The original project hand-rolled this for the Node MCP SDK; here we adapt to
the Python SDK by returning ``mcp.types.TextContent`` instances. ``json_result``
is the canonical way every tool emits a response so the on-the-wire shape
matches the JS version field-for-field.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.types import TextContent


def json_result(payload: Any, *, is_error: bool = False) -> list[TextContent]:
    """Encode ``payload`` as a single ``TextContent`` block of pretty JSON.

    Mirrors the JS ``jsonResult`` helper. The Python MCP SDK accepts a list of
    content blocks as a tool's return value, so we return ``[TextContent(...)]``.
    The ``is_error`` flag is wired into the JSON envelope itself because the
    Python SDK doesn't yet expose an ``isError`` field at the response level —
    the model can still see the failure clearly.
    """
    body = json.dumps(payload, indent=2, default=str)
    if is_error:
        # Mark error responses inline so callers don't have to inspect a
        # separate field. The shape stays JSON-serializable for downstream
        # tooling that pipes our output through ``jq`` and similar.
        body = json.dumps({"_error": True, "result": payload}, indent=2, default=str)
    return [TextContent(type="text", text=body)]


def error_result(message: str, **extra: Any) -> list[TextContent]:
    """Convenience helper for the ``except`` arm of every tool implementation."""
    payload: dict[str, Any] = {"success": False, "error": message}
    payload.update(extra)
    return json_result(payload, is_error=True)
