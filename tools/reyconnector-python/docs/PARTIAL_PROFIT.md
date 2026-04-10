# ReyConnector - Partial Profit Booking

## Overview

ReyConnector supports **multi-level partial take-profit booking** out of the box. When a TradingView alert includes TP levels, the execution engine generates:

1. A **MarketOrderCommand** (the main entry order with SL and first TP)
2. One **PartialCloseCommand** per TP level (specifying trigger price and % to close)
3. An optional **TrailingStopCommand** (activated at a specific price)

Close percentages are resolved in this priority:
1. **Alert-level overrides** (`close1=60,close2=25,close3=15`) — highest priority
2. **Connection config defaults** (`PartialTPConfig` per connection) — if alert doesn't specify
3. **System defaults** (40% / 30% / 30%) — if no connection config exists

---

## Alert Format

### CSV Format (Recommended for TradingView)

```
strategy,action,symbol[,key=value,...]
```

### JSON Format

```json
{"strategy":"...","action":"...","symbol":"...",...}
```

---

## Parameters Reference

### Required Fields

| Field | Position (CSV) | JSON Key | Description |
|-------|---------------|----------|-------------|
| Strategy | 1st | `strategy` or `s` | Strategy name (e.g., `ema200`, `smartmoney`) |
| Action | 2nd | `action` or `a` | `buy` or `sell` (case-insensitive) |
| Symbol | 3rd | `symbol` or `sym` | Instrument (e.g., `EURUSD`, `XAUUSD`) |

### Optional Parameters

| Parameter | CSV Key | JSON Key | Type | Description |
|-----------|---------|----------|------|-------------|
| Stop Loss | `sl=<price>` | `"sl": <price>` | float | Stop loss price level |
| Lot Size | `lots=<size>` | `"lots": <size>` | float | Override connection default lot size |
| Take Profit 1 | `tp1=<price>` | `"tp1": <price>` | float | First partial TP trigger price |
| Take Profit 2 | `tp2=<price>` | `"tp2": <price>` | float | Second partial TP trigger price |
| Take Profit 3 | `tp3=<price>` | `"tp3": <price>` | float | Third partial TP trigger price |
| Close % at TP1 | `close1=<pct>` | `"close1": <pct>` | float | % of position to close at TP1 |
| Close % at TP2 | `close2=<pct>` | `"close2": <pct>` | float | % of position to close at TP2 |
| Close % at TP3 | `close3=<pct>` | `"close3": <pct>` | float | % of position to close at TP3 |
| Trailing Stop | `trailing=<act_price>:<trail_dist>` | `"trailing": {"activation_price":..., "trailing_distance":...}` | string or object | Trailing stop activation |
| Magic Number | `magic=<int>` | `"magic": <int>` | int | EA magic number for identification |
| Comment | `comment=<text>` | `"comment": "<text>"` | string | Trade comment |

---

## Examples

### Example 1: Simple Buy with No Partials

**CSV:**
```
ema200,buy,EURUSD
```

**JSON:**
```json
{"strategy":"ema200","action":"buy","symbol":"EURUSD"}
```

**Generated Commands:**
```json
[
  {
    "kind": "market_order",
    "symbol": "EURUSD",
    "action": "buy",
    "lots": 0.10,
    "stopLoss": null,
    "takeProfit": null,
    "magic": 100001,
    "comment": "rey:ema200:conn-demo-001"
  }
]
```

---

### Example 2: Buy with Stop Loss and 3 Partial TPs (Default Close %)

**CSV:**
```
ema200,buy,EURUSD,sl=1.0800,tp1=1.0900,tp2=1.1000,tp3=1.1100
```

**JSON:**
```json
{
  "strategy": "ema200",
  "action": "buy",
  "symbol": "EURUSD",
  "sl": 1.0800,
  "tp1": 1.0900,
  "tp2": 1.1000,
  "tp3": 1.1100
}
```

**Generated Commands (4 total):**
```json
[
  {
    "kind": "market_order",
    "symbol": "EURUSD",
    "action": "buy",
    "lots": 0.10,
    "stopLoss": 1.0800,
    "takeProfit": 1.0900,
    "magic": 100001,
    "comment": "rey:ema200:conn-demo-001"
  },
  {
    "kind": "partial_close",
    "symbol": "EURUSD",
    "action": "buy",
    "closePercent": 40.0,
    "triggerPrice": 1.0900,
    "magic": 100001,
    "comment": "tp1:40.0%"
  },
  {
    "kind": "partial_close",
    "symbol": "EURUSD",
    "action": "buy",
    "closePercent": 30.0,
    "triggerPrice": 1.1000,
    "magic": 100001,
    "comment": "tp2:30.0%"
  },
  {
    "kind": "partial_close",
    "symbol": "EURUSD",
    "action": "buy",
    "closePercent": 30.0,
    "triggerPrice": 1.1100,
    "magic": 100001,
    "comment": "tp3:30.0%"
  }
]
```

---

### Example 3: Custom Close Percentages (Override Defaults)

**CSV:**
```
ema200,buy,EURUSD,sl=1.0800,tp1=1.0900,close1=60,tp2=1.1000,close2=25,tp3=1.1100,close3=15
```

**Generated Partial Close Commands:**
| TP Level | Trigger Price | Close % | Remaining After |
|----------|-------------|---------|-----------------|
| TP1 | 1.0900 | 60% | 40% of original |
| TP2 | 1.1000 | 25% | 15% of original |
| TP3 | 1.1100 | 15% | 0% (fully closed) |

---

### Example 4: Sell Gold with Trailing Stop

**CSV:**
```
smartmoney,sell,XAUUSD,sl=2060,tp1=2030,tp2=2010,tp3=1990,trailing=2020:5.00
```

**JSON:**
```json
{
  "strategy": "smartmoney",
  "action": "sell",
  "symbol": "XAUUSD",
  "sl": 2060,
  "tp1": 2030,
  "tp2": 2010,
  "tp3": 1990,
  "trailing": {
    "activation_price": 2020,
    "trailing_distance": 5.0
  }
}
```

**Generated Commands (5 total):**
```json
[
  {
    "kind": "market_order",
    "symbol": "XAUUSD",
    "action": "sell",
    "lots": 0.10,
    "stopLoss": 2060.0,
    "takeProfit": 2030.0,
    "magic": 100001,
    "comment": "rey:smartmoney:conn-demo-001"
  },
  {
    "kind": "partial_close",
    "symbol": "XAUUSD",
    "action": "sell",
    "closePercent": 40.0,
    "triggerPrice": 2030.0,
    "comment": "tp1:40.0%"
  },
  {
    "kind": "partial_close",
    "symbol": "XAUUSD",
    "action": "sell",
    "closePercent": 30.0,
    "triggerPrice": 2010.0,
    "comment": "tp2:30.0%"
  },
  {
    "kind": "partial_close",
    "symbol": "XAUUSD",
    "action": "sell",
    "closePercent": 30.0,
    "triggerPrice": 1990.0,
    "comment": "tp3:30.0%"
  },
  {
    "kind": "trailing_stop",
    "symbol": "XAUUSD",
    "action": "sell",
    "activationPrice": 2020.0,
    "trailingDistance": 5.0,
    "magic": 100001
  }
]
```

---

### Example 5: Full Alert with All Parameters

**CSV:**
```
smartmoney,buy,GBPUSD,lots=0.20,sl=1.2600,tp1=1.2700,close1=50,tp2=1.2800,close2=30,tp3=1.2900,close3=20,trailing=1.2750:0.0020,magic=200,comment=smc_entry
```

**Generated Commands (5 total):**
| # | Kind | Key Fields |
|---|------|------------|
| 1 | `market_order` | symbol=GBPUSD, action=buy, lots=0.20, sl=1.2600, tp=1.2700, magic=200, comment=smc_entry |
| 2 | `partial_close` | trigger=1.2700, close=50% |
| 3 | `partial_close` | trigger=1.2800, close=30% |
| 4 | `partial_close` | trigger=1.2900, close=20% |
| 5 | `trailing_stop` | activation=1.2750, distance=0.0020 |

---

### Example 6: Single TP (No Partial Booking)

**CSV:**
```
ema200,buy,EURUSD,sl=1.0800,tp1=1.0900
```

**Generated Commands (2 total):**
| # | Kind | Description |
|---|------|-------------|
| 1 | `market_order` | Entry with SL=1.0800, TP=1.0900 |
| 2 | `partial_close` | Close 40% at 1.0900 (remaining 60% stays open) |

---

## TradingView Webhook Setup

### Step 1: Set Webhook URL

```
https://your-domain.com/v1/webhook?connection_id=conn-demo-001
```

### Step 2: Set Alert Message

**Option A — Static CSV with TradingView variables:**
```
ema200,{{strategy.order.action}},{{ticker}},sl={{strategy.order.price}},tp1=1.0900,tp2=1.1000,tp3=1.1100
```

**Option B — Pure CSV:**
```
ema200,buy,EURUSD,sl=1.0800,tp1=1.0900,tp2=1.1000,tp3=1.1100
```

**Option C — JSON:**
```json
{"strategy":"ema200","action":"{{strategy.order.action}}","symbol":"{{ticker}}","sl":{{strategy.order.price}},"tp1":1.0900,"tp2":1.1000,"tp3":1.1100}
```

### Step 3: Optional Headers

Add `X-Idempotency-Key` header for deduplication (TradingView doesn't support custom headers natively, but proxy setups can add them).

---

## Connection Configuration

Each connection has default partial TP settings that apply when the alert doesn't specify close percentages.

### Default Configuration (conn-demo-001)

```json
{
  "config": {
    "defaultLots": 0.10,
    "defaultMagic": 100001,
    "partialTp": {
      "tp1ClosePercent": 40.0,
      "tp2ClosePercent": 30.0,
      "tp3ClosePercent": 30.0
    },
    "enabledStrategies": null
  }
}
```

### Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `defaultLots` | float | 0.10 | Lot size when alert doesn't specify `lots=` |
| `defaultMagic` | int | 0 | Magic number when alert doesn't specify `magic=` |
| `partialTp.tp1ClosePercent` | float | 40.0 | Default close % at TP1 |
| `partialTp.tp2ClosePercent` | float | 30.0 | Default close % at TP2 |
| `partialTp.tp3ClosePercent` | float | 30.0 | Default close % at TP3 |
| `enabledStrategies` | list or null | null | If set, only these strategy names are allowed. `null` = allow all |

### Priority Resolution

```
Alert parameter  >  Connection config  >  System default

lots:   alert.lots   > connection.defaultLots   > 0.10
magic:  alert.magic  > connection.defaultMagic  > 0
close%: alert.closeN > connection.partialTp.tpN > 40/30/30
```

---

## Broker Command Reference

### MarketOrderCommand

The main entry order.

| Field | Type | JSON Key | Description |
|-------|------|---------|-------------|
| `kind` | `"market_order"` | `kind` | Command type |
| `symbol` | string | `symbol` | Trading instrument |
| `action` | `"buy"` or `"sell"` | `action` | Trade direction |
| `lots` | float | `lots` | Position size |
| `stop_loss` | float or null | `stopLoss` | Stop loss price |
| `take_profit` | float or null | `takeProfit` | First TP price (for broker-level TP) |
| `magic` | int | `magic` | EA identifier |
| `comment` | string | `comment` | Trade comment |

### PartialCloseCommand

Instruction to close a percentage of the position at a trigger price.

| Field | Type | JSON Key | Description |
|-------|------|---------|-------------|
| `kind` | `"partial_close"` | `kind` | Command type |
| `symbol` | string | `symbol` | Trading instrument |
| `action` | `"buy"` or `"sell"` | `action` | Original trade direction |
| `close_percent` | float | `closePercent` | % of original position to close (e.g., 40.0) |
| `trigger_price` | float | `triggerPrice` | Price that triggers the partial close |
| `magic` | int | `magic` | EA identifier |
| `comment` | string | `comment` | Description (e.g., `"tp1:40.0%"`) |

### TrailingStopCommand

Instruction to activate a trailing stop at a specific profit level.

| Field | Type | JSON Key | Description |
|-------|------|---------|-------------|
| `kind` | `"trailing_stop"` | `kind` | Command type |
| `symbol` | string | `symbol` | Trading instrument |
| `action` | `"buy"` or `"sell"` | `action` | Original trade direction |
| `activation_price` | float | `activationPrice` | Price where trailing activates |
| `trailing_distance` | float | `trailingDistance` | Distance the stop trails behind price |
| `magic` | int | `magic` | EA identifier |

### NoopCommand

Returned when the engine cannot or should not act (parse error, disabled connection, etc.).

| Field | Type | JSON Key | Description |
|-------|------|---------|-------------|
| `kind` | `"noop"` | `kind` | Command type |
| `reason` | string | `reason` | Why no action was taken |

---

## Guards & Validation

The execution engine performs these checks before generating commands:

| Check | Result if Failed |
|-------|-----------------|
| Alert body cannot be parsed | `NoopCommand(reason="Parse error: ...")` |
| Connection `is_enabled` is `false` | `NoopCommand(reason="Connection ... is disabled")` |
| Strategy not in `enabled_strategies` list | `NoopCommand(reason="Strategy '...' not in enabled list")` |
| Connection not found | Commands generated with system defaults (no error) |

---

## Testing with curl

### Send a partial profit alert:
```bash
curl -X POST "http://localhost:5242/v1/webhook?connection_id=conn-demo-001" \
  -H "Content-Type: text/plain" \
  -d "ema200,buy,EURUSD,sl=1.0800,tp1=1.0900,tp2=1.1000,tp3=1.1100"
```

### Check what commands were generated:
```bash
# Get the signal log
curl http://localhost:5241/api/v1/signals

# Or send directly to Control API and see commands in response:
curl -X POST http://localhost:5241/api/internal/v1/signals \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-001",
    "connectionId": "conn-demo-001",
    "rawBody": "ema200,buy,EURUSD,sl=1.0800,tp1=1.0900,tp2=1.1000,tp3=1.1100",
    "receivedAtUtc": "2026-04-09T12:00:00Z"
  }'
```

**Response:**
```json
{
  "id": "test-001",
  "commands": [
    {"kind":"market_order","symbol":"EURUSD","action":"buy","lots":0.1,"stopLoss":1.08,"takeProfit":1.09,"magic":100001,"comment":"rey:ema200:conn-demo-001"},
    {"kind":"partial_close","symbol":"EURUSD","action":"buy","closePercent":40.0,"triggerPrice":1.09,"magic":100001,"comment":"tp1:40.0%"},
    {"kind":"partial_close","symbol":"EURUSD","action":"buy","closePercent":30.0,"triggerPrice":1.1,"magic":100001,"comment":"tp2:30.0%"},
    {"kind":"partial_close","symbol":"EURUSD","action":"buy","closePercent":30.0,"triggerPrice":1.11,"magic":100001,"comment":"tp3:30.0%"}
  ]
}
```
