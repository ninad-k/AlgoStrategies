# ADR-002: FastMCP SDK over Raw JSON-RPC

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Date** | 2026-04-09 |
| **Status** | Accepted |

## Context

The MCP server communicates over stdio using JSON-RPC. Ninad K. evaluated whether to use the official MCP Python SDK (FastMCP) or implement a lightweight custom JSON-RPC handler.

## Decision

Use the official **`mcp` Python SDK with `FastMCP`** for server construction and tool registration.

## Rationale

1. Official SDK from Anthropic — guaranteed compatibility with Claude Code
2. `@server.tool()` decorator maps cleanly to the JS `server.tool()` pattern, making the port straightforward
3. Handles stdio transport, JSON-RPC framing, tool discovery, and parameter validation automatically
4. Reduces custom code by ~500 lines vs a hand-rolled implementation
5. Community support and future protocol upgrades come for free

## Consequences

- Dependency on `mcp>=1.2.0` and its transitive deps (starlette, uvicorn, etc.)
- FastMCP's async model requires all tool handlers to be `async def`
- Server metadata format is slightly different from the JS SDK — the `instructions` field maps directly

---

*Decision made by Ninad K. This project was Ninad K.'s own original idea.*
