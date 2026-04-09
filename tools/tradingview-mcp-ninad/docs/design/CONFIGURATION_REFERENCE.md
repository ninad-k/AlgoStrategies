# Configuration Reference

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TVMCP_CDP_HOST` | `localhost` | Host where TradingView Desktop's CDP endpoint is running |
| `TVMCP_CDP_PORT` | `9222` | Port for the Chrome DevTools Protocol endpoint |
| `TVMCP_RULES_PATH` | `./rules.json` | Absolute path to the trading rules file |
| `TVMCP_STATE_DIR` | `~/.tradingview-mcp-ninad` | Directory for logs, sessions, and screenshots |

## Configuration Files

### rules.json
- **Location search order:** `$TVMCP_RULES_PATH` → `<project_root>/rules.json` → `~/.tradingview-mcp/rules.json`
- **Schema:** See `docs/design/DATA_MODEL.md`
- **Hot-reloadable:** Checked on each `morning_brief` invocation

### ~/.claude/.mcp.json
Claude Code MCP server registration:

```json
{
  "mcpServers": {
    "tradingview-ninad": {
      "command": "python",
      "args": ["-m", "tradingview_mcp_ninad"],
      "cwd": "/absolute/path/to/tools/tradingview-mcp-ninad"
    }
  }
}
```

## Connection Constants

| Constant | Value | Location |
|---|---|---|
| `MAX_RETRIES` | 5 | `connection/cdp_connection.py` |
| `BASE_DELAY_SECONDS` | 0.5 | `connection/cdp_connection.py` |
| `MAX_DELAY_SECONDS` | 30.0 | `connection/cdp_connection.py` |
| `MAX_OHLCV_BARS` | 500 | `core/data.py` |
| `MAX_TRADES` | 20 | `core/data.py` |
| `DEFAULT_TIMEOUT_SECONDS` | 10.0 | `core/wait.py` |
| `POLL_INTERVAL_SECONDS` | 0.2 | `core/wait.py` |

---

*Authored by Ninad K.*
