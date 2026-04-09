# Technical Debt Log

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## Active Debt

### TD-001: pychrome sync calls wrapped in anyio.to_thread

**Severity:** Low
**Location:** Every CDP call site (`cdp_connection.py`, `core/capture.py`, `core/tab.py`, etc.)
**Description:** pychrome is a synchronous library. All CDP calls are wrapped in `anyio.to_thread.run_sync()` to avoid blocking FastMCP's async event loop. This adds ~1ms overhead per call and creates boilerplate wrapper functions.
**Proposed Fix:** Evaluate switching to an async CDP client (e.g., `nodriver` or `playwright._impl._cdp_session`) that natively supports async.
**Impact if not fixed:** Minimal — the overhead is negligible compared to the 30ms CDP roundtrip.

### TD-002: JS eval strings are Python f-strings

**Severity:** Low
**Location:** All `core/*.py` files
**Description:** Large JavaScript IIFEs are embedded as Python f-strings with escaped braces (`{{`, `}}`). This is harder to read, edit, and syntax-highlight than native JS files.
**Proposed Fix:** Consider moving JS templates to separate `.js` files and loading them at module init. Would need a template variable substitution system.
**Impact if not fixed:** Developer ergonomics only — the code works correctly.

### TD-003: No type stubs for pychrome

**Severity:** Low
**Location:** `connection/cdp_connection.py`
**Description:** pychrome does not ship type stubs, so mypy will report errors on `tab.Runtime.evaluate`, `tab.Page.enable`, etc.
**Proposed Fix:** Write a minimal `pychrome.pyi` stub or use `# type: ignore[attr-defined]` annotations.
**Impact if not fixed:** mypy strict mode cannot be enabled for the connection layer.

### TD-004: Alert creation is DOM-fragile

**Severity:** Medium
**Location:** `core/alerts.py::create()`
**Description:** The `alert_create` tool manipulates TradingView's alert dialog via DOM selectors and native property setters. TradingView frequently changes its CSS class names, breaking these selectors.
**Proposed Fix:** Investigate whether the pricealerts REST API supports creation (not just listing). If so, use the API directly.
**Impact if not fixed:** `alert_create` may break on TradingView updates. `alert_list` (REST API) is unaffected.

### TD-005: No mypy CI integration yet

**Severity:** Low
**Location:** `pyproject.toml`
**Description:** mypy is listed as a dev dependency but no strict config is set and CI doesn't run it.
**Proposed Fix:** Add `[tool.mypy]` section with strict settings and add to the CI pipeline.
**Impact if not fixed:** Type errors may creep in over time.

### TD-006: Pine `FIND_MONACO` relies on React fiber internals

**Severity:** Medium
**Location:** `core/pine.py`
**Description:** The Monaco editor finder walks TradingView's React fiber tree to locate the editor instance. This is deeply coupled to React's internal structure and TV's component hierarchy.
**Proposed Fix:** Monitor TradingView updates. The fiber walk has been stable across many TV versions, but a major React upgrade could break it. No better alternative exists — TV doesn't expose the editor publicly.
**Impact if not fixed:** All `pine_*` tools break if TV changes its React setup.

### TD-007: Paper broker uses last-known price for market fills

**Severity:** Low
**Location:** `execution/paper_broker.py`
**Description:** Market orders fill at the last price fed via `update_price()`. If no price has been fed for a symbol, the order fails. A real paper broker would query the exchange for current price.
**Proposed Fix:** Auto-query `quote_get` from the chart when no price is cached. Would add a dependency from execution→core→connection which is currently avoided.
**Impact if not fixed:** Users must call `quote_get` before their first paper trade on a symbol.

### TD-008: Binance close_position not implemented

**Severity:** Medium
**Location:** `execution/brokers/binance_broker.py`
**Description:** Binance spot doesn't have "positions" — only balances. The `close_position` method returns an error asking users to place an opposite order instead.
**Proposed Fix:** Add internal position tracking in the Binance adapter (buy 0.1 BTC → track → sell 0.1 BTC to "close"). Alternatively, support Binance futures which do have positions.
**Impact if not fixed:** `trade_close` doesn't work for Binance. Users must use `trade_execute` with the opposite side.

### TD-009: ExecutionManager is a module-level singleton

**Severity:** Low
**Location:** `execution/manager.py`
**Description:** `get_manager()` returns a module-level singleton. This works for the stdio server (one process per session) but makes unit testing harder since state persists across test cases.
**Proposed Fix:** Accept the manager via dependency injection or add a `reset_manager()` function for tests.
**Impact if not fixed:** Test isolation requires careful teardown.

## Resolved Debt

*None yet.*

---

*Maintained by Ninad K.*
