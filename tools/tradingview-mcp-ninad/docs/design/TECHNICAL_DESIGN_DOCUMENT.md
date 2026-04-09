# Technical Design Document — tradingview-mcp-ninad

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |
| **Status** | Approved |
| **Version** | 1.0 |

## 1. Overview

This document describes the technical design of `tradingview-mcp-ninad`, a Python MCP server that enables AI-assisted analysis of TradingView Desktop charts through Claude Code. This project was conceived and designed by Ninad K. as an original idea to bridge local TradingView Desktop sessions with AI-powered trading workflows using the Model Context Protocol.

## 2. Problem Statement

Traders using TradingView Desktop lack programmatic access to their chart data, indicator readings, and Pine Script editor. Manual chart analysis is repetitive, error-prone during volatile sessions, and does not scale across a multi-symbol watchlist. There is no existing Python-native solution that connects TradingView Desktop to an MCP-compatible AI assistant.

## 3. Proposed Solution

A local Python MCP server that:
- Connects to TradingView Desktop via Chrome DevTools Protocol (CDP) on `localhost:9222`
- Exposes 78 tools covering chart reading, Pine Script development, replay trading, and automated morning briefs
- Communicates with Claude Code over stdio using the official MCP Python SDK (FastMCP)
- Keeps all data local — zero external API dependencies beyond TradingView's own servers

## 4. Architecture

### 4.1 High-Level Architecture

```
┌─────────────┐     stdio (JSON-RPC)     ┌──────────────────┐     CDP (ws)     ┌─────────────────┐
│ Claude Code  │ ◄──────────────────────► │  MCP Server      │ ◄─────────────► │  TradingView     │
│ (AI Client)  │                          │  (Python/FastMCP) │                 │  Desktop (Electron)│
└─────────────┘                          └──────────────────┘                 └─────────────────┘
                                                  │
                                                  ▼
                                          ┌──────────────────┐
                                          │  ~/.tradingview-  │
                                          │  mcp-ninad/       │
                                          │  ├── logs/        │
                                          │  ├── sessions/    │
                                          │  └── screenshots/ │
                                          └──────────────────┘
```

### 4.2 Component Breakdown

| Component | Location | Responsibility |
|---|---|---|
| **Server Bootstrap** | `server.py` | FastMCP init, tool registration, stdio transport |
| **Connection Layer** | `connection/` | CDP singleton, retry, target discovery, API path verification |
| **Core Logic** | `core/` | 12 modules — all business logic as async functions |
| **Tool Wrappers** | `tools/` | 15 modules — thin MCP-facing decorators that call core |
| **Rules Engine** | `rules/` | Pydantic v2 model for `rules.json` validation |
| **CLI** | `cli/` | Typer-based `tv` command with 18 sub-commands |
| **Logging** | `logging_config.py` | structlog file-only sink (never stdout) |

### 4.3 Connection Lifecycle

```
get_client()
    ├── Tab cached? ──► Liveness probe (Runtime.evaluate("1"))
    │                       ├── Pass ──► Return cached tab
    │                       └── Fail ──► Drop cache, reconnect
    └── No cache ──► connect()
                        ├── HTTP GET /json/list ──► Find chart target
                        ├── pychrome.Browser ──► Attach to target
                        ├── Enable Runtime, Page, DOM domains
                        └── Cache & return tab
```

Retry policy: Tenacity exponential backoff, 5 attempts, base 0.5s, max 30s.

### 4.4 API Path Verification Pattern

TradingView's internal globals (`window.TradingViewApi._activeChartWidgetWV`, etc.) are undocumented and move between releases. The `api_resolver.py` module:

1. Takes a JS expression path (e.g., `window.TradingViewApi._activeChartWidgetWV.value()`)
2. Evaluates `typeof (path) !== 'undefined' && (path) !== null` in the page
3. Caches verified paths for the session lifetime
4. All tool code references paths through the resolver — when TV changes internals, only `KNOWN_PATHS` needs updating

### 4.5 Tool Registration Pattern

```python
# In tools/health.py
def register(server: FastMCP) -> None:
    @server.tool(name="tv_health_check", description="...")
    async def tv_health_check():
        try:
            return json_result(await core.health_check())
        except Exception as exc:
            return error_result(str(exc))
```

- Tool names are string constants matching the original server character-for-character
- Core logic is separated from MCP wiring for testability
- Every tool catches all exceptions and returns structured error JSON

## 5. Data Flow: Morning Brief

```
morning_brief(rules_path)
    │
    ├── Load rules.json ──► Validate with Pydantic
    ├── Snapshot current chart (to restore later)
    │
    ├── For each symbol in watchlist:
    │       ├── chart.set_symbol(symbol)
    │       ├── chart.set_timeframe(default_timeframe)
    │       ├── Parallel: chart.get_state() + data.get_study_values() + data.get_quote()
    │       └── Collect results
    │
    ├── Restore original chart state
    └── Return { rules, symbols_scanned[], instruction }
              ▲
              │ Claude applies bias_criteria to indicator values
              │ and generates the final brief
```

## 6. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python | AlgoStrategies repo is Python; enables direct imports from backtesting/ML modules |
| MCP SDK | FastMCP (official) | First-party support, decorator-based tool registration |
| CDP client | pychrome | Lightweight, direct CDP access, closest to original's `chrome-remote-interface` |
| Async strategy | `anyio.to_thread` wrappers | pychrome is sync; wrapping preserves FastMCP's async event loop |
| Logging | structlog → file only | MCP uses stdout for JSON-RPC; any stray print corrupts the transport |
| Config | Pydantic v2 | Schema validation on load; hot-reloadable via mtime check |
| Retry | Tenacity | Standard library for Python retries; replaces hand-rolled exponential backoff |

## 7. Security Considerations

- **Local only** — all communication is `localhost`. No data leaves the machine.
- **No credentials stored** — the server uses TradingView's existing session cookies via CDP.
- **Input sanitization** — all user-supplied strings passed to JS `evaluate()` are escaped with `str.replace("'", "\\'")`.
- **No shell execution** — except `tv_launch` which uses controlled binary paths and arguments.

## 8. Performance Targets

| Metric | Target |
|---|---|
| Cold start to first tool response | < 500 ms |
| `chart_get_state` latency | < 100 ms |
| `morning_brief` (3 symbols) | < 15 s |
| Memory footprint | < 50 MB RSS |

## 9. Dependencies

| Package | Version | Purpose |
|---|---|---|
| `mcp` | >= 1.2.0 | MCP Python SDK (FastMCP) |
| `pychrome` | >= 0.2.4 | Chrome DevTools Protocol client |
| `pydantic` | >= 2.10.0 | rules.json validation |
| `tenacity` | >= 9.0.0 | Connection retry logic |
| `structlog` | >= 24.4.0 | Structured file-only logging |
| `httpx` | >= 0.28.0 | Async HTTP for target discovery and symbol search |
| `anyio` | >= 4.6.0 | Async bridge for sync pychrome calls |
| `typer` | >= 0.15.0 | CLI framework |
| `rich` | >= 13.9.0 | CLI output formatting |

## 10. File Structure

```
tools/tradingview-mcp-ninad/
├── pyproject.toml              # Package metadata, deps, CLI entry
├── requirements.txt            # Pinned runtime deps
├── rules.example.json          # Trading rules template
├── CLAUDE.md                   # Tool selection decision tree
├── README.md                   # Setup guide + tool reference
├── scripts/                    # Platform launch scripts
├── src/tradingview_mcp_ninad/
│   ├── server.py               # FastMCP bootstrap
│   ├── instructions.py         # Embedded TOOL SELECTION GUIDE
│   ├── logging_config.py       # structlog file sink
│   ├── connection/             # CDP singleton + resolver
│   ├── core/                   # 12 business logic modules
│   ├── tools/                  # 15 MCP tool wrapper modules
│   ├── rules/                  # Pydantic config model
│   └── cli/                    # typer CLI with 18 commands
├── tests/                      # pytest test suite
└── docs/                       # Project documentation
```

---

*Designed and authored by Ninad K. This project was Ninad K.'s own original idea.*
