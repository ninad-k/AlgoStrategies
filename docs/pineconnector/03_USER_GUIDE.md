# PineConnector User Guide

## Overview

PineConnector receives alerts from TradingView (or any HTTP client), validates them against risk rules, and executes trades on MetaTrader 5. This guide covers all supported alert formats, workflows, and features.

---

## Starting the System

```bash
# Terminal 1: Python server
cd tools/pineconnector
py -3 run.py                  # Live mode
py -3 run.py --dry-run        # Paper trading (no real orders)
py -3 run.py --port 9000      # Custom port

# Terminal 2: Rust engine
cd tools/pineconnector/rust
cargo run --release
```

---

## Alert Formats

### Format 1: JSON (Recommended)

```json
{
  "token": "your_secret_token",
  "action": "buy",
  "symbol": "XAUUSD",
  "lot": 0.1,
  "sl": 2300.00,
  "tp": 2350.00,
  "comment": "my_strategy"
}
```

### Format 2: Plain Text (Comma-Separated)

```
your_secret_token,buy,XAUUSD,lot=0.1,sl=2300,tp=2350,comment=my_strategy
```

### Authentication

Include your token via ANY of these methods:
1. `X-Auth-Token` HTTP header (recommended)
2. `?token=xxx` query parameter
3. `"token"` field in JSON body
4. First field in plain text format

---

## Supported Actions

| Action | Description | Example |
|--------|-------------|---------|
| `buy` | Market buy order | `{"action":"buy","symbol":"EURUSD","lot":0.1}` |
| `sell` | Market sell order | `{"action":"sell","symbol":"XAUUSD","lot":0.05}` |
| `buylimit` | Buy limit pending order | `{"action":"buylimit","symbol":"EURUSD","lot":0.1,"price":1.0800}` |
| `selllimit` | Sell limit pending order | `{"action":"selllimit","symbol":"XAUUSD","lot":0.1,"price":2400}` |
| `buystop` | Buy stop pending order | `{"action":"buystop","symbol":"EURUSD","lot":0.1,"price":1.1200}` |
| `sellstop` | Sell stop pending order | `{"action":"sellstop","symbol":"XAUUSD","lot":0.1,"price":2250}` |
| `closebuy` | Close all buy positions for symbol | `{"action":"closebuy","symbol":"EURUSD"}` |
| `closesell` | Close all sell positions for symbol | `{"action":"closesell","symbol":"XAUUSD"}` |
| `closeall` | Close ALL open positions | `{"action":"closeall","symbol":"ALL"}` |
| `modify` | Modify SL/TP of position | `{"action":"modify","symbol":"EURUSD","sl":1.09,"tp":1.12}` |
| `breakeven` | Move SL to entry price | `{"action":"breakeven","symbol":"EURUSD"}` |
| `trailing` | Enable trailing stop | `{"action":"trailing","symbol":"EURUSD","trailing":{...}}` |

---

## Feature: Partial Profit Booking

Close portions of a position at multiple take-profit levels.

### Shorthand Format (Easiest)

```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.30,
  "sl": 20,
  "tp1": "10@50%",
  "tp2": "20@30%",
  "tp3": "40@20%"
}
```

This means:
- **TP1**: At +10 pips, close 50% (0.15 lots) and move SL to breakeven
- **TP2**: At +20 pips, close 30% (0.09 lots)
- **TP3**: At +40 pips, close remaining 20% (0.06 lots)

### Full Config Format

```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.30,
  "sl": 20,
  "partial_tp": {
    "tp1_pips": 10,
    "tp1_percent": 50,
    "tp2_pips": 20,
    "tp2_percent": 30,
    "tp3_pips": 40,
    "tp3_percent": 100,
    "move_sl_to_be_on_tp1": true,
    "trail_after_tp2": true,
    "trail_distance_pips": 15
  }
}
```

### Equal Split (No Percentages)

```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.30,
  "sl": 20,
  "tp1": 10,
  "tp2": 20,
  "tp3": 40
}
```

Defaults to 50% / 30% / 100% (remaining) split.

### What Happens Step by Step

1. Order placed: 0.30 lots BUY EURUSD, no broker-level TP set
2. Price hits TP1 (+10 pips): Close 0.15 lots, SL moves to breakeven
3. Price hits TP2 (+20 pips): Close 0.09 lots, trailing stop activates (if configured)
4. Price hits TP3 (+40 pips): Close remaining 0.06 lots

---

## Feature: Trailing Stop

### Method 1: With the trade

```json
{
  "action": "buy",
  "symbol": "XAUUSD",
  "lot": 0.1,
  "sl": 50,
  "tp": 200,
  "trailing": {
    "enabled": true,
    "activation_pips": 30,
    "distance_pips": 15,
    "step_pips": 5
  }
}
```

- **activation_pips**: Start trailing after 30 pips profit
- **distance_pips**: Trail 15 pips behind price
- **step_pips**: Only update SL when movement >= 5 pips (prevents micro-updates)

### Method 2: Activate later via signal

```json
{
  "action": "trailing",
  "symbol": "XAUUSD",
  "trailing": {
    "enabled": true,
    "activation_pips": 0,
    "distance_pips": 20,
    "step_pips": 5
  }
}
```

---

## Feature: Time-Based Exit

Auto-close position after N minutes:

```json
{
  "action": "buy",
  "symbol": "NAS100",
  "lot": 0.05,
  "sl": 30,
  "tp": 100,
  "time_exit_minutes": 120
}
```

The position closes automatically after 2 hours regardless of PnL.

---

## Feature: Risk-Based Position Sizing

Instead of specifying lot size, specify risk percentage:

```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "risk_percent": 1,
  "sl": 30,
  "tp": 60
}
```

The system calculates: `lot = (equity * 1%) / (30 pips * pip_value)` and clamps to max lot size.

---

## Feature: Magic Numbers

Use magic numbers to run multiple strategies on the same symbol:

```json
{"action":"buy","symbol":"XAUUSD","lot":0.05,"sl":50,"tp":100,"magic":1001,"comment":"EMA_Strategy"}
{"action":"buy","symbol":"XAUUSD","lot":0.03,"sl":30,"tp":80,"magic":1002,"comment":"RSI_Strategy"}
```

Each strategy's trades are identified separately in MT5.

---

## TradingView Alert Setup

### Step 1: Create Alert

1. Right-click on chart → "Add Alert" (or press Alt+A)
2. Set your condition (strategy order, indicator crossing, price level, etc.)

### Step 2: Configure Webhook

In the Notifications tab:
- Check "Webhook URL"
- Enter: `http://YOUR_VPS_IP:8003/webhook`

### Step 3: Set Alert Message

**For strategy-based alerts:**

```json
{
  "token": "your_secret_token",
  "action": "{{strategy.order.action}}",
  "symbol": "{{ticker}}",
  "lot": 0.1,
  "sl": {{plot("SL")}},
  "tp": {{plot("TP")}},
  "comment": "{{strategy.order.id}}"
}
```

**TradingView placeholders:**
| Placeholder | Replaced With |
|-------------|---------------|
| `{{strategy.order.action}}` | `buy` or `sell` |
| `{{ticker}}` | Symbol name (e.g., `XAUUSD`) |
| `{{strategy.order.id}}` | Entry ID from `strategy.entry()` |
| `{{plot("SL")}}` | Value of named plot |
| `{{close}}` | Current close price |
| `{{time}}` | Current bar time |

**For indicator-based alerts (manual action):**

```json
{"token":"your_token","action":"buy","symbol":"{{ticker}}","lot":0.1,"sl":50,"tp":100}
```

### Step 4: Set Alert Name and Expiration

- Name it descriptively (e.g., "XAUUSD EMA Cross BUY")
- Set expiration to "Open-ended" for always-active alerts

---

## Running Multiple Strategies

### Strategy 1: Scalping XAUUSD

```json
{
  "token": "your_token",
  "action": "{{strategy.order.action}}",
  "symbol": "XAUUSD",
  "lot": 0.05,
  "sl": 20,
  "tp": 40,
  "magic": 1001,
  "comment": "XAU_Scalp"
}
```

### Strategy 2: Swing EURUSD with Partial TP

```json
{
  "token": "your_token",
  "action": "{{strategy.order.action}}",
  "symbol": "EURUSD",
  "lot": 0.20,
  "sl": 40,
  "tp1": "15@50%",
  "tp2": "30@30%",
  "tp3": "60@20%",
  "magic": 1002,
  "comment": "EUR_Swing"
}
```

### Strategy 3: Breakout NAS100 with Trailing

```json
{
  "token": "your_token",
  "action": "{{strategy.order.action}}",
  "symbol": "NAS100",
  "lot": 0.02,
  "sl": 50,
  "tp": 300,
  "trailing": {"enabled":true,"activation_pips":40,"distance_pips":20,"step_pips":5},
  "magic": 1003,
  "comment": "NAS_Breakout"
}
```

All three alerts use the **same webhook URL**. PineConnector handles them independently with separate risk tracking per symbol.

---

## Dashboard

Open `http://YOUR_IP:8003/` in your browser:

- **Health bar**: Shows Rust engine, MT5 connection, ZMQ status
- **Analytics cards**: Net PnL, win rate, profit factor, max drawdown
- **Open trades**: Real-time table of active positions
- **Recent trades**: Closed trades with PnL
- **Close All button**: Emergency position closure

The dashboard auto-refreshes every 5 seconds.

---

## Emergency Controls

### Close all via dashboard

Click the red "Close All" button.

### Close all via API

```bash
curl -X POST http://localhost:8003/api/close-all
```

### Close all via TradingView alert

Create a manual alert with message:
```json
{"token":"your_token","action":"closeall","symbol":"ALL"}
```

---

## Monitoring

### Health check

```bash
curl http://localhost:8003/api/health
```

Returns:
```json
{
  "status": "ok",
  "rust_engine": "connected",
  "mt5_connected": true,
  "zmq_connected": true,
  "uptime_seconds": 3600.5,
  "trades_today": 7,
  "dry_run": false
}
```

### Trade history

```bash
# Last 50 trades
curl http://localhost:8003/api/trades

# Filter by symbol
curl "http://localhost:8003/api/trades?symbol=XAUUSD"

# Filter by status
curl "http://localhost:8003/api/trades?status=open"
```

### Analytics

```bash
curl "http://localhost:8003/api/analytics?days=30"
```
