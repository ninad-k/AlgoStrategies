# TradingView MCP (Ninad) — Tool Selection Guide

Use this decision tree to pick the right tool for any TradingView task.

## "What's on my chart right now?"

1. `chart_get_state` — symbol, timeframe, chart type, all indicator names + entity IDs
2. `data_get_study_values` — current numeric values from every visible indicator
3. `quote_get` — real-time price snapshot (last, OHLC, volume)

## "What levels/lines/labels are showing?"

These read custom Pine indicator drawings (requires indicators to be visible):

- `data_get_pine_lines` — horizontal price levels from `line.new`
- `data_get_pine_labels` — text annotations from `label.new`
- `data_get_pine_tables` — table rows from `table.new`
- `data_get_pine_boxes` — price zones from `box.new`

Always pass `study_filter` to target a specific indicator by name.

## "Give me price data"

- `data_get_ohlcv` with `summary=true` — compact stats (range, change%, avg volume)
- `data_get_ohlcv` with `summary=false` — individual bars (max 500)

## "Analyze my chart fully"

Chain: `chart_get_state` → `data_get_study_values` → `data_get_pine_lines` + `data_get_pine_labels` → `capture_screenshot`

## "Change what I'm looking at"

- `chart_set_symbol` — switch ticker
- `chart_set_timeframe` — switch resolution (1, 5, 15, 60, D, W, M)
- `chart_set_type` — candles, line, area, Heikin-Ashi, etc.
- `chart_manage_indicator` — add/remove studies (use full names: "Relative Strength Index" not "RSI")
- `chart_scroll_to_date` — jump to a date
- `indicator_set_inputs` — change indicator settings

## "Pine Script development"

1. `pine_set_source` — inject code into Pine Editor
2. `pine_smart_compile` — compile + check errors + report study changes
3. `pine_get_errors` — read Monaco markers
4. `pine_get_console` — read `log.info()` output
5. `pine_save` — persist to TradingView cloud
6. `pine_analyze` — offline static analysis (no chart needed)
7. `pine_check` — server-side compile (no chart needed)

## "Practice trading on historical data"

`replay_start` → `replay_step` → `replay_trade` → `replay_status` → `replay_stop`

## "Scan multiple symbols"

- `batch_run` — run screenshot/ohlcv/strategy across a list of symbols and timeframes
- `morning_brief` — flagship workflow: scan watchlist, read indicators, apply `rules.json`

## "Execute a trade"

1. `trade_get_mode` — check current mode (paper/paper_broker/live)
2. `trade_broker_status` — verify which brokers are connected
3. `trade_execute` — place order: symbol, side (buy/sell), quantity, order_type (market/limit/stop/stop_limit), optional price/SL/TP
4. `trade_positions` — list all open positions with P&L
5. `trade_modify` — change SL/TP on an existing position
6. `trade_close` / `trade_close_all` — close by ticket or close everything
7. `trade_account` — balance, equity, free margin
8. `trade_history` — session trade log
9. `trade_set_mode` — switch modes (paper → paper_broker → live, live requires confirm=true)

**Symbol routing:** crypto→Binance, stocks→Alpaca, forex→MT5, futures→IBKR

**Safety:** Default is paper mode. Always call `trade_get_mode` before placing real trades.

## "Full analysis → trade workflow"

Chain: `morning_brief` → pick a symbol → `data_get_pine_lines` → identify level → `trade_execute` → `trade_positions` → monitor with `quote_get` → `trade_close`

## "Draw on the chart / Manage alerts"

- `draw_shape` — horizontal lines, trend lines, rectangles, text
- `alert_create` / `alert_list` / `alert_delete`

## "Multi-pane layouts / Tabs"

- `pane_set_layout` (s, 2h, 2v, 4, 6, 8) / `pane_set_symbol`
- `tab_list` / `tab_new` / `tab_close` / `tab_switch`

## Context Management Rules

- ALWAYS use `summary=true` on `data_get_ohlcv`
- ALWAYS use `study_filter` when you know which indicator you want
- NEVER use `verbose=true` unless the user specifically asks for raw data
- Call `chart_get_state` ONCE at start, reuse entity IDs throughout the session
- Prefer `capture_screenshot` for visual context over pulling large datasets
- ALWAYS call `trade_get_mode` before placing trades to confirm the execution mode
- NEVER place live trades without explicit user confirmation
- Use `trade_broker_status` to verify broker connectivity before routing orders
