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

### Unit: Execution Config

| ID | Test Case | Input | Expected |
|---|---|---|---|
| U-030 | Default config | No file | Paper mode, $100k balance, all limits set |
| U-031 | Valid config | Complete JSON | All fields parsed correctly |
| U-032 | Missing brokers | JSON without brokers section | Defaults applied |

### Unit: Paper Broker

| ID | Test Case | Input | Expected |
|---|---|---|---|
| U-040 | Market buy with price | Feed price, place order | Fill at fed price, position created |
| U-041 | Market buy no price | No price fed | Error: "No price available" |
| U-042 | Close position | Open + close | P&L calculated, balance updated |
| U-043 | Position limit reached | Open max_open_positions + 1 | Rejected with limit error |
| U-044 | Trade history | Open + close | 1 entry in history with correct fields |

### Unit: ExecutionManager

| ID | Test Case | Input | Expected |
|---|---|---|---|
| U-050 | Symbol classification | "BTCUSD" | "crypto" |
| U-051 | Symbol classification | "AAPL" | "stocks" |
| U-052 | Symbol classification | "EURUSD" | "forex" |
| U-053 | Symbol classification | "ES1!" | "futures" |
| U-054 | Mode switching to paper | set_mode("paper") | Success, mode = paper |
| U-055 | Mode switching to live (no confirm) | set_mode("live") | Rejected, needs confirmation |
| U-056 | Mode switching to live (confirmed) | set_mode_confirmed("live") | Success, mode = live |

### End-to-End: MCP Server

| ID | Test Case | Method | Expected |
|---|---|---|---|
| E-001 | Server starts | `python -m tradingview_mcp_ninad` | Process starts, no stdout except MCP frames |
| E-002 | Tool listing | MCP `tools/list` request | 90 tools returned |
| E-003 | Health check from Claude Code | `tv_health_check` | Structured JSON response |

### End-to-End: Paper Trade Round-Trip

| ID | Test Case | Method | Expected |
|---|---|---|---|
| E-010 | Check mode | `trade_get_mode` | `mode: "paper"` |
| E-011 | Check account | `trade_account` | Balance = $100,000 |
| E-012 | Feed price + buy | `update_price` + `trade_execute` | Fill with ticket, price, quantity |
| E-013 | List positions | `trade_positions` | 1 position with correct fields |
| E-014 | P&L update | Update price + `trade_positions` | `unrealized_pnl` reflects change |
| E-015 | Close position | `trade_close` | `pnl` calculated, position removed |
| E-016 | Final balance | `trade_account` | Balance = starting + realized P&L |
| E-017 | Trade history | `trade_history` | 1 closed trade with all fields |

---

*Authored by Ninad K.*
