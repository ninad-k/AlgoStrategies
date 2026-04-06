# PineConnector Architecture

## System Overview

PineConnector is a hybrid Python + Rust trading automation platform that bridges TradingView alerts to MetaTrader 5. The architecture separates concerns by language:

- **Python**: I/O-bound work (HTTP webhooks, MT5 API, database, notifications)
- **Rust**: CPU-bound, latency-critical work (execution engine, partial TP state machine, trailing stops)
- **ZeroMQ**: Ultra-fast inter-process communication (<10ms)

---

## High-Level Architecture

```
+------------------+
|   TradingView    |
|  (Cloud Alerts)  |
+--------+---------+
         | HTTP POST /webhook
         v
+------------------+     ZMQ PUSH      +-------------------+
|  Python FastAPI  | ----------------> |   Rust Engine     |
|  (Port 8003)     |  tcp://:5555      |   (Tokio async)   |
|                  |                   |                   |
|  - Auth          |  ZMQ PUB/SUB     |  - Partial TP FSM |
|  - Parse alert   | <--------------- |  - Trailing stops |
|  - Risk checks   |  tcp://:5558     |  - Breakeven      |
|  - DB writes     |                  |  - Time exit      |
|  - Notifications |                  |  - Retry logic    |
|  - Analytics     |                  |                   |
+------------------+                  +--------+----------+
         ^                                     |
         | ZMQ PUSH                            | ZMQ PUSH
         | tcp://:5557                         | tcp://:5556
         |                                     v
+--------+-----------------------------------+----------+
|                   MT5 Bridge                          |
|                                                       |
|  Option A: Python MetaTrader5 package (daemon thread) |
|  Option B: MQL5 ZMQ EA (runs inside MT5 terminal)    |
|                                                       |
+---------------------------+---------------------------+
                            |
                            v
                  +-------------------+
                  |   MetaTrader 5    |
                  |   (Broker)        |
                  +-------------------+
```

---

## Component Details

### 1. Python FastAPI Server (Port 8003)

**Responsibility**: Entry point for all external communication.

| Module | File | Role |
|--------|------|------|
| Webhook Handler | `main.py` | Receives POST /webhook, authenticates, dispatches |
| Alert Parser | `parser.py` | JSON + plain text format parsing |
| Risk Engine | `risk.py` | 7-check in-memory risk gate (<5ms) |
| ZMQ Producer | `queue.py` | Async PUSH to Rust, PULL from bridge, SUB from Rust |
| MT5 Bridge | `mt5_bridge.py` | Daemon thread executing MetaTrader5 API calls |
| Database | `database.py` | SQLite/PostgreSQL trade storage |
| Notifications | `notifications.py` | Telegram fire-and-forget alerts |
| Analytics | `analytics.py` | PnL, win rate, drawdown calculations |
| Config | `config.py` | dotenv-based configuration |

**Key Design Decisions:**
- Webhook response target: <50ms (minimal processing in request path)
- DB writes happen in background tasks (never block the webhook)
- MT5 bridge runs in a daemon thread (MT5 API is synchronous/blocking)
- Risk checks are pure in-memory computation (no I/O)

### 2. Rust Execution Engine

**Responsibility**: Latency-critical trade management.

| Module | File | Role |
|--------|------|------|
| Entry Point | `main.rs` | Tokio runtime, ZMQ threads, select! loop |
| Engine | `engine.rs` | Position management, signal dispatch, result handling |
| Partial TP | `partial_tp.rs` | 6-state finite state machine for multi-level profit booking |
| Trailing | `trailing.rs` | Trailing stop, breakeven, time-based exit |
| Queue | `queue.rs` | ZMQ thread spawners (OS threads bridged to tokio via mpsc) |
| Models | `models.rs` | Serde structs mirroring Python Pydantic models |
| Config | `config.rs` | Environment + YAML config loading |

**Threading Model:**
```
OS Thread 1: ZMQ PULL (bind :5555)  ──> mpsc::channel ──> Tokio Task
OS Thread 2: ZMQ PUSH (connect :5556) <── mpsc::channel <── Tokio Task
OS Thread 3: ZMQ PUB  (bind :5558)  <── mpsc::channel <── Tokio Task
OS Thread 4: ZMQ PULL (connect :5559) ──> mpsc::channel ──> Tokio Task

Tokio Runtime:
  select! {
    signal from channel   => engine.handle_signal()
    result from channel   => engine.handle_result()
    tick every 100ms      => engine.tick()  // trailing stops, time exits
    ctrl+c                => shutdown
  }
```

**Why OS threads for ZMQ?** The `zmq` Rust crate is synchronous. Rather than using unsafe async wrappers, we spawn dedicated OS threads for ZMQ I/O and bridge to the async tokio runtime via `mpsc::UnboundedChannel`. This is safe, simple, and adds negligible latency (~1 microsecond for channel send).

### 3. MT5 Bridge (Configurable)

**Option A: Python MetaTrader5 Package** (`MT5_BRIDGE_MODE=python`)
- Runs in a daemon thread inside the Python process
- Uses the official `MetaTrader5` Python package (Windows only)
- ZMQ PULL on :5556, ZMQ PUSH to :5557 and :5559
- Auto-reconnect: 5s intervals, up to 10 attempts

**Option B: MQL5 ZMQ EA** (`MT5_BRIDGE_MODE=mql5`)
- Runs as an Expert Advisor inside MetaTrader 5
- Uses the `mql-zmq` library for ZeroMQ inside MQL5
- Non-blocking receive in `OnTick()` handler
- Supports all order types: market, limit, stop

### 4. Dashboard (Port 8003)

Single-page HTML/JS application served by FastAPI:
- Real-time health status (Rust engine, MT5, ZMQ)
- Open/closed trades tables (auto-refresh 5s)
- Analytics cards (PnL, win rate, profit factor, drawdown)
- Emergency "Close All" button

---

## ZeroMQ Topology

```
                    Python                  Rust                    MT5 Bridge
                    ──────                  ────                    ──────────
Signal Flow:        PUSH ─────────────────> PULL (bind :5555)
                    (connect :5555)

Command Flow:                               PUSH ─────────────────> PULL (bind :5556)
                                            (connect :5556)

Result Flow:        PULL (bind :5557) <──────────────────────────── PUSH
                                                                    (connect :5557)

Rust Results:                               PULL <──────────────── PUSH
                                            (connect :5559)         (connect :5559)

State Updates:      SUB  <──────────────── PUB (bind :5558)
                    (connect :5558)
```

| Port | Pattern | Bind Side | Purpose |
|------|---------|-----------|---------|
| 5555 | PUSH/PULL | Rust binds | Validated signals (Python → Rust) |
| 5556 | PUSH/PULL | MT5 bridge binds | Execution commands (Rust → Bridge) |
| 5557 | PUSH/PULL | Python binds | Execution results (Bridge → Python) |
| 5558 | PUB/SUB | Rust binds | State updates (Rust → Python) |
| 5559 | PUSH/PULL | Rust connects | Result copy (Bridge → Rust) |

**Why PUSH/PULL over PUB/SUB for signals?** PUSH/PULL guarantees delivery — no message loss if the consumer is temporarily slow. PUB/SUB drops messages if the subscriber can't keep up, which is acceptable for state updates (latest state matters) but not for trade signals.

---

## Database Schema

```
signals ─────────── 1:1 ─────────── trades ─────────── 1:N ─────────── partial_closes
(raw webhook data)                  (trade lifecycle)                   (TP level closes)

daily_stats ── aggregated metrics per day
```

**SQLite default** (zero-config, file-based) with optional PostgreSQL via `DB_BACKEND=postgresql` config toggle.

---

## Security Model

1. **Token Authentication**: Every webhook must include `X-Auth-Token` header or `?token=` query param matching `WEBHOOK_TOKEN` in `.env`
2. **No secrets in responses**: `/api/config` returns system config but never tokens or passwords
3. **ZMQ on localhost only**: All ZMQ sockets bind to `127.0.0.1` — never exposed to network
4. **Input validation**: Pydantic models enforce types, ranges (`lot >= 0.01`), and enum values

---

## Latency Budget

| Stage | Target | Mechanism |
|-------|--------|-----------|
| Webhook receive + parse | <5ms | Async FastAPI, JSON pre-parse |
| Risk checks | <5ms | Pure in-memory, no I/O |
| ZMQ dispatch to Rust | <1ms | PUSH/PULL on localhost TCP |
| Rust signal processing | <1ms | Pre-computed hash maps, no allocation |
| ZMQ dispatch to MT5 bridge | <1ms | PUSH/PULL on localhost TCP |
| MT5 order execution | 50-500ms | Broker-dependent (network latency) |
| **Total webhook → order** | **<100ms** | Excluding broker latency |

The bottleneck is always the broker's execution speed, not PineConnector.
