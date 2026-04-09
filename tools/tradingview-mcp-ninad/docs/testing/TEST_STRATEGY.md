# Test Strategy

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## Scope

This document defines the overall testing approach for tradingview-mcp-ninad.

## Test Levels

### 1. Unit Tests (`tests/unit/`)

Test pure logic in isolation — no CDP, no TradingView.

| Target | What's Tested |
|---|---|
| `rules/config.py` | Pydantic model validates correct JSON, rejects malformed input |
| `core/pine.py::analyze()` | Static analysis catches array OOB, strategy misuse, version warnings |
| `tools/_format.py` | `json_result` and `error_result` produce correct MCP response shapes |
| `connection/api_resolver.py` | Cache behavior — verified path remembered, unverified path probed |
| `core/morning.py::save_session/get_session` | File I/O round-trip for sessions |

**Mocking:** CDP calls are mocked with `pytest-mock` / `unittest.mock.AsyncMock`.

### 2. Tool Dispatch Tests (`tests/tools/`)

Verify that the MCP tool layer correctly delegates to core and formats responses.

| What's Tested |
|---|
| Each `register()` function attaches tools with correct names |
| Tool handlers catch exceptions and return `error_result` |
| Parameter types are correctly forwarded to core functions |

**Mocking:** Core functions are patched; no real CDP.

### 3. Integration Tests (`tests/integration/`)

Test the CDP connection against a real browser target.

| What's Tested |
|---|
| `connect()` finds a page target and attaches |
| `evaluate("1+1")` returns `2` |
| `get_client()` liveness probe works |
| Reconnect after tab closure |

**Requires:** Any Chromium-based browser running with `--remote-debugging-port=9222`. Does NOT require TradingView.

## Test Tools

| Tool | Purpose |
|---|---|
| `pytest` | Test runner |
| `pytest-asyncio` | Async test support |
| `pytest-mock` | Mocking helpers |

## Entry / Exit Criteria

| Phase | Entry | Exit |
|---|---|---|
| Unit tests | Code compiles, imports resolve | All unit tests pass, no regressions |
| Integration tests | A Chromium target is running on port 9222 | CDP connect/eval/disconnect cycle succeeds |
| Acceptance | Server registered in Claude Code | `tv_health_check` returns success from Claude Code |

## Running Tests

```bash
# All tests
pytest

# Unit only
pytest tests/unit -q

# Integration only (requires browser on port 9222)
pytest tests/integration -q
```

---

*Authored by Ninad K.*
