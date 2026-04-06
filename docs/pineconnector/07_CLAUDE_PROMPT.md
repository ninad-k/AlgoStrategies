# Claude Prompt — Building PineConnector

This document preserves the exact prompt used to generate the PineConnector trading automation platform using Claude Code. It can be reused to regenerate, extend, or adapt the platform.

---

## System Context Prompt

```
You are a senior systems architect, Rust developer, and Python backend engineer
specializing in low-latency trading systems.
```

---

## Full Build Prompt

```
Build a production-grade PineConnector-like trading automation platform using
a hybrid architecture:

- Rust: latency-critical execution engine
- Python: orchestration, API, risk management, and monitoring

The system must be modular, ultra-low latency, fault-tolerant, and production-ready.

-----------------------------------
### CORE ARCHITECTURE (IMPORTANT)
-----------------------------------
Design a hybrid system:

1. Python Layer (FastAPI):
   - Receives TradingView webhooks
   - Validates, parses, and enqueues signals
   - Handles risk management and configuration

2. Rust Layer (Execution Engine):
   - Consumes signals from queue
   - Executes trades with minimal latency
   - Maintains persistent connection with trading platform

3. Communication:
   - Use ultra-fast IPC:
     - Option 1: ZeroMQ (preferred)
     - Option 2: Redis (fallback)
     - Option 3: TCP socket

4. Execution Flow:
   TradingView -> Python Webhook -> Queue -> Trade Engine -> Broker/MT5

-----------------------------------
### PHASE 1: PYTHON WEBHOOK (FASTAPI)
-----------------------------------
Build async FastAPI server:

- POST /webhook
- Accept JSON and plain text alerts

Preferred format (fast parsing):
{
  "action": "BUY",
  "symbol": "EURUSD",
  "lot": 0.3,
  "sl": 20,
  "tp": 40
}

Requirements:
- Async/await (non-blocking)
- Response time < 50ms
- Secret token authentication
- Input validation
- Minimal processing in request path

-----------------------------------
### PHASE 2: RISK MANAGEMENT (PYTHON)
-----------------------------------
Implement:

- Max lot size
- Max trades per day
- Max open trades per symbol
- Equity protection
- Spread filter
- Trade cooldown

IMPORTANT:
- Risk checks must be fast and non-blocking

-----------------------------------
### PHASE 3: RUST EXECUTION ENGINE (LOW LATENCY)
-----------------------------------
Build a Rust service:

Requirements:
- Ultra-fast signal processing
- Persistent connection with MT5 or broker
- No re-initialization per trade
- Multi-threaded or async (Tokio)

Functions:
- place_order
- close_order
- modify_order

Features:
- Retry mechanism (non-blocking)
- Symbol mapping
- Support:
  - Market orders
  - Pending orders
  - Close commands

-----------------------------------
### PHASE 4: PARTIAL PROFIT BOOKING (CRITICAL FEATURE)
-----------------------------------
Implement multi-level TP (max 3 levels)

Supported formats:

1. Equal split:
BUY EURUSD LOT=0.3 SL=20 TP1=10 TP2=20 TP3=40

2. Percentage-based:
BUY EURUSD LOT=0.3 SL=20 TP1=10@50% TP2=20@30% TP3=40@20%

Execution strategy (LOW LATENCY OPTIMIZED):
- Prefer SINGLE order + partial close logic (handled in Rust)
- Avoid multiple order placement when possible

Logic:
- TP1 hit -> close partial + move SL to breakeven
- TP2 hit -> close partial + optional trailing SL
- TP3 hit -> close remaining

-----------------------------------
### PHASE 5: TRADE MANAGEMENT (RUST + PYTHON)
-----------------------------------
- Trailing stop (Rust preferred)
- Break-even logic
- Time-based exit
- Sync trade state between Rust and Python

-----------------------------------
### PHASE 6: NOTIFICATIONS (PYTHON)
-----------------------------------
- Telegram alerts:
  - Trade executed
  - TP/SL hit
  - Errors

-----------------------------------
### PHASE 7: DATA & ANALYTICS (PYTHON)
-----------------------------------
- Store trades in DB (PostgreSQL or SQLite)
- Track:
  - PnL
  - Win rate
  - Drawdown

IMPORTANT:
- DB writes must be async or batched (not in execution path)

-----------------------------------
### LOW LATENCY REQUIREMENTS (CRITICAL)
-----------------------------------
- Webhook response < 50ms
- Signal dispatch to Rust < 10ms
- No blocking I/O in critical path
- Use in-memory queue or ZeroMQ
- Keep MT5 connection persistent
- Avoid heavy logging in execution path
- Pre-parse structured JSON alerts

-----------------------------------
### SECURITY
-----------------------------------
- Token authentication
- Optional IP whitelist
- Input sanitization

-----------------------------------
### PROJECT STRUCTURE
-----------------------------------
python/
  api/
  risk/
  parser/
  config/
  notifications/
  db/

rust/
  src/
    main.rs
    execution.rs
    queue.rs
    risk.rs

-----------------------------------
### DELIVERABLES
-----------------------------------
Provide:

1. Full Python code (FastAPI, risk engine, queue producer)
2. Full Rust code (execution engine)
3. Communication setup (ZeroMQ or TCP)
4. requirements.txt (Python)
5. Cargo.toml (Rust)
6. Config examples
7. Example TradingView alerts
8. curl test request
9. Setup instructions (Python + Rust)
10. Run instructions (both services)
11. Deployment guide (VPS)

-----------------------------------
### BONUS FEATURES
-----------------------------------
- Dry-run / paper trading mode
- Multi-account support
- Auto-reconnect logic
- Health check endpoint

-----------------------------------
### CODING STANDARDS
-----------------------------------
- Clean architecture
- Modular design
- Type hints (Python) + strong typing (Rust)
- Proper error handling
- Minimal latency-focused design

-----------------------------------
### OUTPUT FORMAT
-----------------------------------
1. Architecture explanation
2. Python code (file-by-file)
3. Rust code (file-by-file)
4. Setup & run instructions
5. Example alerts

Focus on performance, reliability, and real-world trading usage.
```

---

## Design Decisions Made During Build

| Decision | Choice | Rationale |
|----------|--------|-----------|
| MT5 connectivity | Both Python bridge + MQL5 EA (configurable) | Maximum flexibility |
| Project location | `tools/pineconnector/` | Consistent with existing tools pattern |
| Database | SQLite default, PostgreSQL optional | Zero setup for development, PG for production |
| ZMQ pattern | PUSH/PULL (signals), PUB/SUB (state) | Guaranteed delivery for trades, latest-wins for state |
| ZMQ transport | TCP on localhost | Windows has no Unix socket support |
| Rust ZMQ threading | OS threads bridged to tokio via mpsc | `zmq` crate is synchronous |
| Partial TP design | Single order + partial close | Lower latency than multiple orders |
| Risk checks | All in-memory, no I/O | <5ms target |
| DB writes | Background async tasks | Never block webhook response |

---

## How to Adapt This Prompt

### For a different broker (not MT5):
Replace Phase 3's "MT5" references with your broker's API. The Trade engine and Python webhook layer remain unchanged — only the bridge needs swapping.

### For cryptocurrency exchanges:
Replace the MT5 bridge with exchange API calls (Binance, Bybit, etc.). Add WebSocket price feed for real-time trailing stop updates instead of relying on execution results.

### For different alert sources (not TradingView):
The webhook endpoint accepts standard HTTP POST. Any system that can send JSON via HTTP works — custom scripts, other charting platforms, cron jobs, etc.

### To add more TP levels:
Extend `PartialTPConfig` in both `python/models.py` and `rust/src/models.rs`. Extend the state machine in `rust/src/partial_tp.rs` with `WaitingTP4`, `TP4Hit`, etc.
