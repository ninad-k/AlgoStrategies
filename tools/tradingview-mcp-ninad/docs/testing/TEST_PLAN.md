# Test Plan

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## Test Cases

### Unit: Rules Config Validation

| ID | Test Case | Input | Expected |
|---|---|---|---|
| U-001 | Valid rules.json | Complete JSON with all fields | `RulesConfig` object with correct values |
| U-002 | Missing optional fields | JSON with only `watchlist` | Defaults applied: timeframe="240", empty arrays |
| U-003 | Empty watchlist | `{"watchlist": []}` | Valid model, empty list |
| U-004 | Invalid JSON | Malformed string | `ValidationError` raised |
| U-005 | Extra fields ignored | JSON with unknown keys | Valid model, extras dropped |

### Unit: Pine Static Analysis

| ID | Test Case | Input | Expected |
|---|---|---|---|
| U-010 | Array OOB access | `array.get(arr, 5)` on size-3 array | Error diagnostic at correct line |
| U-011 | .first() on empty array | `arr.first()` where arr size=0 | Warning diagnostic |
| U-012 | strategy.entry without strategy() | Script with entry but no declaration | Error diagnostic |
| U-013 | Old Pine version | `//@version=3` | Info diagnostic suggesting upgrade |
| U-014 | Clean script | Valid v6 indicator | `issue_count: 0` |

### Unit: Response Formatting

| ID | Test Case | Input | Expected |
|---|---|---|---|
| U-020 | Success result | `json_result({"success": True})` | `[TextContent(text='{"success": true}')]` |
| U-021 | Error result | `error_result("failed")` | JSON with `_error: true` wrapper |

### Tool Dispatch: Health

| ID | Test Case | Expected |
|---|---|---|
| T-001 | `tv_health_check` success | Calls `core.health_check()`, wraps in `json_result` |
| T-002 | `tv_health_check` failure | Catches exception, returns `error_result` with hint |

### Integration: CDP Connection

| ID | Test Case | Precondition | Expected |
|---|---|---|---|
| I-001 | Connect to running browser | Chromium on port 9222 | `get_client()` returns live tab |
| I-002 | Evaluate simple expression | Connected | `evaluate("1+1")` returns `2` |
| I-003 | Liveness probe | Connected | `evaluate("1")` succeeds |
| I-004 | Reconnect after disconnect | Tab closed externally | Next `get_client()` reconnects |
| I-005 | No target available | No browser running | `CdpConnectionError` raised |

### End-to-End: MCP Server

| ID | Test Case | Method | Expected |
|---|---|---|---|
| E-001 | Server starts | `python -m tradingview_mcp_ninad` | Process starts, no stdout except MCP frames |
| E-002 | Tool listing | MCP `tools/list` request | 78 tools returned |
| E-003 | Health check from Claude Code | `tv_health_check` | Structured JSON response |

---

*Authored by Ninad K.*
