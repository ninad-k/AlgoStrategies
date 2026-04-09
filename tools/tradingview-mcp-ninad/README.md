# tradingview-mcp-ninad

Python MCP server for reading and controlling a live TradingView Desktop chart via Chrome DevTools Protocol. Exposes **78 tools** across chart reading, Pine Script development, replay trading, multi-pane layouts, drawing, alerts, and a flagship **morning brief** workflow.

## Architecture

```
Claude Code  <-->  MCP server (stdio)  <-->  CDP (localhost:9222)  <-->  TradingView Desktop
```

All data stays local. No external API keys required (except TradingView's own account for the desktop app).

## Quick Start

### 1. Install

```bash
cd tools/tradingview-mcp-ninad
pip install -e .
```

### 2. Configure rules

```bash
cp rules.example.json rules.json
# Edit rules.json with your watchlist, bias criteria, and risk rules
```

### 3. Launch TradingView with CDP

```bash
# macOS
./scripts/launch_tv_debug_mac.sh

# Windows
scripts\launch_tv_debug.bat

# Linux
./scripts/launch_tv_debug_linux.sh
```

### 4. Register with Claude Code

Add to `~/.claude/.mcp.json`:

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

Restart Claude Code and run `tv_health_check` to verify.

### 5. Run your morning brief

Ask Claude: *"Run morning_brief"* — or from terminal:

```bash
tv brief
```

## CLI

The `tv` command mirrors the most common MCP tools:

```
tv health          # Check CDP connection
tv brief           # Morning brief workflow
tv state           # Current chart state
tv quote [SYMBOL]  # Real-time quote
tv ohlcv           # Price data (summary)
tv indicators      # Data window readout
tv screenshot      # Capture chart
tv tabs            # List chart tabs
tv panes           # List panes
tv watchlist       # Watchlist symbols
tv alerts          # Active alerts
tv analyze FILE    # Static Pine analysis
tv check FILE      # Server-side Pine compile
```

All commands output JSON to stdout for piping to `jq`, scripts, or other tools.

## Tool Categories (78 tools)

| Category | Tools | Count |
|---|---|---|
| Health | `tv_health_check`, `tv_discover`, `tv_ui_state`, `tv_launch` | 4 |
| Chart | `chart_get_state`, `chart_set_symbol`, `chart_set_timeframe`, `chart_set_type`, `chart_manage_indicator`, `chart_get_visible_range`, `chart_set_visible_range`, `chart_scroll_to_date`, `symbol_info`, `symbol_search` | 10 |
| Data | `data_get_ohlcv`, `data_get_indicator`, `data_get_strategy_results`, `data_get_trades`, `data_get_equity`, `quote_get`, `depth_get`, `data_get_pine_lines`, `data_get_pine_labels`, `data_get_pine_tables`, `data_get_pine_boxes`, `data_get_study_values` | 12 |
| Indicators | `indicator_set_inputs`, `indicator_toggle_visibility` | 2 |
| Pine Script | `pine_get_source`, `pine_set_source`, `pine_compile`, `pine_smart_compile`, `pine_get_errors`, `pine_get_console`, `pine_save`, `pine_analyze`, `pine_check` | 9 |
| Replay | `replay_start`, `replay_step`, `replay_autoplay`, `replay_stop`, `replay_trade`, `replay_status` | 6 |
| Morning Brief | `morning_brief`, `session_save`, `session_get` | 3 |
| Watchlist | `watchlist_get`, `watchlist_add` | 2 |
| Batch | `batch_run` | 1 |
| Capture | `capture_screenshot` | 1 |
| Drawing | `draw_shape`, `draw_list`, `draw_get_properties`, `draw_remove_one`, `draw_clear` | 5 |
| Alerts | `alert_create`, `alert_list`, `alert_delete` | 3 |
| Panes | `pane_list`, `pane_set_layout`, `pane_focus`, `pane_set_symbol` | 4 |
| Tabs | `tab_list`, `tab_new`, `tab_close`, `tab_switch` | 4 |
| UI | `ui_click`, `ui_keyboard`, `ui_type_text`, `ui_hover`, `ui_mouse_click`, `ui_open_panel`, `ui_fullscreen`, `layout_list`, `layout_switch`, `ui_scroll`, `ui_find_element`, `ui_evaluate` | 12 |

## Configuration

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `TVMCP_CDP_HOST` | `localhost` | CDP endpoint host |
| `TVMCP_CDP_PORT` | `9222` | CDP endpoint port |
| `TVMCP_RULES_PATH` | `./rules.json` | Path to trading rules |
| `TVMCP_STATE_DIR` | `~/.tradingview-mcp-ninad` | Logs and sessions directory |

### rules.json

```json
{
  "watchlist": ["BTCUSD", "ETHUSD", "SOLUSD"],
  "default_timeframe": "240",
  "bias_criteria": {
    "bullish": ["Ribbon direction is up", "Price above 20 EMA", "RSI below 60"],
    "bearish": ["Ribbon direction is down", "Price below 20 EMA", "RSI above 40"],
    "neutral": ["Ribbon is flat", "Price chopping around 20 EMA", "RSI between 45-55"]
  },
  "risk_rules": [
    "Minimum R:R 1:2",
    "No trading first 15 min of NY session",
    "Max 2 open positions",
    "2 consecutive losses = stop for the day"
  ],
  "notes": "Add macro events, key dates, etc."
}
```

## Tech Stack

- **Python 3.11+** with FastMCP (official MCP SDK)
- **pychrome** for Chrome DevTools Protocol
- **tenacity** for connection retry logic
- **pydantic v2** for rules.json validation
- **structlog** for file-only logging (never stdout)
- **typer + rich** for the `tv` CLI

## Disclaimer

This is an unofficial tool. Not affiliated with TradingView Inc. Ensure your usage complies with TradingView's Terms of Use.
