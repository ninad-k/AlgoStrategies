# Spike: Async CDP Client Alternatives

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Date** | 2026-04-09 |
| **Status** | Complete |
| **Time-boxed** | 2 hours |

> This project was Ninad K.'s own original idea.

## Question

Should we replace pychrome (sync) with an async CDP client to eliminate the `anyio.to_thread` wrappers?

## Context

pychrome is synchronous. Every CDP call is wrapped in `anyio.to_thread.run_sync()` to avoid blocking FastMCP's async event loop. This works but adds boilerplate and ~1ms overhead per call.

## Options Investigated

### Option A: Keep pychrome + anyio wrappers (Current)

**Pros:** Already working, battle-tested in production, minimal dependency surface
**Cons:** Boilerplate wrappers, can't use CDP events efficiently
**Effort:** Zero (status quo)

### Option B: Switch to nodriver

**Pros:** Async-native, modern, actively maintained
**Cons:** Heavier API surface, designed for full browser automation (overkill)
**Effort:** Medium — rewrite `cdp_connection.py` + all thread wrapper sites

### Option C: Switch to playwright CDP session

**Pros:** Async, well-maintained, excellent typing
**Cons:** Downloads a full browser binary (~150MB), massive transitive deps, private API (`_impl._cdp_session`)
**Effort:** Large — and using private APIs is a maintenance risk

### Option D: Raw websockets + httpx

**Pros:** No external CDP library at all, fully async, minimal deps
**Cons:** Must implement CDP framing, message ID tracking, domain management manually
**Effort:** Large — effectively writing our own CDP client

## Recommendation

**Stay with Option A (pychrome + anyio wrappers).** The 1ms overhead is negligible against the 30ms CDP roundtrip. The boilerplate is tolerable (a dozen wrapper functions). No option offers enough benefit to justify the migration risk.

Revisit if:
- We need CDP events (websocket push) for real-time streaming
- pychrome stops being maintained
- The thread pool becomes a bottleneck under concurrent tool calls

## Evidence

Benchmark: `anyio.to_thread.run_sync(lambda: 1)` takes 0.8ms on M2 Mac. A CDP `Runtime.evaluate("1")` roundtrip takes 28-35ms. The thread bridge is <3% of total latency.

---

*Researched by Ninad K.*
