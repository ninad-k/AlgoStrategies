# Developer Onboarding Guide

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was conceived and built by Ninad K. as an original idea.

## Welcome

This guide gets new developers productive on tradingview-mcp-ninad in under 30 minutes.

## What This Project Does

tradingview-mcp-ninad is a Python MCP server that lets Claude Code read and control TradingView Desktop charts locally. It connects via Chrome DevTools Protocol and exposes 78 tools for chart analysis, Pine Script development, and automated trading workflows.

## Quick Start (5 minutes)

```bash
cd AlgoStrategies/tools/tradingview-mcp-ninad
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
tv --help                    # Should show 18 commands
ruff check src/              # Should pass
```

## Understand the Architecture (10 minutes)

Read these files in order:
1. `README.md` — what it does, how to use it
2. `CLAUDE.md` — the tool selection decision tree (this is what the AI model sees)
3. `src/tradingview_mcp_ninad/server.py` — how tools are registered
4. `src/tradingview_mcp_ninad/connection/cdp_connection.py` — how we talk to TradingView
5. `src/tradingview_mcp_ninad/connection/api_resolver.py` — the "verifyAndReturn" pattern

## Key Concepts

### The CDP Bridge
TradingView Desktop is an Electron app. We connect to its internal Chromium via CDP on port 9222 and run JavaScript in the page context using `Runtime.evaluate`.

### The API Resolver
TradingView's internal globals (`window.TradingViewApi._activeChartWidgetWV`, etc.) are undocumented and can change between releases. The `api_resolver.py` caches verified paths so all tool code goes through one abstraction. When TV moves a global, update `KNOWN_PATHS` — nothing else changes.

### Tool Structure: Three Layers
```
tools/health.py     → Thin MCP wrapper: @server.tool decorator + try/except
core/health.py      → Business logic: JS eval + response shaping
connection/         → CDP plumbing: singleton tab, retry, evaluate
```

New features go in `core/`, get a thin wrapper in `tools/`, and register in `server.py`.

### The stdio Contract
The MCP server communicates over stdout (JSON-RPC). **Never print to stdout.** All logging goes to `~/.tradingview-mcp-ninad/logs/server.log` via structlog.

## Adding a New Tool

1. Add the core logic in `core/<module>.py`
2. Add the MCP wrapper in `tools/<module>.py`
3. If it's a new module, import and register in `server.py`
4. Run `ruff check src/` and verify the tool appears in `tv_health_check`

## Running Tests

```bash
pytest tests/unit -q          # Pure logic tests (no TradingView needed)
pytest tests/integration -q   # Needs Chromium on port 9222
```

## Key Files to Know

| File | Why |
|---|---|
| `server.py` | Where everything is wired together |
| `connection/cdp_connection.py` | If CDP is acting up, start here |
| `connection/api_resolver.py` | If TV updated and tools broke, update KNOWN_PATHS here |
| `core/morning.py` | The flagship morning brief workflow |
| `instructions.py` | The TOOL SELECTION GUIDE that steers the AI model |
| `logging_config.py` | If logs are missing or stdout is corrupted |

## Team Conventions

- All code in `src/tradingview_mcp_ninad/`
- Snake_case everywhere
- Type hints on public functions
- Docstrings on modules and public functions (explain "why", not "what")
- No AI tool names in code comments (per AGENTS.md)
- Tool names are stable API contracts — never rename without a major version bump

---

*Authored by Ninad K.*
