# PineConnector — Trading Automation Platform

Hybrid Python + Rust system that bridges TradingView alerts to MetaTrader 5 with ultra-low latency execution, partial profit booking, and trailing stops.

## Architecture

```
TradingView Alert
  ↓ POST /webhook (token auth, <50ms)
Python FastAPI [port 8003] — parse, validate, risk check
  ↓ ZMQ PUSH tcp://127.0.0.1:5555
Trade Engine (tokio) — execution logic, partial TP, trailing stops
  ↓ ZMQ PUSH tcp://127.0.0.1:5556
MT5 Bridge — Python MetaTrader5 package OR MQL5 ZMQ EA
  ↓ ZMQ PUSH tcp://127.0.0.1:5557
Python — DB writes, Telegram notifications
```

## Setup

### Python

```bash
cd tools/pineconnector
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your webhook token, MT5 credentials, Telegram bot token
```

### Rust

```bash
cd tools/pineconnector/rust
cargo build --release
```

> Requires Rust toolchain and `libzmq` system library.
> On Windows: `vcpkg install zeromq` or download from https://zeromq.org

### MQL5 EA (alternative bridge)

1. Install [mql-zmq](https://github.com/dingmaotu/mql-zmq) library into MT5
2. Copy `mql5/PineConnector_EA.mq5` to your MT5 `Experts` folder
3. Compile and attach to any chart
4. Set `MT5_BRIDGE_MODE=mql5` in `.env`

## Running

### Start both services

```bash
# Terminal 1: Python webhook server
cd tools/pineconnector
py -3 run.py

# Terminal 2: Rust execution engine
cd tools/pineconnector/rust
cargo run --release
```

### Dry run mode (no real trades)

```bash
py -3 run.py --dry-run
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook` | Receive TradingView alerts |
| GET | `/api/health` | System health check |
| GET | `/api/trades` | List trades (query: limit, offset, symbol, status) |
| GET | `/api/trades/open` | List open trades |
| GET | `/api/analytics` | PnL, win rate, drawdown |
| GET | `/api/config` | Current config (no secrets) |
| POST | `/api/close-all` | Emergency close all positions |
| GET | `/` | Dashboard |

## Webhook Formats

### JSON (preferred)

```json
{
  "token": "your_secret_token",
  "action": "buy",
  "symbol": "XAUUSD",
  "lot": 0.1,
  "sl": 2300,
  "tp": 2350
}
```

### JSON with partial TP

```json
{
  "token": "your_secret_token",
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.3,
  "sl": 20,
  "partial_tp": {
    "tp1_pips": 10, "tp1_percent": 50,
    "tp2_pips": 20, "tp2_percent": 30,
    "tp3_pips": 40, "tp3_percent": 100,
    "move_sl_to_be_on_tp1": true,
    "trail_after_tp2": true,
    "trail_distance_pips": 15
  }
}
```

### JSON with shorthand TP levels

```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.3,
  "sl": 20,
  "tp1": "10@50%",
  "tp2": "20@30%",
  "tp3": "40@20%"
}
```

### Plain text (comma-separated)

```
your_token,buy,XAUUSD,sl=50,tp=100,lot=0.1
```

### Close commands

```json
{"action": "closebuy", "symbol": "EURUSD"}
{"action": "closesell", "symbol": "XAUUSD"}
{"action": "closeall", "symbol": "ALL"}
```

## Test Commands

```bash
# Buy with SL/TP
curl -X POST http://localhost:8003/webhook \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: your_secret_token" \
  -d '{"action":"buy","symbol":"XAUUSD","lot":0.01,"sl":50,"tp":100}'

# Buy with partial TP
curl -X POST http://localhost:8003/webhook \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: your_secret_token" \
  -d '{"action":"buy","symbol":"EURUSD","lot":0.10,"sl":20,"tp1":"10@50%","tp2":"20@30%","tp3":"40@20%"}'

# Close all
curl -X POST http://localhost:8003/webhook \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: your_secret_token" \
  -d '{"action":"closeall","symbol":"ALL"}'

# Health check
curl http://localhost:8003/api/health

# Analytics
curl http://localhost:8003/api/analytics?days=30
```

## TradingView Alert Setup

1. Create an alert on your TradingView strategy
2. Set webhook URL: `http://YOUR_VPS_IP:8003/webhook`
3. Set alert message (JSON format):

```
{"token":"your_secret_token","action":"{{strategy.order.action}}","symbol":"{{ticker}}","lot":0.1,"sl":{{plot("SL")}},"tp":{{plot("TP")}}}
```

## Risk Management

Configured in `configs/risk.yaml`:

- **Max lot size**: Rejects signals above limit
- **Max trades/day**: Daily trade cap
- **Max open/symbol**: Per-symbol position limit
- **Cooldown**: Minimum seconds between trades per symbol
- **Daily loss limit**: USD and percentage caps
- **Signal dedup**: Rejects duplicate signals within 5s window

## Deployment (VPS)

1. Provision a Windows VPS (MT5 requires Windows)
2. Install MT5, Python 3.11+, Rust toolchain
3. Clone repo, install dependencies
4. Configure `.env` with production credentials
5. Run both services (use `nssm` or Task Scheduler for auto-start)
6. Open firewall port 8003 for TradingView webhooks
7. Point TradingView alerts to `http://VPS_IP:8003/webhook`

## ZMQ Port Map

| Port | Socket | Direction | Purpose |
|------|--------|-----------|---------|
| 5555 | PUSH/PULL | Python → Rust | Validated signals |
| 5556 | PUSH/PULL | Rust → MT5 Bridge | Execution commands |
| 5557 | PUSH/PULL | MT5 Bridge → Python | Execution results |
| 5558 | PUB/SUB | Rust → Python | State updates |
| 5559 | PUSH/PULL | MT5 Bridge → Rust | Result copy for state tracking |
