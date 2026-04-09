# ADR-003: pychrome for CDP Communication

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Date** | 2026-04-09 |
| **Status** | Accepted |

## Context

The server needs a Chrome DevTools Protocol client to communicate with TradingView Desktop. Ninad K. evaluated several Python CDP libraries.

## Decision

Use **pychrome** as the primary CDP client, with sync calls wrapped in `anyio.to_thread.run_sync()`.

## Alternatives Considered

| Library | Pros | Cons |
|---|---|---|
| **pychrome** | Lightweight, direct CDP mapping, closest to `chrome-remote-interface` | Synchronous API |
| **Playwright** | High-level, async-native | Heavy dependency (downloads Chromium); overkill for eval-only use |
| **pycdp** | Typed CDP bindings | Less mature, smaller community |
| **selenium** | Well-known | Not designed for CDP direct access; wrong abstraction level |

## Rationale

1. pychrome provides the same low-level CDP access as the Node.js `chrome-remote-interface` — closest 1:1 port
2. The server only uses `Runtime.evaluate`, `Page.captureScreenshot`, `Input.dispatchKeyEvent`, and domain enable calls — no high-level browser automation needed
3. `anyio.to_thread.run_sync()` wrappers add ~1ms overhead per call, negligible vs the 30ms CDP roundtrip
4. No binary downloads or browser management — pychrome talks to the already-running TradingView process

## Consequences

- Every CDP call site needs an `async def` wrapper that runs the sync call in a thread
- Cannot use CDP events (websocket push) efficiently — acceptable since all tools are request-response
- If a future tool needs page navigation or complex interaction, Playwright could be added as an optional fallback

---

*Decision made by Ninad K. This project was Ninad K.'s own original idea.*
