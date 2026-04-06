# PineConnector API Reference

**Base URL**: `http://localhost:8003`

---

## POST /webhook

Receive and process TradingView alerts.

### Authentication

One of the following (checked in order):
1. `X-Auth-Token` HTTP header
2. `?token=` query parameter
3. `token` field in JSON body
4. First field in plain text body

### Request — JSON Format

```http
POST /webhook HTTP/1.1
Content-Type: application/json
X-Auth-Token: your_token

{
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.10,
  "sl": 1.0850,
  "tp": 1.0950,
  "comment": "my_strategy",
  "magic": 1001
}
```

### Request — Plain Text Format

```http
POST /webhook HTTP/1.1
Content-Type: text/plain
X-Auth-Token: your_token

your_token,buy,EURUSD,lot=0.10,sl=1.0850,tp=1.0950,comment=my_strategy
```

### Request Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `token` | string | No* | `""` | Auth token (alternative to header) |
| `action` | string | **Yes** | — | Trade action (see Actions table) |
| `symbol` | string | **Yes** | — | Trading symbol (e.g., EURUSD, XAUUSD) |
| `lot` | float | No | 0.01 | Trade volume (minimum 0.01) |
| `sl` | float | No | 0 | Stop loss price |
| `tp` | float | No | 0 | Take profit price |
| `sl_pips` | float | No | 0 | Stop loss in pips |
| `tp_pips` | float | No | 0 | Take profit in pips |
| `price` | float | No | 0 | Entry price (for pending orders) |
| `comment` | string | No | `""` | Trade comment (visible in MT5) |
| `magic` | int | No | 0 | Magic number for strategy identification |
| `risk_percent` | float | No | 0 | Risk percentage (overrides lot calculation) |
| `time_exit_minutes` | int | No | 0 | Auto-close after N minutes (0 = disabled) |
| `partial_tp` | object | No | null | Partial TP configuration (see below) |
| `trailing` | object | No | null | Trailing stop configuration (see below) |
| `tp1` | string | No | — | Shorthand: `"10"` or `"10@50%"` |
| `tp2` | string | No | — | Shorthand: `"20"` or `"20@30%"` |
| `tp3` | string | No | — | Shorthand: `"40"` or `"40@20%"` |

### Partial TP Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tp1_pips` | float | 0 | TP1 distance in pips |
| `tp1_percent` | float | 50 | Percentage of lot to close at TP1 |
| `tp2_pips` | float | 0 | TP2 distance in pips |
| `tp2_percent` | float | 30 | Percentage of lot to close at TP2 |
| `tp3_pips` | float | 0 | TP3 distance in pips |
| `tp3_percent` | float | 100 | Percentage of lot to close at TP3 |
| `move_sl_to_be_on_tp1` | bool | true | Move SL to breakeven on TP1 hit |
| `trail_after_tp2` | bool | false | Activate trailing after TP2 hit |
| `trail_distance_pips` | float | 10 | Trail distance if activated after TP2 |

### Trailing Stop Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | false | Enable trailing stop |
| `activation_pips` | float | 20 | Pips profit before trailing starts |
| `distance_pips` | float | 10 | Distance behind price |
| `step_pips` | float | 1 | Minimum SL movement |

### Actions Table

| Action | Description |
|--------|-------------|
| `buy` | Market buy |
| `sell` | Market sell |
| `buylimit` | Buy limit (requires `price`) |
| `selllimit` | Sell limit (requires `price`) |
| `buystop` | Buy stop (requires `price`) |
| `sellstop` | Sell stop (requires `price`) |
| `closebuy` | Close all buy positions for symbol |
| `closesell` | Close all sell positions for symbol |
| `closeall` | Close all open positions |
| `modify` | Modify SL/TP of position |
| `breakeven` | Move SL to entry price |
| `trailing` | Enable/update trailing stop |
| `cancel_buylimit` | Cancel pending buy limit |
| `cancel_selllimit` | Cancel pending sell limit |

### Response

**Success (accepted):**
```json
{
  "status": "accepted",
  "signal_id": "a1b2c3d4e5f6g7h8",
  "reason": ""
}
```

**Risk rejected:**
```json
{
  "status": "rejected",
  "signal_id": "",
  "reason": "Daily trade limit reached (20)"
}
```

**Parse error:**
```json
HTTP 400
{"detail": "Parse error: Unknown action: invalid"}
```

**Auth failure:**
```json
HTTP 401
{"detail": "Invalid token"}
```

---

## GET /api/health

System health check with per-component status.

### Response

```json
{
  "status": "ok",
  "service": "pineconnector",
  "rust_engine": "connected",
  "mt5_connected": true,
  "zmq_connected": true,
  "uptime_seconds": 7200.5,
  "trades_today": 12,
  "dry_run": false
}
```

| Field | Type | Values |
|-------|------|--------|
| `status` | string | `"ok"` or `"error"` |
| `rust_engine` | string | `"connected"` or `"disconnected"` |
| `mt5_connected` | bool | true/false |
| `zmq_connected` | bool | true/false |
| `dry_run` | bool | true if paper trading |

---

## GET /api/trades

List trades with optional filters.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max records to return |
| `offset` | int | 0 | Pagination offset |
| `symbol` | string | null | Filter by symbol |
| `status` | string | null | Filter: `pending`, `open`, `partial`, `closed`, `error` |

### Response

```json
[
  {
    "id": 1,
    "signal_id": "a1b2c3d4e5f6g7h8",
    "ticket": 987654321,
    "symbol": "EURUSD",
    "action": "buy",
    "lot": 0.10,
    "entry_price": 1.0900,
    "exit_price": 0,
    "sl": 1.0850,
    "tp": 1.0950,
    "profit": 0,
    "commission": -0.70,
    "swap": 0,
    "open_time": "2026-04-06T10:30:00Z",
    "close_time": "",
    "status": "open",
    "remaining_lot": 0.10,
    "comment": "my_strategy",
    "magic": 1001
  }
]
```

---

## GET /api/trades/open

List only open/pending/partial trades.

### Response

Same format as `/api/trades`, filtered to `status IN ('pending', 'open', 'partial')`.

---

## GET /api/analytics

Trade analytics over a configurable period.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `days` | int | 30 | Analysis period in days |

### Response

```json
{
  "pnl": {
    "total_pnl": 1250.50,
    "total_commission": -84.00,
    "net_pnl": 1166.50,
    "total_trades": 47,
    "period_days": 30,
    "daily": [
      {"date": "2026-03-07", "pnl": 85.00, "cumulative": 85.00},
      {"date": "2026-03-08", "pnl": -30.00, "cumulative": 55.00}
    ]
  },
  "win_rate": {
    "total": 47,
    "wins": 31,
    "losses": 16,
    "win_rate": 65.9,
    "avg_win": 62.50,
    "avg_loss": -28.75,
    "profit_factor": 4.21,
    "expectancy": 24.82
  },
  "drawdown": {
    "max_drawdown": 285.00,
    "max_drawdown_pct": 3.2,
    "current_drawdown": 45.00,
    "peak_equity": 1250.50,
    "current_equity": 1166.50
  }
}
```

---

## GET /api/config

Current system configuration (no secrets exposed).

### Response

```json
{
  "bridge_mode": "python",
  "dry_run": false,
  "db_backend": "sqlite",
  "zmq": {
    "signal": "tcp://127.0.0.1:5555",
    "command": "tcp://127.0.0.1:5556",
    "result": "tcp://127.0.0.1:5557",
    "state": "tcp://127.0.0.1:5558"
  },
  "symbols_loaded": 15
}
```

---

## POST /api/close-all

Emergency close all open positions.

### Response

```json
{
  "status": "close_all_dispatched",
  "signal_id": "e1f2g3h4i5j6k7l8"
}
```

---

## GET /

Serves the dashboard HTML page (single-page application).
