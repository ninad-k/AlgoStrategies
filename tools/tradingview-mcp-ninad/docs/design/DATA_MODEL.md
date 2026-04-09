# Data Model & Schema Design

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## Overview

tradingview-mcp-ninad does not use a traditional database. All persistent state is file-based JSON on the local filesystem. This document covers the data structures used across the system.

## 1. rules.json Schema

The trading rules configuration file. Validated by `rules/config.py` using Pydantic v2.

```json
{
  "watchlist": ["string"],
  "default_timeframe": "string",
  "bias_criteria": {
    "bullish": ["string"],
    "bearish": ["string"],
    "neutral": ["string"]
  },
  "risk_rules": ["string"],
  "notes": "string"
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `watchlist` | `list[str]` | Yes | `[]` | Symbols to scan during morning brief |
| `default_timeframe` | `str` | No | `"240"` | Chart resolution in minutes (or D/W/M) |
| `bias_criteria.bullish` | `list[str]` | No | `[]` | Conditions for bullish bias |
| `bias_criteria.bearish` | `list[str]` | No | `[]` | Conditions for bearish bias |
| `bias_criteria.neutral` | `list[str]` | No | `[]` | Conditions for neutral bias |
| `risk_rules` | `list[str]` | No | `[]` | Trading rules/constraints |
| `notes` | `str` | No | `""` | Free-text context (macro events, etc.) |

## 2. Session File Schema

Saved to `~/.tradingview-mcp-ninad/sessions/YYYY-MM-DD.json`.

```json
{
  "date": "2026-04-09",
  "saved_at": "2026-04-09T14:30:00+00:00",
  "brief": "BTCUSD | BIAS: bullish | KEY LEVEL: 68500 | WATCH: EMA ribbon direction..."
}
```

## 3. KNOWN_PATHS Dictionary

Internal mapping of TradingView's undocumented JS globals. Defined in `connection/api_resolver.py`.

| Key | JS Path | Used By |
|---|---|---|
| `chart_api` | `window.TradingViewApi._activeChartWidgetWV.value()` | Most tools |
| `chart_widget_collection` | `window.TradingViewApi._chartWidgetCollection` | Pane tools |
| `bottom_widget_bar` | `window.TradingView.bottomWidgetBar` | Pine editor |
| `replay_api` | `window.TradingViewApi._replayApi` | Replay tools |
| `alert_service` | `window.TradingViewApi._alertService` | Alert tools |
| `main_series_bars` | `...mainSeries().bars()` | OHLCV, quote |

## 4. MCP Tool Response Envelope

Every tool returns this shape:

```json
{
  "success": true,
  "field1": "...",
  "field2": "..."
}
```

On error:

```json
{
  "_error": true,
  "result": {
    "success": false,
    "error": "Human-readable message",
    "hint": "Optional recovery suggestion"
  }
}
```

## 5. Log Entry Schema

Written to `~/.tradingview-mcp-ninad/logs/server.log` as structlog JSON:

```json
{
  "event": "cdp.connected",
  "target_url": "https://www.tradingview.com/chart/...",
  "level": "info",
  "timestamp": "2026-04-09T14:30:00.000000Z"
}
```

---

*Authored by Ninad K.*
