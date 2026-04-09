# Code Walkthrough

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## How a Tool Call Flows Through the System

Let's trace `chart_get_state` from Claude Code all the way to TradingView and back.

### 1. Claude Code sends an MCP request

```json
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "chart_get_state", "arguments": {}}, "id": 1}
```

This arrives on the Python process's **stdin**.

### 2. FastMCP dispatches to the registered handler

In `tools/chart.py`:
```python
@server.tool(name="chart_get_state", description="...")
async def chart_get_state():
    try:
        return json_result(await core.get_state())
    except Exception as exc:
        return error_result(str(exc))
```

### 3. Core logic builds a JS IIFE and evaluates it

In `core/chart.py`:
```python
async def get_state() -> dict:
    state = await evaluate(f"""
        (function() {{
          var chart = {CHART_API};
          var studies = chart.getAllStudies().map(s => {{ ... }});
          return {{ symbol: chart.symbol(), resolution: chart.resolution(), ... }};
        }})()
    """)
    return {"success": True, **state}
```

### 4. `evaluate()` ensures a live CDP connection

In `connection/cdp_connection.py`:
```python
async def evaluate(expression, *, await_promise=False):
    tab = await get_client()           # ← Liveness probe + reconnect if needed
    return await _evaluate_raw(tab, expression)
```

### 5. `get_client()` checks the cached tab

```python
async def get_client():
    if _tab is not None:
        try:
            await _evaluate_raw(_tab, "1")   # ← Liveness probe
            return _tab                       # ← Cache hit
        except:
            _reset_state()                   # ← Stale, reconnect
    return await connect()                    # ← Cache miss
```

### 6. pychrome sends the CDP command over WebSocket

```python
async def _evaluate_raw(tab, expression):
    def _call():
        return tab.Runtime.evaluate(expression=expression, returnByValue=True)
    result = await anyio.to_thread.run_sync(_call)   # ← Sync → async bridge
    return result.get("result", {}).get("value")
```

### 7. TradingView executes the JS and returns the result

The JS IIFE runs in TradingView's page context, accesses the chart widget's internal API, and returns a serialized object.

### 8. Response flows back up

```
TradingView → CDP WebSocket → pychrome → _evaluate_raw → evaluate → core.get_state → tools.chart_get_state → json_result → FastMCP → stdout JSON-RPC → Claude Code
```

## How a Trade Flows Through the System

```
trade_execute(symbol="BTCUSD", side="buy", quantity=0.1)
    │
    ├── tools/execution.py → @server.tool wrapper, try/except
    ├── core/execution.py → builds OrderIntent, calls get_manager()
    ├── execution/manager.py → checks limits, routes by mode
    │       ├── mode == "paper" → paper_broker.place_order()
    │       └── mode != "paper" → _classify_symbol() → pick broker → broker.place_order()
    ├── execution/paper_broker.py → fills at last known price, creates Position
    └── Returns FillResult → json_result → FastMCP → stdout → Claude Code
```

Key difference from chart tools: execution does NOT go through CDP. It either uses the in-memory paper broker or calls broker APIs (Alpaca REST, Binance WS, MT5 C API, IBKR TWS).

## Module Dependency Graph

```
server.py
    ├── instructions.py (TOOL_SELECTION_GUIDE string)
    ├── logging_config.py (structlog setup)
    ├── tools/*.py (16 modules)
    │       └── core/*.py (13 modules)
    │               ├── connection/cdp_connection.py
    │               ├── connection/api_resolver.py
    │               └── connection/__init__.py (re-exports)
    └── tools/execution.py → core/execution.py
                                    └── execution/ (separate from connection/)
                                            ├── manager.py (routing + limits)
                                            ├── paper_broker.py (in-memory sim)
                                            ├── protocol.py (BrokerProtocol interface)
                                            ├── config.py (Pydantic config)
                                            └── brokers/ (alpaca, binance, mt5, ibkr)
```

## The Four Layers Explained

### Layer 1: `tools/*.py` — MCP Surface
- One file per category (health, chart, data, ...)
- Each file has a `register(server)` function
- Each tool is an `async def` decorated with `@server.tool(name="...")`
- Catches ALL exceptions and wraps them in `error_result()`
- No business logic here — just delegation

### Layer 2: `core/*.py` — Business Logic
- One file per category, matching the tools layer
- Pure async functions that take keyword args and return dicts
- Contains the JS IIFE strings that run inside TradingView
- Can be called from both MCP tools and the CLI
- Raises exceptions on failure (tools layer catches them)

### Layer 3: `connection/*.py` — CDP Plumbing
- `cdp_connection.py`: Singleton tab, retry, evaluate, disconnect
- `api_resolver.py`: KNOWN_PATHS dict + verify-and-cache
- `__init__.py`: Clean re-exports so callers do `from ..connection import evaluate`

### Layer 4: `execution/*.py` — Trade Execution (independent of CDP)
- `protocol.py`: BrokerProtocol interface + data models (OrderIntent, FillResult, Position, etc.)
- `paper_broker.py`: In-memory simulator with P&L tracking, SL/TP, trade logging to disk
- `manager.py`: ExecutionManager singleton — routes orders by symbol class, enforces limits, gates modes
- `config.py`: Pydantic-validated `execution_config.json` (brokers, routing, safety)
- `brokers/`: One adapter per broker, all implementing BrokerProtocol
  - Each uses lazy imports so broker SDKs aren't required unless that broker is used
  - All blocking calls wrapped in `asyncio.to_thread` for async compatibility

## Why JS Eval Strings Are Wrapped in IIFEs

```javascript
(function() {
  var chart = window.TradingViewApi._activeChartWidgetWV.value();
  return { symbol: chart.symbol() };
})()
```

1. **IIFE** prevents variable leakage into the page's global scope
2. **`var`** instead of `let/const` — TradingView's page may be in strict mode or not; `var` always works
3. **Single eval** — batching all reads into one CDP call saves 30ms per roundtrip
4. **returnByValue: true** — serializes the result, no remote object handles to manage

---

*Authored by Ninad K.*
