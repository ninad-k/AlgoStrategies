# ReyConnector - Feature & Parameter Reference

## Table of Contents

1. [API Endpoints](#1-api-endpoints)
2. [Data Models](#2-data-models)
3. [Configuration](#3-configuration)
4. [In-Memory Stores](#4-in-memory-stores)
5. [Execution Engine](#5-execution-engine)
6. [MT5 Expert Advisor](#6-mt5-expert-advisor)
7. [Docker Configuration](#7-docker-configuration)
8. [CORS Configuration](#8-cors-configuration)
9. [JSON Serialization](#9-json-serialization)

---

## 1. API Endpoints

### 1.1 Control API (Port 5241)

**FastAPI App Title:** `"ReyConnector Control API"`
**Version:** `"0.1.0"`
**Module:** `reyconnector.apps.control_api:app`

---

#### GET `/health`

Health check endpoint.

| Property | Value |
|----------|-------|
| Auth | None |
| Response Code | 200 |

**Response Body:**
```json
{
  "status": "ok",
  "service": "reyconnector.control_api"
}
```

---

#### GET `/api/v1/connections`

Returns all registered connections, sorted alphabetically by `display_name`.

| Property | Value |
|----------|-------|
| Auth | None |
| Response Code | 200 |
| Response Type | `list[ConnectionSummary]` |

**Query Parameters:** None

**Response Body:**
```json
[
  {
    "id": "conn-demo-001",
    "displayName": "Demo MT5",
    "isEnabled": true,
    "createdAtUtc": "2026-04-09T12:00:00+00:00",
    "lastSeenAtUtc": null
  }
]
```

**Default Data:** One demo connection is pre-loaded on startup:
| Field | Value |
|-------|-------|
| `id` | `"conn-demo-001"` |
| `display_name` | `"Demo MT5"` |
| `is_enabled` | `true` |
| `created_at_utc` | Server startup time (UTC) |
| `last_seen_at_utc` | `null` |

---

#### GET `/api/v1/signals`

Returns recent signals from the in-memory log, in reverse chronological order (newest first).

| Property | Value |
|----------|-------|
| Auth | None |
| Response Code | 200 |
| Response Type | `list[IncomingAlertEnvelope]` |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `take` | int | 100 | Number of most recent signals to return |

**Response Body:**
```json
[
  {
    "id": "a1b2c3d4e5f67890abcdef1234567890",
    "connectionId": "conn-demo-001",
    "rawBody": "ema200squeeze,buy,EURUSD",
    "idempotencyKey": null,
    "receivedAtUtc": "2026-04-09T12:00:00.123456+00:00"
  }
]
```

---

#### POST `/api/internal/v1/signals`

Internal endpoint for ingesting a signal envelope. Called by the Webhook Ingest service.

| Property | Value |
|----------|-------|
| Auth | None (internal network only) |
| Response Code | **202 Accepted** |
| Request Type | `IncomingAlertEnvelope` (JSON body) |
| Response Type | `dict` |

**Request Body (JSON, accepts both camelCase and snake_case):**
```json
{
  "id": "a1b2c3d4e5f67890abcdef1234567890",
  "connectionId": "conn-demo-001",
  "rawBody": "ema200squeeze,buy,EURUSD",
  "idempotencyKey": "tv-alert-abc123",
  "receivedAtUtc": "2026-04-09T12:00:00.123456+00:00"
}
```

**Response Body:**
```json
{
  "id": "a1b2c3d4e5f67890abcdef1234567890"
}
```

---

### 1.2 Webhook Ingest (Port 5242)

**FastAPI App Title:** `"ReyConnector Webhook Ingest"`
**Version:** `"0.1.0"`
**Module:** `reyconnector.apps.webhook_ingest:app`

---

#### POST `/v1/webhook`

Primary webhook endpoint for receiving TradingView alerts. Creates an `IncomingAlertEnvelope` and forwards it to the Control API.

| Property | Value |
|----------|-------|
| Auth | None |
| Response Code | 202 (success) or 503 (forwarding failed) |
| Content-Type | Any (body read as raw bytes) |

**Query Parameters:**

| Parameter | Alias | Type | Default | Description |
|-----------|-------|------|---------|-------------|
| `connection_id` | - | `str \| None` | `None` | Connection identifier (snake_case) |
| `connectionId` | camelCase alias | `str \| None` | `None` | Connection identifier (camelCase) |

> Both `connection_id` and `connectionId` are accepted. If both provided, `connection_id` takes precedence. Either can be `None`.

**Request Headers (Optional):**

| Header | Case-Sensitive | Description |
|--------|---------------|-------------|
| `X-Idempotency-Key` | No (`x-idempotency-key` also works) | Unique key for deduplication |

**Request Body:** Raw text/bytes (any content type accepted).

Examples:
```
ema200squeeze,buy,EURUSD
```
```json
{"strategy": "ema200", "action": "buy", "symbol": "EURUSD"}
```

**Success Response (202 Accepted):**
```json
{
  "signalId": "a1b2c3d4e5f67890abcdef1234567890",
  "receivedAtUtc": "2026-04-09T12:00:00.123456+00:00"
}
```

**Error Response (503 Service Unavailable):**

Returned when the Control API is unreachable (network error, timeout, connection refused).

```json
{
  "detail": "Signal accepted but forwarding failed; check Control API availability.",
  "error": "Connection refused: localhost:5241"
}
```

**Behavior Notes:**
- If Control API returns 4xx/5xx: logs a warning but still returns **202** to the caller
- If Control API is unreachable (network exception): returns **503** to the caller
- The httpx client uses a **15-second timeout** for the forwarding POST
- Serialization uses `model_dump(mode="json", by_alias=True)` for camelCase JSON

---

#### GET `/health`

Health check endpoint.

| Property | Value |
|----------|-------|
| Response Code | 200 |

**Response Body:**
```json
{
  "status": "ok",
  "service": "reyconnector.webhook_ingest"
}
```

---

### 1.3 Gateway (Port 5243)

**FastAPI App Title:** `"ReyConnector Gateway"`
**Version:** `"0.1.0"`
**Module:** `reyconnector.apps.gateway:app`

---

#### GET `/health`

Health check endpoint.

| Property | Value |
|----------|-------|
| Response Code | 200 |

**Response Body:**
```json
{
  "status": "ok",
  "service": "reyconnector.gateway"
}
```

---

#### GET `/info`

Service information and role description.

| Property | Value |
|----------|-------|
| Response Code | 200 |

**Response Body:**
```json
{
  "product": "ReyConnector",
  "role": "Session gateway (WebSocket / gRPC in a later iteration)",
  "stack": "python"
}
```

---

## 2. Data Models

All models inherit from `CamelModel`, which provides automatic snake_case -> camelCase JSON serialization.

### 2.1 IncomingAlertEnvelope

**File:** `src/reyconnector/contracts/incoming_alert.py`
**Parent:** `CamelModel`
**Purpose:** Wraps a raw TradingView webhook alert with metadata for tracking.

| Field | Python Type | JSON Key (camelCase) | Default | Description |
|-------|------------|---------------------|---------|-------------|
| `id` | `str` | `id` | (required) | Unique identifier, UUID4 hex (32 chars) |
| `connection_id` | `str \| None` | `connectionId` | `None` | Connection this alert belongs to |
| `raw_body` | `str` | `rawBody` | (required) | Raw webhook body as UTF-8 string |
| `idempotency_key` | `str \| None` | `idempotencyKey` | `None` | Optional deduplication key from header |
| `received_at_utc` | `datetime` | `receivedAtUtc` | (required) | UTC timestamp when alert was received |

**Factory Method:** `IncomingAlertEnvelope.new(*, raw_body, connection_id, idempotency_key)`
- Auto-generates `id` = `uuid.uuid4().hex`
- Auto-sets `received_at_utc` = `datetime.now(UTC)`

---

### 2.2 ConnectionSummary

**File:** `src/reyconnector/contracts/connection_summary.py`
**Parent:** `CamelModel`
**Purpose:** Represents a registered connection (e.g., an MT5 terminal).

| Field | Python Type | JSON Key (camelCase) | Default | Description |
|-------|------------|---------------------|---------|-------------|
| `id` | `str` | `id` | (required) | Unique connection identifier |
| `display_name` | `str` | `displayName` | (required) | Human-readable name |
| `is_enabled` | `bool` | `isEnabled` | (required) | Whether connection is active |
| `created_at_utc` | `datetime` | `createdAtUtc` | (required) | Creation timestamp (UTC) |
| `last_seen_at_utc` | `datetime \| None` | `lastSeenAtUtc` | `None` | Last heartbeat timestamp |

---

### 2.3 NoopCommand

**File:** `src/reyconnector/contracts/broker_command.py`
**Parent:** `CamelModel`
**Purpose:** Placeholder broker command returned by the execution engine (Phase 6 stub).

| Field | Python Type | JSON Key | Default | Description |
|-------|------------|---------|---------|-------------|
| `kind` | `Literal["noop"]` | `kind` | `"noop"` | Command type discriminator |
| `reason` | `str` | `reason` | (required) | Human-readable reason for noop |

---

### 2.4 CamelModel (Base)

**File:** `src/reyconnector/contracts/base.py`
**Parent:** `pydantic.BaseModel`
**Purpose:** Base model providing automatic snake_case <-> camelCase JSON mapping.

**Configuration:**
| Setting | Value | Effect |
|---------|-------|--------|
| `alias_generator` | `to_camel` | Python `snake_case` -> JSON `camelCase` |
| `populate_by_name` | `True` | Accepts both `camelCase` and `snake_case` on input |

---

### 2.5 WebhookSettings

**File:** `src/reyconnector/config.py`
**Parent:** `pydantic_settings.BaseSettings`
**Purpose:** Environment-based configuration for the Webhook Ingest service.

**Settings Config:**
| Setting | Value |
|---------|-------|
| `env_prefix` | `"REYCONNECTOR_"` |
| `env_file` | `".env"` |
| `extra` | `"ignore"` |

| Field | Python Type | Env Variable | Default | Description |
|-------|------------|-------------|---------|-------------|
| `control_api_base_url` | `str` | `REYCONNECTOR_CONTROL_API_BASE_URL` | `"http://localhost:5241"` | Base URL of the Control API service |

---

## 3. Configuration

### 3.1 Environment Variables

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `REYCONNECTOR_CONTROL_API_BASE_URL` | Webhook Ingest | `http://localhost:5241` | URL where Control API is running |

### 3.2 .env File

Place in the `tools/reyconnector-python/` directory. The Webhook Ingest service reads it automatically via `pydantic-settings`.

```env
REYCONNECTOR_CONTROL_API_BASE_URL=http://localhost:5241
```

### 3.3 Hardcoded Defaults

| Setting | Value | Location | Description |
|---------|-------|----------|-------------|
| Demo connection ID | `"conn-demo-001"` | `stores.py` | Pre-loaded connection |
| Demo connection name | `"Demo MT5"` | `stores.py` | Pre-loaded display name |
| Signal log max items | `500` | `stores.py` | Maximum signals in memory |
| Signal log default take | `100` | `control_api.py` | Default query page size |
| httpx timeout | `15.0` seconds | `webhook_ingest.py` | Forwarding POST timeout |
| CORS origins | `["http://localhost:4200", "https://localhost:4200"]` | `control_api.py` | Allowed browser origins |

---

## 4. In-Memory Stores

### 4.1 InMemoryConnectionStore

**File:** `src/reyconnector/application/stores.py`
**Instance:** `connection_store` (module-level singleton)

| Feature | Detail |
|---------|--------|
| Storage | `dict[str, ConnectionSummary]` |
| Thread safety | `threading.Lock` on all operations |
| Initial data | One demo connection: `conn-demo-001` / `Demo MT5` |
| Persistence | None (resets on restart) |

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `list_connections` | `() -> list[ConnectionSummary]` | Returns all connections sorted by `display_name` |
| `get` | `(cid: str) -> ConnectionSummary \| None` | Returns a connection by ID, or `None` |

---

### 4.2 InMemorySignalLogStore

**File:** `src/reyconnector/application/stores.py`
**Instance:** `signal_log_store` (module-level singleton)

| Feature | Detail |
|---------|--------|
| Storage | `collections.deque` |
| Max items | 500 (configurable in constructor) |
| Eviction | Oldest signal removed when max exceeded |
| Thread safety | `threading.Lock` on all operations |
| Persistence | None (resets on restart) |

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `append` | `(envelope: IncomingAlertEnvelope) -> None` | Adds signal, evicts oldest if > 500 |
| `recent` | `(take: int = 100) -> list[IncomingAlertEnvelope]` | Returns last N signals, newest first |

---

## 5. Execution Engine

### 5.1 ExecutionEngineProtocol

**File:** `src/reyconnector/execution/engine.py`
**Type:** `@runtime_checkable Protocol`

This is the **plugin interface** for custom execution logic. Any class implementing this protocol can replace the default engine.

**Method Signature:**
```python
async def process(
    self,
    *,
    connection_id: str,
    alert: IncomingAlertEnvelope,
    metadata: dict[str, str] | None = None,
) -> list[NoopCommand]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `connection_id` | `str` | Which connection this alert targets |
| `alert` | `IncomingAlertEnvelope` | The full signal envelope with raw body |
| `metadata` | `dict[str, str] \| None` | Optional key-value metadata (e.g., source info) |

**Returns:** `list[NoopCommand]` (will be `list[BrokerCommand]` in future phases)

### 5.2 DefaultExecutionEngine

**File:** `src/reyconnector/execution/engine.py`
**Implements:** `ExecutionEngineProtocol`

Current behavior: Returns a single `NoopCommand` with reason `"Phase 6: wire partial TP / trailing here"`.

This is a **placeholder**. In Phase 6, this will be replaced with logic to:
1. Parse `alert.raw_body` into structured trade instructions
2. Look up connection configuration (account, risk params)
3. Generate broker-specific commands (market orders, limits, etc.)
4. Route commands to the Gateway for MT5 dispatch

---

## 6. MT5 Expert Advisor

### 6.1 File

**Path:** `clients/mql5-ea/ReyConnector.mq5`

### 6.2 Properties

| Property | Value |
|----------|-------|
| Copyright | `"Rey Capital"` |
| Link | `"https://reycapital.example"` |
| Version | `"1.000"` |
| Description | "ReyConnector bridge - connection handshake and order execution (expand per roadmap)." |

### 6.3 Input Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `InpConnectionId` | `string` | `"conn-demo-001"` | Connection ID matching a registered connection in ReyConnector |

### 6.4 Event Handlers

| Handler | Current Behavior | Future Behavior |
|---------|-----------------|-----------------|
| `OnInit()` | Prints connection ID, returns `INIT_SUCCEEDED` | Establish TLS session to Gateway |
| `OnDeinit(reason)` | Prints stop reason | Close TLS session, deregister |
| `OnTick()` | Empty stub | Check for pending commands, execute orders |

### 6.5 Installation

1. Copy `ReyConnector.mq5` to `<MT5_DATA>/MQL5/Experts/`
2. Compile in MetaEditor (F7)
3. Drag onto any chart in MT5
4. Enable AutoTrading
5. Set `InpConnectionId` in EA properties

---

## 7. Docker Configuration

### 7.1 Dockerfile.control-api

**File:** `infra/docker/Dockerfile.control-api`

| Property | Value |
|----------|-------|
| Base image | `python:3.12-slim` |
| Working directory | `/app` |
| Exposed port | `8080` |
| Entry command | `uvicorn reyconnector.apps.control_api:app --host 0.0.0.0 --port 8080` |

**Environment variables set in image:**

| Variable | Value | Purpose |
|----------|-------|---------|
| `PYTHONDONTWRITEBYTECODE` | `1` | Prevent `.pyc` file creation |
| `PYTHONUNBUFFERED` | `1` | Force stdout/stderr to be unbuffered |

**Build command:**
```bash
docker build -f infra/docker/Dockerfile.control-api -t reyconnector-py-control-api .
```

**Run command:**
```bash
docker run -p 5241:8080 reyconnector-py-control-api
```

---

## 8. CORS Configuration

**Service:** Control API only
**File:** `src/reyconnector/apps/control_api.py`

| Setting | Value |
|---------|-------|
| `allow_origins` | `["http://localhost:4200", "https://localhost:4200"]` |
| `allow_credentials` | `True` |
| `allow_methods` | `["*"]` (all HTTP methods) |
| `allow_headers` | `["*"]` (all headers) |

> CORS is configured for the Angular Portal UI which runs on `localhost:4200`. Update `allow_origins` if your frontend runs on a different port.

---

## 9. JSON Serialization

### 9.1 CamelCase Convention

All JSON payloads use **camelCase** keys for compatibility with the Angular portal and .NET parity. The Python code uses **snake_case** internally.

**Mapping examples:**

| Python Field | JSON Key |
|-------------|---------|
| `connection_id` | `connectionId` |
| `raw_body` | `rawBody` |
| `idempotency_key` | `idempotencyKey` |
| `received_at_utc` | `receivedAtUtc` |
| `display_name` | `displayName` |
| `is_enabled` | `isEnabled` |
| `created_at_utc` | `createdAtUtc` |
| `last_seen_at_utc` | `lastSeenAtUtc` |

### 9.2 Bidirectional Support

- **Output (serialization):** Always camelCase (`model_dump(mode="json", by_alias=True)`)
- **Input (deserialization):** Accepts both camelCase and snake_case (`populate_by_name=True`)

### 9.3 Webhook Query Parameter

The webhook endpoint accepts both formats for the connection ID query parameter:
- `?connection_id=conn-demo-001` (snake_case)
- `?connectionId=conn-demo-001` (camelCase)

Both are handled via separate `Query()` parameters that are merged internally.
