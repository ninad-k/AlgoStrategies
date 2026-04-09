# ADR-004: structlog with File-Only Sink

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Date** | 2026-04-09 |
| **Status** | Accepted |

## Context

MCP stdio transport uses stdout exclusively for JSON-RPC frames. Any stray log line on stdout corrupts the protocol and causes Claude Code to silently disconnect. Ninad K. needed a logging strategy that guarantees stdout safety.

## Decision

Use **structlog** with a **RotatingFileHandler** pointed at `~/.tradingview-mcp-ninad/logs/server.log`. Strip all existing handlers from the root logger at import time. Assert no stdout handlers exist.

## Rationale

1. structlog produces structured JSON logs — easy to parse, grep, and correlate
2. File-only sink eliminates the stdout corruption risk entirely
3. The import-time assertion (`_assert_no_stdout_handlers`) catches third-party libraries that attach StreamHandlers
4. Rotating file handler prevents unbounded log growth (5 MB per file, 3 backups)

## Consequences

- Developers must use `structlog.get_logger()` — never `print()` or `logging.getLogger()` with default config
- Logs are only visible by reading the file, not in the terminal — acceptable for a background server
- The CLI (`tv` command) writes to stderr for user messages and stdout for JSON output

---

*Decision made by Ninad K. This project was Ninad K.'s own original idea.*
