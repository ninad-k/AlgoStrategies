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

## Resolved Debt

*None yet — this is the initial release.*

---

*Maintained by Ninad K.*
