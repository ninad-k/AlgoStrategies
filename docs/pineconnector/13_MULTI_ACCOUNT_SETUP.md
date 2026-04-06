# Multi-Account & Multi-Alert Setup Guide

**Version**: 1.0
**Last Updated**: April 2026

This guide explains how to configure PineConnector for managing multiple MT5 accounts with different connection types and multiple alert sources simultaneously.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Multi-Instance Setup](#multi-instance-setup)
3. [Connection Types](#connection-types)
4. [Multi-Alert Routing](#multi-alert-routing)
5. [Magic Numbers](#magic-numbers)
6. [Configuration Examples](#configuration-examples)
7. [Monitoring Multiple Accounts](#monitoring-multiple-accounts)
8. [Best Practices](#best-practices)

---

## Architecture Overview

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    TradingView Platform                      │
│  (Multiple Strategies, Multiple Alert Rules)                 │
└──────────────┬──────────────┬──────────────┬─────────────────┘
               │              │              │
        ┌──────▼────┐  ┌──────▼────┐  ┌──────▼────┐
        │ Strategy A │  │ Strategy B │  │ Strategy C │
        │  (Trend)   │  │(Momentum)  │  │ (Range)    │
        └──────┬────┘  └──────┬────┘  └──────┬────┘
               │              │              │
               └──────────────┼──────────────┘
                              │
                    HTTP POST /webhook
                    (Single Endpoint)
                              │
        ┌─────────────────────▼──────────────────────┐
        │    PineConnector Instance #1               │
        │  (Account: Live Trading, Magic: 1001)      │
        │                                            │
        │  ├─ FastAPI Webhook Receiver               │
        │  ├─ Risk Management Gates                  │
        │  ├─ Trade Engine (Rust)                    │
        │  └─ MT5 Bridge (Python Package)            │
        │      └─> MT5 Account #1                    │
        └────────────────────────────────────────────┘
               │
        ┌──────▼─────────────────────────────────────┐
        │    PineConnector Instance #2               │
        │  (Account: Demo, Magic: 2001)              │
        │                                            │
        │  ├─ FastAPI Webhook Receiver (Port 8004)   │
        │  ├─ Risk Management Gates                  │
        │  ├─ Trade Engine (Rust)                    │
        │  └─ MT5 Bridge (MQL5 EA)                   │
        │      └─> MT5 Account #2                    │
        └────────────────────────────────────────────┘
               │
        ┌──────▼─────────────────────────────────────┐
        │    PineConnector Instance #3               │
        │  (Account: Copy Trading, Magic: 3001)      │
        │                                            │
        │  ├─ FastAPI Webhook Receiver (Port 8005)   │
        │  ├─ Risk Management Gates                  │
        │  ├─ Trade Engine (Rust)                    │
        │  └─ MT5 Bridge (Python Package)            │
        │      └─> MT5 Account #3                    │
        └────────────────────────────────────────────┘
```

---

## Multi-Instance Setup

### Running Multiple Instances

Each PineConnector instance runs independently on a different port:

**Instance 1 - Live Trading Account**
```bash
python run.py --port 8003 --config live.yaml
```
- Connects to live MT5 account
- Database: `trades_live.db`
- Magic numbers: 1001-1999
- Risk limit: $5000 daily

**Instance 2 - Demo Account**
```bash
python run.py --port 8004 --config demo.yaml
```
- Connects to demo MT5 account
- Database: `trades_demo.db`
- Magic numbers: 2001-2999
- Risk limit: Unlimited (testing)

**Instance 3 - Copy Trading Account**
```bash
python run.py --port 8005 --config copytrade.yaml
```
- Connects to copy trading account
- Database: `trades_copy.db`
- Magic numbers: 3001-3999
- Risk limit: $2000 daily

### Instance Configuration (YAML)

**live.yaml**
```yaml
server:
  host: 0.0.0.0
  port: 8003
  reload: false

database:
  url: sqlite:///./data/trades_live.db
  backend: sqlite

mt5:
  account: 123456789
  password: your_password
  server: MetaQuotes-Live
  magic_base: 1000

risk_management:
  enabled: true
  max_trades_per_day: 20
  max_drawdown_percent: 10.0
  daily_loss_limit: 5000.00
  dedup_window_seconds: 30

telegram:
  enabled: true
  bot_token: your_token
  chat_id: your_chat_id

zmq:
  signal_port: 5555
  command_port: 5556
  result_port: 5557
  state_port: 5558
```

**demo.yaml**
```yaml
server:
  host: 0.0.0.0
  port: 8004
  reload: false

database:
  url: sqlite:///./data/trades_demo.db
  backend: sqlite

mt5:
  account: 987654321
  password: demo_password
  server: MetaQuotes-Demo
  magic_base: 2000

risk_management:
  enabled: false  # No limits for testing

dry_run: false  # Real execution on demo
```

**copytrade.yaml**
```yaml
server:
  host: 0.0.0.0
  port: 8005
  reload: false

database:
  url: postgresql://user:pass@localhost/pineconnector_copy
  backend: postgresql

mt5:
  account: 555666777
  password: copy_password
  server: MetaQuotes-Live
  magic_base: 3000

risk_management:
  enabled: true
  max_trades_per_day: 50
  max_open_per_symbol: 10
  daily_loss_limit: 2000.00
```

---

## Connection Types

### Type 1: Python MetaTrader5 Package

**Advantages:**
- Direct DLL integration
- Lower latency (~50ms)
- Real-time execution
- Full position control

**How it works:**
```
TradingView Signal
    ↓
FastAPI /webhook
    ↓
Risk Validation
    ↓
ZMQ PUSH to Trade Engine
    ↓
MT5 Bridge (Python daemon)
    ↓
MetaTrader5 DLL
    ↓
MT5 Terminal (local)
    ↓
Execution (real-time)
```

**Requirements:**
- MT5 installed on same machine
- Account logged in
- Windows OS (for direct DLL)

**Configuration:**
```python
# mt5_bridge.py uses MetaTrader5 package
import MetaTrader5 as mt5

mt5.initialize(
    path="C:\\Program Files\\MetaTrader 5\\terminal64.exe",
    login=123456789,
    password="your_password",
    server="MetaQuotes-Live"
)
```

**Bridge Flow:**
```
ZMQ PULL Socket (port 5556)
    ↓
Receive ExecutionCommand
    ↓
Extract: symbol, action, lot, sl, tp
    ↓
Validate position (if modify/close)
    ↓
Execute via CTrade (MQL5 wrapper)
    ↓
Send result back via ZMQ PUSH (port 5557)
    ↓
Update database with ticket & execution details
```

### Type 2: MQL5 Expert Advisor (Network-Based)

**Advantages:**
- Works remotely (VPS)
- No local MT5 needed
- Flexible deployment
- Scalable

**How it works:**
```
TradingView Signal
    ↓
FastAPI /webhook
    ↓
Risk Validation
    ↓
ZMQ PUSH to Trade Engine
    ↓
Network ZMQ Socket
    ↓
MQL5 Expert Advisor
    ↓
MT5 Terminal (remote/VPS)
    ↓
Execution (network latency ~100-200ms)
```

**Requirements:**
- MQL5 EA running in MT5
- Network connectivity
- ZMQ library in MT5
- Open ports for ZMQ

**MQL5 EA Code Structure:**
```mql5
// PineConnector_EA.mq5

#include <zmq/zmq.mqh>

// Global socket for receiving commands
void OnInit() {
    // Create ZMQ socket on port 5556
    socket = zmq_socket(ZMQ_PULL);
    zmq_bind(socket, "tcp://0.0.0.0:5556");
}

void OnTick() {
    // Poll for incoming commands (non-blocking)
    if (zmq_recv(socket, command, timeout=0)) {
        // Parse command
        string action = command["action"];
        string symbol = command["symbol"];
        double lot = command["lot"];
        double sl = command["sl"];
        double tp = command["tp"];

        // Execute trade
        trade.Buy(lot, symbol, 0, sl, tp);

        // Send result back via ZMQ PUSH
        zmq_send(result_socket, result_json);
    }
}

void OnDeinit(const int reason) {
    zmq_close(socket);
}
```

**Bridge Flow:**
```
ZMQ Network Socket (port 5556)
    ↓
Receive ExecutionCommand from Trade Engine
    ↓
Parse JSON (action, symbol, lot, sl, tp)
    ↓
Validate (enough margin, valid symbol)
    ↓
Execute via CTrade class
    ↓
Store ticket & results
    ↓
Send result via ZMQ PUSH (port 5557)
```

### Type 3: REST API Bridge (Alternative)

For advanced setups, you can also use REST API instead of ZMQ:

```python
# Alternative: REST API bridge to remote MT5
import requests

def send_signal_via_rest(signal_data):
    response = requests.post(
        "http://vps-ip:8006/api/execute",
        json={
            "action": signal_data["action"],
            "symbol": signal_data["symbol"],
            "lot": signal_data["lot"],
            "sl": signal_data["sl"],
            "tp": signal_data["tp"],
            "token": "secret_token"
        },
        timeout=5
    )
    return response.json()
```

---

## Multi-Alert Routing

### Alert Routing Strategy

```
┌──────────────────────────────┐
│  TradingView Alert Received  │
│  POST /webhook               │
│  {action, symbol, lot, ...}  │
└────────────┬─────────────────┘
             │
     ┌───────▼────────┐
     │ Extract Fields │
     │ - action       │
     │ - symbol       │
     │ - lot          │
     │ - magic (1001) │
     │ - token        │
     └───────┬────────┘
             │
    ┌────────▼────────────┐
    │ Validate Token      │
    │ (Check signature)   │
    └────────┬────────────┘
             │
    ┌────────▼────────────┐
    │ Route by Magic #    │
    │ 1001-1999: Inst #1  │
    │ 2001-2999: Inst #2  │
    │ 3001-3999: Inst #3  │
    └────────┬────────────┘
             │
    ┌────────▼────────────┐
    │ Run Risk Gates      │
    │ - Dedup             │
    │ - Lot size          │
    │ - Daily limit       │
    │ - Equity protection │
    └────────┬────────────┘
             │
    ┌────────▼────────────┐
    │ Send to Trade Eng.  │
    │ (ZMQ PUSH)          │
    └────────┬────────────┘
             │
    ┌────────▼────────────┐
    │ Log & Database      │
    │ - Signal ID         │
    │ - Status (accept)   │
    │ - Timestamp         │
    └─────────────────────┘
```

### Real Alert Examples

**Alert 1: Trend Strategy → Instance #1 (Live)**
```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.10,
  "sl": 1.0850,
  "tp": 1.0950,
  "magic": 1001,
  "comment": "Trend_EMA_Crossover",
  "token": "live_token_xyz"
}
```
→ Routes to Instance #1 on port 8003 (Live Account)

**Alert 2: Momentum Strategy → Instance #2 (Demo)**
```json
{
  "action": "buy",
  "symbol": "GBPUSD",
  "lot": 0.50,
  "sl": 1.2500,
  "tp": 1.2600,
  "magic": 2001,
  "comment": "Momentum_RSI",
  "token": "demo_token_abc"
}
```
→ Routes to Instance #2 on port 8004 (Demo Account)

**Alert 3: Range Strategy → Instance #3 (Copy Trading)**
```json
{
  "action": "sell",
  "symbol": "XAUUSD",
  "lot": 0.50,
  "sl": 1950,
  "tp": 1930,
  "magic": 3001,
  "comment": "Range_Bollinger",
  "token": "copy_token_def"
}
```
→ Routes to Instance #3 on port 8005 (Copy Trading Account)

---

## Magic Numbers

### Magic Number Strategy

Magic numbers identify which strategy/instance sent a trade:

**Structure:** `XYYY` (4 digits)
- `X` = Instance (1, 2, 3...)
- `YYY` = Strategy (001, 002, 003...)

**Examples:**

| Magic | Instance | Strategy | Purpose |
|-------|----------|----------|---------|
| 1001 | 1 (Live) | 001 | Trend EMA Strategy |
| 1002 | 1 (Live) | 002 | Momentum RSI Strategy |
| 1003 | 1 (Live) | 003 | Range Bollinger Strategy |
| 2001 | 2 (Demo) | 001 | Testing Trend EMA |
| 2002 | 2 (Demo) | 002 | Testing Momentum RSI |
| 3001 | 3 (Copy) | 001 | Copy Trend EMA |
| 3002 | 3 (Copy) | 002 | Copy Momentum RSI |

### Benefits of Magic Numbers

1. **Trade Identification**: Know which strategy made each trade
2. **Instance Routing**: Automatically route to correct account
3. **Selective Close**: Close only specific strategy's trades
4. **Analytics**: Analyze performance per strategy
5. **Risk Limits**: Different risk per strategy

### Example: Close Specific Strategy

Close all trades from Trend Strategy (magic 1001):

```
POST /webhook
{
  "action": "closeall",
  "symbol": "EURUSD",
  "magic": 1001,
  "comment": "Close Trend Strategy"
}
```

---

## Configuration Examples

### Scenario 1: Live + Demo + Copy Trading

**Directory Structure:**
```
tools/pineconnector/
├── config/
│   ├── live.yaml
│   ├── demo.yaml
│   └── copytrade.yaml
├── data/
│   ├── trades_live.db
│   ├── trades_demo.db
│   └── trades_copy_postgresql/
├── logs/
│   ├── instance_8003.log
│   ├── instance_8004.log
│   └── instance_8005.log
└── run.py
```

**Start Script (start_all.sh):**
```bash
#!/bin/bash

# Start Instance 1 (Live)
nohup python run.py --port 8003 --config live.yaml > logs/instance_8003.log 2>&1 &
sleep 2

# Start Instance 2 (Demo)
nohup python run.py --port 8004 --config demo.yaml > logs/instance_8004.log 2>&1 &
sleep 2

# Start Instance 3 (Copy Trading)
nohup python run.py --port 8005 --config copytrade.yaml > logs/instance_8005.log 2>&1 &

echo "All instances started"
ps aux | grep "python run.py"
```

**TradingView Alert for All Instances:**
```
{
  "action": "{{strategy.action}}",
  "symbol": "{{syminfo.tickerid}}",
  "lot": {{strategy.lot}},
  "sl": {{strategy.sl}},
  "tp": {{strategy.tp}},
  "magic": {{strategy.magic}},
  "comment": "{{strategy.name}}",
  "token": "{{strategy.token}}"
}
```

### Scenario 2: Multiple Strategies on Same Account

```
Instance #1 (Port 8003) - Live Account
├─ Strategy A (Magic 1001): Trend EMA
├─ Strategy B (Magic 1002): Momentum RSI
└─ Strategy C (Magic 1003): Range Bollinger

Instance #2 (Port 8004) - Demo Account
├─ Strategy A (Magic 2001): Trend EMA (testing)
└─ Strategy B (Magic 2002): Momentum RSI (testing)
```

**All alerts → /webhook endpoint, routed by magic number**

---

## Monitoring Multiple Accounts

### Dashboard for Each Instance

**Instance #1 (Port 8003):**
```
http://localhost:8003
```

**Instance #2 (Port 8004):**
```
http://localhost:8004
```

**Instance #3 (Port 8005):**
```
http://localhost:8005
```

Each dashboard shows:
- Trades specific to that account
- PnL for that account
- Risk metrics for that account
- Health status of that MT5 connection

### Centralized Monitoring (Advanced)

**Docker Compose Setup:**
```yaml
version: '3.8'
services:
  pineconnector_live:
    build: .
    ports:
      - "8003:8003"
    environment:
      - PORT=8003
      - CONFIG=live.yaml
    volumes:
      - ./data/trades_live.db:/app/data/trades_live.db
    networks:
      - pineconnector

  pineconnector_demo:
    build: .
    ports:
      - "8004:8004"
    environment:
      - PORT=8004
      - CONFIG=demo.yaml
    volumes:
      - ./data/trades_demo.db:/app/data/trades_demo.db
    networks:
      - pineconnector

  pineconnector_copy:
    build: .
    ports:
      - "8005:8005"
    environment:
      - PORT=8005
      - CONFIG=copytrade.yaml
    volumes:
      - ./data/trades_copy.db:/app/data/trades_copy.db
    networks:
      - pineconnector

networks:
  pineconnector:
```

**Start all instances:**
```bash
docker-compose up -d
```

### Centralized API Gateway (Nginx)

```nginx
upstream instance_live {
    server 127.0.0.1:8003;
}

upstream instance_demo {
    server 127.0.0.1:8004;
}

upstream instance_copy {
    server 127.0.0.1:8005;
}

# Route to specific instance by header
server {
    listen 8000;
    server_name _;

    location / {
        if ($http_x_instance = "live") {
            proxy_pass http://instance_live;
        }
        if ($http_x_instance = "demo") {
            proxy_pass http://instance_demo;
        }
        if ($http_x_instance = "copy") {
            proxy_pass http://instance_copy;
        }
        # Default to live
        proxy_pass http://instance_live;
    }
}
```

**Usage:**
```bash
# Route to demo instance
curl -H "X-Instance: demo" http://localhost:8000/api/trades

# Route to copy trading instance
curl -H "X-Instance: copy" http://localhost:8000/api/health
```

---

## Best Practices

### 1. **Magic Number Convention**
- Document magic numbers clearly
- Use consistent numbering
- Avoid overlaps
- Include in strategy name

### 2. **Token Security**
- Different token per instance
- Rotate tokens regularly
- Store in secure environment variables
- Use strong random tokens (32+ chars)

### 3. **Risk Management Per Instance**
```yaml
Instance #1 (Live):
  - max_trades_per_day: 20
  - daily_loss_limit: $5000
  - max_drawdown: 10%

Instance #2 (Demo):
  - max_trades_per_day: unlimited
  - daily_loss_limit: disabled
  - max_drawdown: disabled

Instance #3 (Copy Trading):
  - max_trades_per_day: 50
  - daily_loss_limit: $2000
  - max_drawdown: 5%
```

### 4. **Logging and Monitoring**
- Separate log files per instance
- Centralized logging (ELK, Splunk)
- Alert on instance failures
- Dashboard for all accounts

### 5. **Testing Before Live**
1. Test strategy on Instance #2 (Demo)
2. Verify logic and execution
3. Validate risk parameters
4. Deploy to Instance #1 (Live)

### 6. **Backup and Recovery**
```bash
# Backup databases
cp data/trades_live.db backups/trades_live_$(date +%Y%m%d_%H%M%S).db
cp data/trades_demo.db backups/trades_demo_$(date +%Y%m%d_%H%M%S).db
cp data/trades_copy.db backups/trades_copy_$(date +%Y%m%d_%H%M%S).db

# Backup configs
cp config/*.yaml backups/configs_$(date +%Y%m%d_%H%M%S)/
```

### 7. **Connection Redundancy**
```python
# Failover logic in MT5 bridge
max_retries = 3
retry_delay = 5  # seconds

while not connected and retries < max_retries:
    try:
        mt5.initialize()
        connected = True
    except ConnectionError:
        retries += 1
        time.sleep(retry_delay)

if not connected:
    send_alert("MT5 Bridge disconnected", "CRITICAL")
    # Pause trading or fallback
```

---

## Troubleshooting Multi-Account Issues

### Issue: Signal Not Routed to Correct Instance

**Cause**: Magic number mismatch

**Solution**:
```bash
# Check signal received
curl http://localhost:8003/api/trades | grep magic

# Verify magic number in TradingView alert
# Should match instance magic range (1001-1999, 2001-2999, etc)
```

### Issue: Different Risk Limits Not Applied

**Cause**: Configuration file not loaded

**Solution**:
```bash
# Verify config path
python run.py --port 8003 --config /full/path/to/live.yaml

# Check config loaded
curl http://localhost:8003/api/config | grep risk_management
```

### Issue: MT5 Connections Conflicting

**Cause**: Same account logged in multiple instances

**Solution**:
```python
# Each instance must use DIFFERENT MT5 account
# Instance 1: Account 123456789
# Instance 2: Account 987654321
# Instance 3: Account 555666777
```

### Issue: Database Locks

**Cause**: Multiple instances accessing same database

**Solution**:
```yaml
# Use DIFFERENT database per instance
Instance 1: trades_live.db
Instance 2: trades_demo.db
Instance 3: trades_copy.db

# OR use PostgreSQL for concurrent access
Instance 1: postgresql://host/trades_live
Instance 2: postgresql://host/trades_demo
Instance 3: postgresql://host/trades_copy
```

---

## Summary

| Feature | Single Instance | Multi-Instance |
|---------|-----------------|-----------------|
| **Accounts** | 1 MT5 account | Multiple MT5 accounts |
| **Strategies** | Multiple (same account) | Multiple per account |
| **Connections** | 1 type (Python/MQL5) | Mixed types possible |
| **Alerts** | All → same instance | Routed by magic number |
| **Risk Limits** | Global | Per instance |
| **Dashboard** | 1 view | Multiple views |
| **Database** | Single | Per instance |
| **Scalability** | Limited | Unlimited |

**Recommended Configuration:**
- **Development**: 1 instance (demo) on port 8003
- **Production**: 2-3 instances on ports 8003-8005
- **Enterprise**: Docker/Kubernetes with load balancer
