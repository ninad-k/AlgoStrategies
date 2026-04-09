# Operations Runbook

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## Service Overview

`tradingview-mcp-ninad` is a local MCP stdio server. It runs as a child process of Claude Code, not as a long-lived daemon. Each Claude Code session spawns a new instance.

## Log Location

```
~/.tradingview-mcp-ninad/logs/server.log
```

Rotating: 5 MB max per file, 3 backups.

## Health Check

```bash
tv health
# or from Claude Code: call tv_health_check
```

Expected healthy response:
```json
{
  "success": true,
  "cdp_connected": true,
  "chart_symbol": "BTCUSD",
  "api_available": true
}
```

## Common Scenarios

### TradingView not detected

**Symptom:** `tv_health_check` returns "Cannot reach Chrome DevTools"

**Action:**
1. Verify TradingView Desktop is running
2. Verify it was launched with CDP: `curl http://localhost:9222/json/version`
3. If not, relaunch: `./scripts/launch_tv_debug_mac.sh`

### CDP connected but API unavailable

**Symptom:** `"api_available": false`

**Action:**
1. Ensure a chart is open (not just the TradingView home screen)
2. Navigate to any chart — the API only exists on chart pages

### MCP server crashes on startup

**Symptom:** Claude Code shows "server disconnected"

**Action:**
1. Check logs: `tail -50 ~/.tradingview-mcp-ninad/logs/server.log`
2. Common cause: port 9222 in use by another process
3. Common cause: Python version < 3.11

### Morning brief stuck / slow

**Symptom:** `morning_brief` takes > 30s

**Action:**
1. Each symbol switch takes ~2s (TV data load time). 10 symbols = 20s minimum.
2. Reduce `watchlist` in `rules.json` to 3-5 symbols
3. Check if TradingView is rate-limiting (free tier has slower data)

### Stale indicator data

**Symptom:** `data_get_study_values` returns old values

**Action:**
1. TradingView caches indicator values until the next bar
2. Wait for the chart to fully render after symbol/timeframe change
3. The `wait_for_chart_ready` helper polls for DOM stability — if bypassed, add a manual delay

### Pine Editor not found

**Symptom:** `pine_*` tools return "Monaco not found"

**Action:**
1. The Pine Editor must be open (bottom panel)
2. Call `ui_open_panel(panel="pine-editor")` first
3. `pine_smart_compile` and `pine_set_source` auto-open it, but may fail on first attempt

## Monitoring

Since this is a local tool (not a production service), monitoring is limited to:

- **Log tailing:** `tail -f ~/.tradingview-mcp-ninad/logs/server.log`
- **Session files:** `ls ~/.tradingview-mcp-ninad/sessions/`
- **Screenshot output:** `ls ~/.tradingview-mcp-ninad/screenshots/`

## Restart Procedure

No restart needed — Claude Code spawns a fresh server per session. To force a clean state:

1. Close the Claude Code session
2. Kill any lingering Python processes: `pkill -f tradingview_mcp_ninad`
3. Open a new Claude Code session

---

*Authored by Ninad K.*
