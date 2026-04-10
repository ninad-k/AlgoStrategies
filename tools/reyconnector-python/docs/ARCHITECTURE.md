# ReyConnector - Architecture Diagram

## Overview

ReyConnector is a cloud-based **TradingView -> MT5 bridge** built as a 3-service Python microservice stack. It receives webhook alerts from TradingView, logs them as signals, and (in future phases) routes them to MetaTrader 5 for order execution via a pluggable Execution Engine.

**Stack**: Python 3.11+, FastAPI, Pydantic v2, httpx, uvicorn

---

## System Architecture

```
                     EXTERNAL SYSTEMS
 +-----------------+                       +-----------------+
 |  TradingView    |                       |  Portal Web UI  |
 |  (Pine Script   |                       |  (Angular SPA)  |
 |   Alerts)       |                       |  localhost:4200  |
 +--------+--------+                       +--------+--------+
          |                                         |
          | POST /v1/webhook                        | GET /api/v1/*
          | ?connection_id=conn-demo-001            |
          | Body: "ema200,buy,EURUSD"               |
          |                                         |
 =========|=========================================|=================
          |           REYCONNECTOR SERVICES         |
          |                                         |
          v                                         v
 +--------+------------------+     +----------------+----------------+
 |  WEBHOOK INGEST           |     |  CONTROL API                    |
 |  Port: 5242               |     |  Port: 5241                     |
 |                            |     |                                 |
 |  FastAPI Application      |     |  FastAPI Application            |
 |  Title: "ReyConnector     |     |  Title: "ReyConnector           |
 |          Webhook Ingest"  |     |          Control API"           |
 |                            |     |                                 |
 |  Endpoints:               |     |  CORS:                          |
 |  POST /v1/webhook         |     |  - localhost:4200 (http/https)  |
 |  GET  /health             |     |                                 |
 |                            |     |  Endpoints:                     |
 |  Responsibilities:        |     |  GET  /health                   |
 |  - Receive raw webhooks   |     |  GET  /api/v1/connections       |
 |  - Create alert envelope  |     |  GET  /api/v1/signals?take=N    |
 |  - Forward to Control API |     |  POST /api/internal/v1/signals  |
 |                            |     |                                 |
 +--------+------------------+     +---+----+------------------------+
          |                            |    ^
          | POST /api/internal/        |    |
          |   v1/signals               |    |
          | (httpx, 15s timeout)       |    |
          +----------------------------+    |
                                            |
                                            |
                              +-------------+--------------+
                              |  IN-MEMORY STORES          |
                              |  (Singleton instances)     |
                              |                            |
                              |  +----------------------+  |
                              |  | ConnectionStore      |  |
                              |  | - dict[str, Conn]    |  |
                              |  | - thread-safe (Lock) |  |
                              |  | - Pre-loaded demo:   |  |
                              |  |   "conn-demo-001"    |  |
                              |  +----------------------+  |
                              |                            |
                              |  +----------------------+  |
                              |  | SignalLogStore       |  |
                              |  | - deque (max 500)    |  |
                              |  | - thread-safe (Lock) |  |
                              |  | - LIFO retrieval     |  |
                              |  +----------------------+  |
                              +----------------------------+
                                            |
                                            | (Phase 6 - future)
                                            v
                              +----------------------------+
                              |  EXECUTION ENGINE          |
                              |  (Pluggable Protocol)      |
                              |                            |
                              |  Current:                  |
                              |  DefaultExecutionEngine    |
                              |  -> returns NoopCommand    |
                              |                            |
                              |  Future:                   |
                              |  - Partial TP routing      |
                              |  - Trailing stop wiring    |
                              |  - Broker command dispatch |
                              +-------------+--------------+
                                            |
                                            | BrokerCommand[]
                                            v
 +------------------------------------------+----------------------------+
 |  GATEWAY                                                              |
 |  Port: 5243                                                           |
 |                                                                       |
 |  FastAPI Application                                                  |
 |  Title: "ReyConnector Gateway"                                        |
 |                                                                       |
 |  Endpoints:                                                           |
 |  GET /health                                                          |
 |  GET /info                                                            |
 |                                                                       |
 |  Future Role:                                                         |
 |  - WebSocket / gRPC session management                                |
 |  - MT5 EA bidirectional communication                                 |
 |  - Connection heartbeats                                              |
 +-----------------------------------------------------------------------+
          ^
          | (Future: TLS session)
          |
 +--------+--------+
 |  MetaTrader 5   |
 |  ReyConnector   |
 |  Expert Advisor |
 |                  |
 |  Connection ID:  |
 |  "conn-demo-001" |
 +------------------+
```

---

## Service Decomposition

```
 +==================================================================+
 |                   reyconnector (Python package)                   |
 +==================================================================+
 |                                                                   |
 |  src/reyconnector/                                                |
 |  |                                                                |
 |  +-- __init__.py              __version__ = "0.1.0"              |
 |  +-- config.py                WebhookSettings (pydantic-settings) |
 |  |                                                                |
 |  +-- contracts/               Pydantic v2 data models             |
 |  |   +-- base.py              CamelModel (snake -> camelCase)     |
 |  |   +-- incoming_alert.py    IncomingAlertEnvelope               |
 |  |   +-- connection_summary.py ConnectionSummary                  |
 |  |   +-- broker_command.py    NoopCommand                         |
 |  |                                                                |
 |  +-- application/             Business logic & state              |
 |  |   +-- stores.py            InMemoryConnectionStore             |
 |  |                            InMemorySignalLogStore              |
 |  |                                                                |
 |  +-- execution/               Pluggable execution layer           |
 |  |   +-- engine.py            ExecutionEngineProtocol             |
 |  |                            DefaultExecutionEngine              |
 |  |                                                                |
 |  +-- apps/                    FastAPI application entry points     |
 |      +-- control_api.py       Port 5241 - Signal mgmt & queries   |
 |      +-- webhook_ingest.py    Port 5242 - TradingView receiver    |
 |      +-- gateway.py           Port 5243 - Health & future WS/gRPC |
 |                                                                   |
 +==================================================================+
 |                                                                   |
 |  clients/                     Platform client adapters            |
 |  +-- mql5-ea/                                                     |
 |      +-- ReyConnector.mq5     MT5 Expert Advisor (stub)           |
 |                                                                   |
 |  infra/                       Deployment infrastructure           |
 |  +-- docker/                                                      |
 |      +-- Dockerfile.control-api  Python 3.12-slim, port 8080     |
 |                                                                   |
 |  scripts/                     Developer tooling                   |
 |  +-- start-local.sh           Prints 3 uvicorn commands           |
 |                                                                   |
 +==================================================================+
```

---

## Pydantic Model Hierarchy

```
  BaseModel (pydantic)
      |
      v
  CamelModel
  (alias_generator=to_camel, populate_by_name=True)
      |
      +----> IncomingAlertEnvelope
      |        - id: str
      |        - connection_id: str | None     (JSON: connectionId)
      |        - raw_body: str                 (JSON: rawBody)
      |        - idempotency_key: str | None   (JSON: idempotencyKey)
      |        - received_at_utc: datetime     (JSON: receivedAtUtc)
      |
      +----> ConnectionSummary
      |        - id: str
      |        - display_name: str             (JSON: displayName)
      |        - is_enabled: bool              (JSON: isEnabled)
      |        - created_at_utc: datetime      (JSON: createdAtUtc)
      |        - last_seen_at_utc: datetime|None (JSON: lastSeenAtUtc)
      |
      +----> NoopCommand
               - kind: Literal["noop"]  = "noop"
               - reason: str

  BaseSettings (pydantic-settings)
      |
      v
  WebhookSettings
  (env_prefix="REYCONNECTOR_", env_file=".env", extra="ignore")
      - control_api_base_url: str = "http://localhost:5241"
```

---

## Execution Engine Protocol (Plugin Architecture)

```
  +------------------------------------------+
  |  ExecutionEngineProtocol                  |
  |  (@runtime_checkable Protocol)           |
  |                                           |
  |  async def process(                      |
  |    *,                                     |
  |    connection_id: str,                   |
  |    alert: IncomingAlertEnvelope,         |
  |    metadata: dict[str, str] | None,      |
  |  ) -> list[NoopCommand]                  |
  +---------------------+--------------------+
                        |
            +-----------+-----------+
            |                       |
            v                       v
  +---------+----------+  +---------+-----------+
  | DefaultExecution   |  | (Future)            |
  | Engine             |  | LiveExecutionEngine |
  |                    |  |                     |
  | Returns:           |  | Will:               |
  | [NoopCommand(      |  | - Parse raw_body    |
  |   reason="Phase 6: |  | - Map to broker cmd |
  |   wire partial TP  |  | - Partial TP logic  |
  |   / trailing here")]| | - Trailing stop     |
  +--------------------+  | - Send to MT5       |
                          +---------------------+
```

---

## Thread Safety Model

```
  +-----------------------------+
  |  InMemoryConnectionStore    |
  |                             |
  |  _lock = threading.Lock()  |
  |  _connections = dict(...)   |
  |                             |
  |  list_connections():        |
  |    with self._lock:         |
  |      return sorted(...)     |
  |                             |
  |  get(cid):                  |
  |    with self._lock:         |
  |      return _connections    |
  |        .get(cid)            |
  +-----------------------------+

  +-----------------------------+
  |  InMemorySignalLogStore     |
  |                             |
  |  _lock = threading.Lock()  |
  |  _items = deque()           |
  |  max_items = 500            |
  |                             |
  |  append(envelope):          |
  |    with self._lock:         |
  |      append + trim          |
  |                             |
  |  recent(take=100):          |
  |    with self._lock:         |
  |      return reversed slice  |
  +-----------------------------+
```
