# PineConnector Requirements Specification

## 1. Functional Requirements

### FR-01: Webhook Reception
- **FR-01.1**: Accept HTTP POST requests at `/webhook` endpoint
- **FR-01.2**: Support JSON content type (`application/json`)
- **FR-01.3**: Support plain text content type (`text/plain`)
- **FR-01.4**: Auto-detect JSON from body even with wrong content-type
- **FR-01.5**: Return structured JSON response with signal_id and status

### FR-02: Alert Parsing
- **FR-02.1**: Parse structured JSON alerts with typed fields
- **FR-02.2**: Parse comma-separated plain text alerts
- **FR-02.3**: Support partial TP shorthand (`tp1=10@50%`)
- **FR-02.4**: Support trailing stop shorthand keys
- **FR-02.5**: Case-insensitive action parsing
- **FR-02.6**: Flexible field mapping (e.g., `risk` maps to `risk_percent`)

### FR-03: Authentication
- **FR-03.1**: Token authentication via `X-Auth-Token` HTTP header
- **FR-03.2**: Token authentication via `?token=` query parameter
- **FR-03.3**: Token authentication via `token` field in JSON body
- **FR-03.4**: Token authentication via first field in plain text
- **FR-03.5**: Return HTTP 401 for invalid tokens
- **FR-03.6**: Bypass authentication when no token configured (dev mode)

### FR-04: Risk Management
- **FR-04.1**: Signal deduplication within configurable time window
- **FR-04.2**: Maximum lot size enforcement
- **FR-04.3**: Maximum daily trade count enforcement
- **FR-04.4**: Maximum open trades per symbol enforcement
- **FR-04.5**: Maximum total open trades enforcement
- **FR-04.6**: Per-symbol trade cooldown
- **FR-04.7**: Daily loss protection (USD amount)
- **FR-04.8**: Daily loss protection (equity percentage)
- **FR-04.9**: Risk-based lot sizing from equity percentage
- **FR-04.10**: Close/cancel commands bypass all risk checks

### FR-05: Order Execution
- **FR-05.1**: Market buy orders
- **FR-05.2**: Market sell orders
- **FR-05.3**: Buy limit pending orders
- **FR-05.4**: Sell limit pending orders
- **FR-05.5**: Buy stop pending orders
- **FR-05.6**: Sell stop pending orders
- **FR-05.7**: Close buy positions (per symbol)
- **FR-05.8**: Close sell positions (per symbol)
- **FR-05.9**: Close all positions (all symbols)
- **FR-05.10**: Modify SL/TP of existing positions
- **FR-05.11**: Non-blocking retry for transient errors (up to 3 attempts)

### FR-06: Partial Profit Booking
- **FR-06.1**: Support up to 3 take-profit levels
- **FR-06.2**: Percentage-based lot allocation per TP level
- **FR-06.3**: Equal-split default when no percentages specified
- **FR-06.4**: Move SL to breakeven on TP1 hit (configurable)
- **FR-06.5**: Activate trailing stop on TP2 hit (configurable)
- **FR-06.6**: Close all remaining on TP3 hit
- **FR-06.7**: Handle minimum lot constraints (close all if computed lot < min)
- **FR-06.8**: Lot rounding (floor to 0.01)

### FR-07: Trailing Stop
- **FR-07.1**: Configurable activation threshold (pips)
- **FR-07.2**: Configurable trail distance (pips)
- **FR-07.3**: Step enforcement (minimum SL movement to prevent micro-updates)
- **FR-07.4**: Direction-aware (only move SL in favorable direction)
- **FR-07.5**: Peak profit tracking

### FR-08: Trade Management
- **FR-08.1**: Breakeven (move SL to entry after threshold)
- **FR-08.2**: Time-based exit (auto-close after N minutes)
- **FR-08.3**: Magic number differentiation for multi-strategy

### FR-09: Notifications
- **FR-09.1**: Telegram alert on trade opened
- **FR-09.2**: Telegram alert on trade closed
- **FR-09.3**: Telegram alert on partial TP hit
- **FR-09.4**: Telegram alert on execution error
- **FR-09.5**: Fire-and-forget (never block execution)
- **FR-09.6**: Graceful degradation when Telegram unconfigured

### FR-10: Data & Analytics
- **FR-10.1**: Store all signals (accepted and rejected) in database
- **FR-10.2**: Store all trades with full lifecycle
- **FR-10.3**: Store partial close records
- **FR-10.4**: Calculate net PnL over configurable period
- **FR-10.5**: Calculate win rate, profit factor, expectancy
- **FR-10.6**: Calculate max drawdown (absolute and percentage)
- **FR-10.7**: Daily PnL breakdown

### FR-11: Dashboard
- **FR-11.1**: Real-time health status display
- **FR-11.2**: Open trades table with auto-refresh
- **FR-11.3**: Closed trades table
- **FR-11.4**: Analytics summary cards
- **FR-11.5**: Emergency close-all button

### FR-12: Configuration
- **FR-12.1**: Symbol mapping (TradingView to MT5 broker names)
- **FR-12.2**: Pip size configuration per symbol
- **FR-12.3**: Risk parameters via YAML config
- **FR-12.4**: Environment-based configuration (.env file)
- **FR-12.5**: Dry-run / paper trading mode

---

## 2. Non-Functional Requirements

### NFR-01: Performance
- **NFR-01.1**: Webhook response time < 50ms (p95)
- **NFR-01.2**: Signal dispatch to Trade engine < 10ms
- **NFR-01.3**: Risk check completion < 5ms
- **NFR-01.4**: No blocking I/O in the webhook request path
- **NFR-01.5**: Database writes executed asynchronously
- **NFR-01.6**: ZMQ message latency < 1ms on localhost

### NFR-02: Reliability
- **NFR-02.1**: MT5 auto-reconnect on connection loss
- **NFR-02.2**: Command queuing during MT5 disconnect (up to 50 commands)
- **NFR-02.3**: Graceful degradation on component failure
- **NFR-02.4**: No data loss on Python or Rust restart (DB persistence)
- **NFR-02.5**: Signal deduplication prevents double-execution

### NFR-03: Scalability
- **NFR-03.1**: Handle 100+ alerts per minute
- **NFR-03.2**: Support multiple concurrent strategies
- **NFR-03.3**: Support multiple symbols simultaneously
- **NFR-03.4**: SQLite for single-server, PostgreSQL for production

### NFR-04: Security
- **NFR-04.1**: Token-based authentication for all webhook requests
- **NFR-04.2**: ZMQ sockets bound to localhost only
- **NFR-04.3**: No secrets exposed in API responses
- **NFR-04.4**: Input validation on all incoming data (Pydantic)

### NFR-05: Maintainability
- **NFR-05.1**: Modular architecture (separate files per concern)
- **NFR-05.2**: Type hints on all Python functions
- **NFR-05.3**: Strong typing in Rust (serde derive)
- **NFR-05.4**: Structured logging with module names
- **NFR-05.5**: Unit tests for partial TP and trailing stop logic

### NFR-06: Operability
- **NFR-06.1**: Health check endpoint with component status
- **NFR-06.2**: Web dashboard for monitoring
- **NFR-06.3**: CLI flags for host, port, dry-run
- **NFR-06.4**: Startup banner with configuration summary

---

## 3. Technical Constraints

| Constraint | Reason |
|-----------|--------|
| Windows OS required | MetaTrader 5 only runs on Windows |
| MT5 terminal must be running | Python MT5 package requires active terminal |
| ZMQ on TCP (not IPC) | Windows does not support Unix domain sockets |
| Rust ZMQ in OS threads | `zmq` crate is synchronous, bridged to tokio via mpsc |
| Single-threaded engine logic | Prevents race conditions on position state |

---

## 4. Dependencies

### Python
| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >= 0.115 | HTTP server |
| uvicorn | >= 0.30 | ASGI server |
| pydantic | >= 2.0 | Data validation |
| pyzmq | >= 25.0 | ZeroMQ bindings |
| MetaTrader5 | >= 5.0.45 | MT5 API |
| aiohttp | >= 3.9 | Async HTTP (Telegram) |
| PyYAML | >= 6.0 | Config parsing |
| python-dotenv | >= 1.0 | Environment config |
| asyncpg | >= 0.29 | PostgreSQL (optional) |

### Rust
| Crate | Version | Purpose |
|-------|---------|---------|
| tokio | 1.x | Async runtime |
| zmq | 0.10 | ZeroMQ bindings |
| serde / serde_json | 1.0 | Serialization |
| serde_yaml | 0.9 | YAML config |
| chrono | 0.4 | Time handling |
| uuid | 1.x | Unique IDs |
| tracing | 0.1 | Structured logging |
| anyhow | 1.0 | Error handling |
