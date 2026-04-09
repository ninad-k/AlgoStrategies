# Troubleshooting Guide

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## Quick Diagnostics

```bash
# 1. Is TradingView running with CDP?
curl -s http://localhost:9222/json/version | python3 -m json.tool

# 2. Is the Python package installed?
tv --help

# 3. Can the server connect?
tv health

# 4. Check server logs
tail -50 ~/.tradingview-mcp-ninad/logs/server.log
```

## Issue: "Cannot reach Chrome DevTools"

**Cause:** TradingView Desktop was not started with `--remote-debugging-port=9222`.

**Fix:**
```bash
# Kill and relaunch properly
pkill -f TradingView
./scripts/launch_tv_debug_mac.sh
```

**Verify:** `curl http://localhost:9222/json/version` should return JSON with browser info.

## Issue: "No TradingView chart target found"

**Cause:** TradingView is running but no chart tab is open.

**Fix:** Open any chart in TradingView Desktop. The server needs a page with URL matching `tradingview.com/chart`.

## Issue: Claude Code says "server disconnected"

**Cause:** The MCP server crashed on startup. Possible reasons:
1. Import error (missing dependency)
2. Port 9222 in use by another app
3. Python version too old

**Debug:**
```bash
python3 -m tradingview_mcp_ninad 2>&1 | head -20
```

If it prints anything to stdout other than JSON-RPC, that's the problem.

## Issue: `morning_brief` returns errors for some symbols

**Cause:** TradingView needs time to load data after switching symbols. The 0.9s delay may not be enough for slow connections.

**Fix:** This is expected for illiquid or exotic symbols. The tool reports per-symbol errors and continues scanning the rest of the watchlist.

## Issue: Pine tools say "Monaco not found in React fiber tree"

**Cause:** The Pine Editor panel is not open, or TradingView changed its internal React structure.

**Fix:**
1. Open the Pine Editor manually (bottom panel)
2. Try `ui_open_panel(panel="pine-editor")` first
3. If TradingView updated and broke the fiber walk, the `FIND_MONACO` constant in `core/pine.py` needs updating

## Issue: `indicator_set_inputs` says "Study not found"

**Cause:** The `entity_id` is wrong or the indicator was removed since the last `chart_get_state` call.

**Fix:** Call `chart_get_state` again to get fresh entity IDs.

## Issue: Screenshots are black or empty

**Cause:** TradingView hasn't finished rendering the chart when the screenshot is taken.

**Fix:** Add a brief delay before `capture_screenshot`, or call `chart_get_state` first (which implicitly waits for the chart to be interactive).

## Issue: `batch_run` is very slow

**Cause:** Each symbol switch requires TradingView to load new data. The `delay_ms` parameter (default 2000ms) adds intentional wait time per iteration.

**Fix:** Reduce the symbol list, or accept that N symbols x M timeframes = N*M*(2+delay) seconds. There's no way to parallelize this since TradingView Desktop has one chart at a time.

## Issue: `alert_create` doesn't work

**Cause:** Alert creation via DOM manipulation is fragile — TradingView's alert dialog structure changes frequently.

**Fix:** This tool uses a best-effort DOM approach. If it fails, create alerts manually in TradingView. The `alert_list` tool (which uses the REST API) is more reliable.

## Collecting Debug Information

If you need to report an issue, collect:

```bash
# Server version
python3 -c "import tradingview_mcp_ninad; print(tradingview_mcp_ninad.__version__)"

# Python version
python3 --version

# Installed packages
pip list | grep -E "mcp|pychrome|pydantic|tenacity|structlog"

# CDP target list
curl -s http://localhost:9222/json/list | python3 -m json.tool

# Recent logs
tail -100 ~/.tradingview-mcp-ninad/logs/server.log
```

---

*Authored by Ninad K.*
