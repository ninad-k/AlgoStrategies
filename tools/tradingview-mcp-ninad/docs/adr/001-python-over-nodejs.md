# ADR-001: Python over Node.js for the MCP Server

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Date** | 2026-04-09 |
| **Status** | Accepted |

## Context

Ninad K. conceived the idea to build a Python-native MCP server for TradingView Desktop as part of the AlgoStrategies project. The original reference implementation (tradingview-mcp-jackson) was written in Node.js. A decision was needed on which language would best serve this project's goals.

## Decision

Build the MCP server in **Python 3.11+** using FastMCP, pychrome, and pydantic.

## Alternatives Considered

| Language | Pros | Cons |
|---|---|---|
| **Node.js** | Closest to original; zero-impedance with TV's JS runtime | Foreign to AlgoStrategies repo; duplicate toolchain |
| **Python** | Native to AlgoStrategies; enables direct imports from backtesting/ML; mature MCP SDK | pychrome is sync (requires anyio wrappers) |
| **.NET 9** | Strong typing, Native AOT | No existing .NET in repo; heaviest friction |
| **Go** | Fast binary, single deploy | Foreign ecosystem; immature MCP SDK |

## Rationale

1. AlgoStrategies is a Python-first repo (freqtrade, backtesting, ML models, dashboards)
2. Future tools can `import` from `risk_management`, `backtesting.metrics`, `models` directly
3. Python MCP SDK (FastMCP) is mature with decorator-based tool registration
4. Single toolchain (pip, pytest, ruff) across the entire project
5. The team already writes Python daily — no ramp-up cost

## Consequences

- pychrome CDP calls are synchronous and must be wrapped with `anyio.to_thread.run_sync()` to avoid blocking FastMCP's async event loop
- Cold start is ~200-400ms (vs ~80ms for Node) — acceptable for a stdio server spawned per session
- JS eval payloads are strings in Python f-strings, which is slightly less ergonomic than JS template literals

---

*Decision made by Ninad K. This project was Ninad K.'s own original idea.*
