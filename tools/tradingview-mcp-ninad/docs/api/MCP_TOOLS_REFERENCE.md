# MCP Tools API Reference — tradingview-mcp-ninad

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Version** | 1.0 |
| **Total Tools** | 78 |

This document is the authoritative reference for every MCP tool exposed by the server. Tool names are stable API contracts — they must not change without a major version bump.

> This project was conceived and built by Ninad K. as an original idea.

---

## Health (4 tools)

### `tv_health_check`
Check CDP connection to TradingView and return current chart state.

- **Parameters:** none
- **Returns:** `{ success, cdp_connected, target_id, target_url, chart_symbol, chart_resolution, chart_type, api_available }`

### `tv_discover`
Report which known TradingView API paths are available and their methods.

- **Parameters:** none
- **Returns:** `{ success, apis_available, apis_total, apis: { chartApi, chartWidgetCollection, ... } }`

### `tv_ui_state`
Get current UI state: which panels are open, what buttons are visible/enabled/disabled.

- **Parameters:** none
- **Returns:** `{ success, bottom_panel, right_panel, pine_editor, strategy_tester, buttons, key_buttons, chart, replay }`

### `tv_launch`
Launch TradingView Desktop with CDP enabled. Auto-detects install location.

- **Parameters:**
  - `port` (int, optional) — CDP port, default 9222
  - `kill_existing` (bool, optional) — kill running instances first, default true
- **Returns:** `{ success, platform, binary, pid, cdp_port, cdp_url, browser, user_agent }`

---

## Chart (10 tools)

### `chart_get_state`
Get current chart state (symbol, timeframe, chart type, indicators).

- **Parameters:** none
- **Returns:** `{ success, symbol, resolution, chartType, studies: [{ id, name }] }`

### `chart_set_symbol`
Change the chart symbol.

- **Parameters:**
  - `symbol` (str, required) — e.g., "BTCUSD", "AAPL", "ES1!", "NYMEX:CL1!"
- **Returns:** `{ success, symbol, chart_ready }`

### `chart_set_timeframe`
Change the chart timeframe/resolution.

- **Parameters:**
  - `timeframe` (str, required) — e.g., "1", "5", "15", "60", "D", "W", "M"
- **Returns:** `{ success, timeframe, chart_ready }`

### `chart_set_type`
Change chart type.

- **Parameters:**
  - `chart_type` (str, required) — name or number: Bars(0), Candles(1), Line(2), Area(3), Renko(4), Kagi(5), PointAndFigure(6), LineBreak(7), HeikinAshi(8), HollowCandles(9)
- **Returns:** `{ success, chart_type, type_num }`

### `chart_manage_indicator`
Add or remove an indicator/study on the chart.

- **Parameters:**
  - `action` (str, required) — "add" or "remove"
  - `indicator` (str, required) — full name: "Relative Strength Index", "MACD", etc.
  - `entity_id` (str, optional) — required for remove
  - `inputs` (str, optional) — JSON string of input overrides
- **Returns:** `{ success, action, indicator, entity_id, new_study_count }`

### `chart_get_visible_range`
Get the visible date range and bars range on the chart.

- **Parameters:** none
- **Returns:** `{ success, visible_range, bars_range }`

### `chart_set_visible_range`
Zoom the chart to a specific date range.

- **Parameters:**
  - `from_ts` (float, required) — start unix timestamp
  - `to_ts` (float, required) — end unix timestamp
- **Returns:** `{ success, requested, actual }`

### `chart_scroll_to_date`
Jump the chart view to center on a specific date.

- **Parameters:**
  - `date` (str, required) — ISO date or unix timestamp string
- **Returns:** `{ success, date, centered_on, resolution, window }`

### `symbol_info`
Get detailed metadata about the current symbol.

- **Parameters:** none
- **Returns:** `{ success, symbol, full_name, exchange, description, type, resolution, chart_type }`

### `symbol_search`
Search for symbols by name or keyword.

- **Parameters:**
  - `query` (str, required) — e.g., "AAPL", "crude oil"
  - `type` (str, optional) — "stock", "futures", "crypto", "forex"
- **Returns:** `{ success, query, source, results: [{ symbol, description, exchange, type, full_name }], count }`

---

## Data (12 tools)

### `data_get_ohlcv`
Get OHLCV bar data. Use `summary=true` for compact stats.

- **Parameters:**
  - `count` (int, optional) — number of bars, max 500, default 100
  - `summary` (bool, optional) — return summary stats instead of all bars
- **Returns (summary):** `{ success, bar_count, period, open, close, high, low, range, change, change_pct, avg_volume, last_5_bars }`
- **Returns (full):** `{ success, bar_count, total_available, source, bars: [{ time, open, high, low, close, volume }] }`

### `data_get_indicator`
Get indicator/study info and input values.

- **Parameters:**
  - `entity_id` (str, required) — from chart_get_state
- **Returns:** `{ success, entity_id, visible, inputs }`

### `data_get_strategy_results`
Get strategy performance metrics from Strategy Tester.

- **Parameters:** none
- **Returns:** `{ success, metric_count, source, metrics }`

### `data_get_trades`
Get trade list from Strategy Tester.

- **Parameters:**
  - `max_trades` (int, optional) — maximum trades to return, default 20
- **Returns:** `{ success, trade_count, source, trades }`

### `data_get_equity`
Get equity curve data from Strategy Tester.

- **Parameters:** none
- **Returns:** `{ success, data_points, source, data, equity_summary }`

### `quote_get`
Get real-time quote data for a symbol.

- **Parameters:**
  - `symbol` (str, optional) — blank = current chart symbol
- **Returns:** `{ success, symbol, time, open, high, low, close, last, volume, bid, ask, description, exchange, type }`

### `depth_get`
Get order book / DOM data from the chart.

- **Parameters:** none
- **Returns:** `{ success, bid_levels, ask_levels, spread, bids, asks }`

### `data_get_pine_lines`
Read horizontal price levels drawn by Pine Script indicators.

- **Parameters:**
  - `study_filter` (str, optional) — match study name substring
  - `verbose` (bool, optional) — return raw line data
- **Returns:** `{ success, study_count, studies: [{ name, total_lines, horizontal_levels }] }`

### `data_get_pine_labels`
Read text labels drawn by Pine Script indicators.

- **Parameters:**
  - `study_filter` (str, optional)
  - `max_labels` (int, optional) — default 50
  - `verbose` (bool, optional)
- **Returns:** `{ success, study_count, studies: [{ name, total_labels, showing, labels }] }`

### `data_get_pine_tables`
Read table data drawn by Pine Script indicators.

- **Parameters:**
  - `study_filter` (str, optional)
- **Returns:** `{ success, study_count, studies: [{ name, tables: [{ rows }] }] }`

### `data_get_pine_boxes`
Read box/zone boundaries drawn by Pine Script indicators.

- **Parameters:**
  - `study_filter` (str, optional)
  - `verbose` (bool, optional)
- **Returns:** `{ success, study_count, studies: [{ name, total_boxes, zones: [{ high, low }] }] }`

### `data_get_study_values`
Get current indicator values from the data window for all visible studies.

- **Parameters:** none
- **Returns:** `{ success, study_count, studies: [{ name, values }] }`

---

## Indicators (2 tools)

### `indicator_set_inputs`
Change indicator/study input values.

- **Parameters:**
  - `entity_id` (str, required)
  - `inputs` (str, required) — JSON string, e.g. `'{"length": 50}'`
- **Returns:** `{ success, entity_id, updated_inputs }`

### `indicator_toggle_visibility`
Show or hide an indicator/study.

- **Parameters:**
  - `entity_id` (str, required)
  - `visible` (bool, required)
- **Returns:** `{ success, entity_id, visible }`

---

## Pine Script (9 tools)

### `pine_get_source`
Get current Pine Script source from the editor.

- **Returns:** `{ success, source, line_count, char_count }`

### `pine_set_source`
Inject Pine Script code into the editor.

- **Parameters:**
  - `source` (str, required)
- **Returns:** `{ success, lines_set }`

### `pine_compile`
Compile current script and add/update on chart.

- **Returns:** `{ success, button_clicked, source }`

### `pine_smart_compile`
Intelligent compile: detect button, compile, check errors, report study changes.

- **Returns:** `{ success, button_clicked, has_errors, error_count, errors, studies_before, studies_after }`

### `pine_get_errors`
Read compilation errors from the editor.

- **Returns:** `{ success, has_errors, error_count, errors: [{ line, column, message, severity }] }`

### `pine_get_console`
Read Pine Script console output.

- **Returns:** `{ success, entries: [{ timestamp, type, message }], entry_count }`

### `pine_save`
Save the current script (Ctrl+S).

- **Returns:** `{ success, action }`

### `pine_analyze`
Run static analysis on Pine Script code (offline).

- **Parameters:**
  - `source` (str, required)
- **Returns:** `{ success, issue_count, diagnostics: [{ line, column, message, severity }] }`

### `pine_check`
Compile Pine Script via TradingView's server API (no chart needed).

- **Parameters:**
  - `source` (str, required)
- **Returns:** `{ success, compiled, error_count, warning_count, errors, warnings }`

---

## Replay (6 tools)

### `replay_start`
Start replay mode at a historical date.

- **Parameters:**
  - `date` (str, optional) — YYYY-MM-DD format
- **Returns:** `{ success, replay_started, date, current_date }`

### `replay_step`
Step one bar forward.

- **Returns:** `{ success, action, current_date }`

### `replay_autoplay`
Toggle auto-advance with configurable speed.

- **Parameters:**
  - `speed` (int, optional) — delay in milliseconds
- **Returns:** `{ success, autoplay_active, delay_ms }`

### `replay_stop`
Stop replay and return to live mode.

- **Returns:** `{ success, action }`

### `replay_trade`
Execute a simulated trade.

- **Parameters:**
  - `action` (str, required) — "buy", "sell", or "close"
- **Returns:** `{ success, action, position, realized_pnl }`

### `replay_status`
Get current replay status, position, and P&L.

- **Returns:** `{ success, is_replay_available, is_replay_started, is_autoplay_started, current_date, position, realized_pnl }`

---

## Morning Brief (3 tools)

### `morning_brief`
Scan watchlist, read indicators, apply rules for session bias.

- **Parameters:**
  - `rules_path` (str, optional) — path to rules.json
- **Returns:** `{ success, generated_at, rules_loaded_from, rules, symbols_scanned, instruction }`

### `session_save`
Persist today's brief to disk.

- **Parameters:**
  - `brief` (str, required)
  - `date` (str, optional) — YYYY-MM-DD
- **Returns:** `{ success, path, date }`

### `session_get`
Retrieve a saved session brief.

- **Parameters:**
  - `date` (str, optional) — defaults to today/yesterday
- **Returns:** `{ success, date, brief, saved_at }`

---

## Watchlist (2), Batch (1), Capture (1), Drawing (5), Alerts (3), Panes (4), Tabs (4), UI (12)

### `watchlist_get` / `watchlist_add`
Read or add symbols to the watchlist.

### `batch_run`
Execute action across multiple symbols/timeframes. Actions: "screenshot", "get_ohlcv", "get_strategy_results".

### `capture_screenshot`
Take a PNG screenshot. Regions: "full", "chart", "strategy_tester". Methods: "cdp", "api".

### `draw_shape` / `draw_list` / `draw_get_properties` / `draw_remove_one` / `draw_clear`
Create, inspect, and manage chart drawings.

### `alert_create` / `alert_list` / `alert_delete`
Create, list, and delete price alerts.

### `pane_list` / `pane_set_layout` / `pane_focus` / `pane_set_symbol`
Manage multi-chart layouts and pane symbols.

### `tab_list` / `tab_new` / `tab_close` / `tab_switch`
Manage chart tabs.

### `ui_click` / `ui_keyboard` / `ui_type_text` / `ui_hover` / `ui_mouse_click` / `ui_open_panel` / `ui_fullscreen` / `layout_list` / `layout_switch` / `ui_scroll` / `ui_find_element` / `ui_evaluate`
Low-level UI interaction via CDP Input events and DOM manipulation.

---

*Authored by Ninad K. This project was Ninad K.'s own original idea.*
