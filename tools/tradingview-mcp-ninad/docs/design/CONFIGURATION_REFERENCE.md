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

## Execution Configuration

### execution_config.json

- **Location search order:** `<project_root>/execution_config.json` → `~/.tradingview-mcp-ninad/execution_config.json`
- **Falls back to:** safe defaults (paper mode, no broker keys)

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | str | `"paper"` | Execution mode: paper, paper_broker, live |
| `paper_balance` | float | `100000.0` | Starting balance for built-in paper broker |
| `paper_currency` | str | `"USD"` | Currency for paper broker |
| `max_position_size` | float | `10000.0` | Max notional per position |
| `max_open_positions` | int | `5` | Max simultaneous open positions |
| `require_confirmation_for_live` | bool | `true` | Gate live mode behind confirm=true |
| `symbol_routing.crypto` | str | `"binance"` | Broker for crypto symbols |
| `symbol_routing.stocks` | str | `"alpaca"` | Broker for stock symbols |
| `symbol_routing.forex` | str | `"mt5"` | Broker for forex symbols |
| `symbol_routing.futures` | str | `"ibkr"` | Broker for futures symbols |
| `brokers.alpaca.api_key` | str | `""` | Alpaca API key |
| `brokers.alpaca.paper` | bool | `true` | Use Alpaca paper endpoint |
| `brokers.binance.api_key` | str | `""` | Binance API key |
| `brokers.binance.testnet` | bool | `true` | Use Binance testnet |
| `brokers.mt5.login` | int | `0` | MT5 account number |
| `brokers.ibkr.port` | int | `7497` | TWS port (7497=paper, 7496=live) |

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
