# ReyConnector - Data Flow Diagrams

## 1. Primary Flow: TradingView Webhook -> Signal Log

This is the main data flow through the system when a TradingView alert fires.

```
 TRADINGVIEW PLATFORM
 +------------------------------------------------------+
 |  Pine Script Strategy fires alert on bar close       |
 |  Alert message: "ema200squeeze,buy,EURUSD"           |
 |  Webhook URL configured by user                       |
 +----------------------------+-------------------------+
                              |
                              | HTTP POST
                              | URL: https://<host>/v1/webhook?connection_id=conn-demo-001
                              | Content-Type: text/plain (or application/json)
                              | Body: "ema200squeeze,buy,EURUSD"
                              | Headers (optional):
                              |   X-Idempotency-Key: "tv-alert-abc123"
                              |
                              v
 WEBHOOK INGEST SERVICE (Port 5242)
 +------------------------------------------------------+
 |                                                       |
 |  POST /v1/webhook handler                             |
 |                                                       |
 |  Step 1: Extract query parameters                     |
 |  +--------------------------------------------------+ |
 |  | connection_id = request.query["connection_id"]    | |
 |  |            OR  request.query["connectionId"]      | |
 |  | (supports both snake_case and camelCase)          | |
 |  +--------------------------------------------------+ |
 |                                                       |
 |  Step 2: Read raw body                                |
 |  +--------------------------------------------------+ |
 |  | raw_body = await request.body()                   | |
 |  | raw_text = raw_body.decode("utf-8")               | |
 |  +--------------------------------------------------+ |
 |                                                       |
 |  Step 3: Extract idempotency key from headers         |
 |  +--------------------------------------------------+ |
 |  | idem_key = headers.get("x-idempotency-key")      | |
 |  |        OR headers.get("X-Idempotency-Key")       | |
 |  +--------------------------------------------------+ |
 |                                                       |
 |  Step 4: Create IncomingAlertEnvelope                 |
 |  +--------------------------------------------------+ |
 |  | IncomingAlertEnvelope.new(                        | |
 |  |   raw_body = "ema200squeeze,buy,EURUSD",         | |
 |  |   connection_id = "conn-demo-001",               | |
 |  |   idempotency_key = "tv-alert-abc123"            | |
 |  | )                                                 | |
 |  |                                                   | |
 |  | Auto-generated:                                   | |
 |  |   id = uuid4().hex  (e.g. "a1b2c3d4e5f6...")    | |
 |  |   received_at_utc = datetime.now(UTC)            | |
 |  +--------------------------------------------------+ |
 |                                                       |
 |  Step 5: Forward to Control API                       |
 |  +--------------------------------------------------+ |
 |  | httpx.AsyncClient (timeout=15.0s)                 | |
 |  | POST {control_api_base_url}                       | |
 |  |      /api/internal/v1/signals                     | |
 |  |                                                   | |
 |  | Body (JSON, camelCase serialization):             | |
 |  | {                                                 | |
 |  |   "id": "a1b2c3d4e5f6...",                      | |
 |  |   "connectionId": "conn-demo-001",               | |
 |  |   "rawBody": "ema200squeeze,buy,EURUSD",        | |
 |  |   "idempotencyKey": "tv-alert-abc123",           | |
 |  |   "receivedAtUtc": "2026-04-09T12:00:00Z"       | |
 |  | }                                                 | |
 |  +--------------------------------------------------+ |
 |                                                       |
 |  Step 6: Return response                              |
 |  +--------------------------------------------------+ |
 |  | Success (202 Accepted):                           | |
 |  | {                                                 | |
 |  |   "signalId": "a1b2c3d4e5f6...",                | |
 |  |   "receivedAtUtc": "2026-04-09T12:00:00Z"       | |
 |  | }                                                 | |
 |  |                                                   | |
 |  | Control API unreachable (503):                    | |
 |  | {                                                 | |
 |  |   "detail": "Signal accepted but forwarding      | |
 |  |             failed; check Control API ...",       | |
 |  |   "error": "<exception message>"                 | |
 |  | }                                                 | |
 |  +--------------------------------------------------+ |
 +----------------------------+-------------------------+
                              |
                              | HTTP POST (internal)
                              | /api/internal/v1/signals
                              | JSON body (camelCase)
                              |
                              v
 CONTROL API SERVICE (Port 5241)
 +------------------------------------------------------+
 |                                                       |
 |  POST /api/internal/v1/signals handler                |
 |  (status_code = 202)                                  |
 |                                                       |
 |  Step 1: Deserialize envelope                         |
 |  +--------------------------------------------------+ |
 |  | FastAPI auto-parses JSON body into                | |
 |  | IncomingAlertEnvelope (Pydantic v2)               | |
 |  | Supports both camelCase and snake_case input      | |
 |  | (populate_by_name=True)                           | |
 |  +--------------------------------------------------+ |
 |                                                       |
 |  Step 2: Append to signal log                         |
 |  +--------------------------------------------------+ |
 |  | signal_log_store.append(envelope)                 | |
 |  |                                                   | |
 |  | Thread-safe (Lock):                               | |
 |  |   _items.append(envelope)                         | |
 |  |   if len > 500: remove oldest                     | |
 |  +--------------------------------------------------+ |
 |                                                       |
 |  Step 3: Return acknowledgment                        |
 |  +--------------------------------------------------+ |
 |  | 202 Accepted                                      | |
 |  | {"id": "a1b2c3d4e5f6..."}                        | |
 |  +--------------------------------------------------+ |
 |                                                       |
 +------------------------------------------------------+
```

---

## 2. Query Flow: Portal / Client Reads Signals & Connections

```
 PORTAL WEB UI (Angular, localhost:4200)
 +------------------------------------------------------+
 |  Dashboard polls for latest signals and connections   |
 +----------------------------+-------------------------+
                              |
          +-------------------+-------------------+
          |                                       |
          v                                       v
 +--------+----------+               +-----------+----------+
 | GET /api/v1/      |               | GET /api/v1/         |
 | connections       |               | signals?take=100     |
 +--------+----------+               +-----------+----------+
          |                                       |
          v                                       v
 CONTROL API (Port 5241)              CONTROL API (Port 5241)
 +--------------------+               +-----------------------+
 |                     |               |                       |
 | connection_store    |               | signal_log_store      |
 | .list_connections() |               | .recent(take=100)     |
 |                     |               |                       |
 | Lock acquired:      |               | Lock acquired:        |
 |   Return sorted     |               |   Return last N items |
 |   by display_name   |               |   (reverse chrono)    |
 |                     |               |                       |
 +--------+------------+               +-----------+-----------+
          |                                        |
          v                                        v
 +--------+------------+               +-----------+-----------+
 | 200 OK               |               | 200 OK                |
 | [                     |               | [                     |
 |   {                   |               |   {                   |
 |     "id":             |               |     "id": "a1b2...",  |
 |       "conn-demo-001",|               |     "connectionId":   |
 |     "displayName":    |               |       "conn-demo-001",|
 |       "Demo MT5",     |               |     "rawBody":        |
 |     "isEnabled": true,|               |       "ema200,buy,    |
 |     "createdAtUtc":   |               |        EURUSD",       |
 |       "2026-04-...",  |               |     "idempotencyKey": |
 |     "lastSeenAtUtc":  |               |       "tv-abc123",    |
 |       null            |               |     "receivedAtUtc":  |
 |   }                   |               |       "2026-04-..."   |
 | ]                     |               |   },                  |
 +------------------------+               |   ...                 |
                                          | ]                     |
                                          +------------------------+
```

---

## 3. Future Flow: Signal -> Execution -> MT5 (Phase 6)

```
 CONTROL API (Signal received)
 +------------------------------------------------------+
 |  signal_log_store has new IncomingAlertEnvelope       |
 +----------------------------+-------------------------+
                              |
                              v
 EXECUTION ENGINE (pluggable)
 +------------------------------------------------------+
 |                                                       |
 |  engine.process(                                      |
 |    connection_id = "conn-demo-001",                  |
 |    alert = IncomingAlertEnvelope(...),               |
 |    metadata = {"source": "tradingview"}              |
 |  )                                                    |
 |                                                       |
 |  CURRENT (DefaultExecutionEngine):                    |
 |  +--------------------------------------------------+ |
 |  | Returns: [NoopCommand(                            | |
 |  |   reason="Phase 6: wire partial TP /             | |
 |  |           trailing here"                          | |
 |  | )]                                                | |
 |  +--------------------------------------------------+ |
 |                                                       |
 |  FUTURE (LiveExecutionEngine):                        |
 |  +--------------------------------------------------+ |
 |  |                                                   | |
 |  |  Step 1: Parse raw_body                           | |
 |  |  "ema200,buy,EURUSD"                              | |
 |  |  -> strategy="ema200", action="buy",              | |
 |  |     symbol="EURUSD"                               | |
 |  |                                                   | |
 |  |  Step 2: Look up connection config                | |
 |  |  conn-demo-001 -> MT5 account, risk params        | |
 |  |                                                   | |
 |  |  Step 3: Generate broker commands                 | |
 |  |  [                                                | |
 |  |    MarketOrder(symbol="EURUSD", type=BUY,         | |
 |  |      lots=0.10, sl=..., tp1=..., tp2=...,        | |
 |  |      trailing=True)                               | |
 |  |  ]                                                | |
 |  |                                                   | |
 |  |  Step 4: Dispatch to MT5 via Gateway              | |
 |  +--------------------------------------------------+ |
 +----------------------------+-------------------------+
                              |
                              | BrokerCommand[]
                              v
 GATEWAY (Port 5243)
 +------------------------------------------------------+
 |  Future: WebSocket / gRPC session to MT5 EA           |
 |                                                       |
 |  Step 1: Find active session for connection_id        |
 |  Step 2: Serialize command to MT5-compatible format   |
 |  Step 3: Push command over session channel            |
 |  Step 4: Wait for execution confirmation              |
 +----------------------------+-------------------------+
                              |
                              | TLS / WebSocket
                              v
 MT5 EXPERT ADVISOR
 +------------------------------------------------------+
 |  ReyConnector.mq5                                     |
 |                                                       |
 |  Input: InpConnectionId = "conn-demo-001"             |
 |                                                       |
 |  OnInit():                                            |
 |    - Connect to Gateway via TLS                       |
 |    - Register connection_id                           |
 |    - Enter command receive loop                       |
 |                                                       |
 |  OnCommand(MarketOrder):                              |
 |    - Validate symbol, check spread                    |
 |    - CTrade::Buy/Sell(lots, symbol, sl, tp)           |
 |    - Return execution result                          |
 |                                                       |
 +------------------------------------------------------+
```

---

## 4. Envelope Lifecycle (Complete Data Journey)

```
 BIRTH                                      DEATH
   |                                           |
   v                                           v
 +----+     +--------+     +---------+     +--------+
 | TV |     |Webhook |     |Control  |     |Deque   |
 |alert| --> |Ingest  | --> |API      | --> |eviction|
 |fires|     |creates |     |appends  |     |at 500  |
 +----+     |envelope|     |to store |     |items   |
            +--------+     +---------+     +--------+

 Envelope Field Population Timeline:
 ===========================================================================

 TradingView fires alert:
   -> raw body exists as text: "ema200,buy,EURUSD"
   -> connection_id in webhook URL query string
   -> idempotency_key in X-Idempotency-Key header (optional)

 Webhook Ingest creates IncomingAlertEnvelope.new():
   -> id = uuid4().hex           (auto-generated, immutable)
   -> connection_id              (from query param)
   -> raw_body                   (from HTTP body)
   -> idempotency_key            (from header, nullable)
   -> received_at_utc            (auto-set to datetime.now(UTC))

 Webhook Ingest serializes (by_alias=True for camelCase):
   -> JSON: {id, connectionId, rawBody, idempotencyKey, receivedAtUtc}

 Control API deserializes (populate_by_name=True):
   -> Accepts both camelCase and snake_case
   -> Validated by Pydantic v2

 Signal Log Store appends:
   -> deque._items.append(envelope)
   -> If len > 500: oldest removed (popleft)

 Portal queries GET /api/v1/signals?take=100:
   -> Returns last 100 signals in reverse chronological order
   -> Serialized as camelCase JSON arrays
```

---

## 5. Error & Fallback Flow

```
 WEBHOOK INGEST receives POST /v1/webhook
         |
         v
 Create IncomingAlertEnvelope
         |
         v
 Forward to Control API
 POST /api/internal/v1/signals
         |
         +---- SUCCESS (2xx) ----+
         |                       |
         |                       v
         |               Return 202 Accepted
         |               {
         |                 "signalId": "...",
         |                 "receivedAtUtc": "..."
         |               }
         |
         +---- HTTP ERROR (4xx/5xx) ----+
         |                              |
         |                              v
         |                    Log warning:
         |                    "Control-API returned
         |                     <status>: <body>"
         |                              |
         |                              v
         |                    Return 202 Accepted
         |                    (signal was received,
         |                     forwarding issue logged)
         |
         +---- NETWORK EXCEPTION ----+
         |  (ConnectionError,         |
         |   TimeoutException, etc.)  |
         |                            v
         |                  Log exception:
         |                  "Could not forward to
         |                   Control-API"
         |                            |
         |                            v
         |                  Return 503
         |                  {
         |                    "detail": "Signal
         |                      accepted but forwarding
         |                      failed; check Control
         |                      API availability.",
         |                    "error": "<exception msg>"
         |                  }
         |
         v
 (In all cases, the webhook caller gets a response)
```

---

## 6. Inter-Service Communication Map

```
                       +-------------------+
                       |  Webhook Ingest   |
                       |  :5242            |
                       +---------+---------+
                                 |
                                 | POST /api/internal/v1/signals
                                 | (httpx.AsyncClient, timeout=15s)
                                 | JSON body, camelCase
                                 |
                                 v
                       +---------+---------+
                       |  Control API      |
                       |  :5241            |
                       +---------+---------+
                                 |
                                 | (Phase 6: invoke execution engine)
                                 |
                                 v
                       +---------+---------+
                       |  Gateway          |
                       |  :5243            |
                       +---------+---------+
                                 |
                                 | (Future: WebSocket/gRPC to MT5)
                                 v
                       +---------+---------+
                       |  MT5 EA           |
                       |  (ReyConnector)   |
                       +-------------------+

 Communication Protocol:
 +--------------------+---------------------+------------------+
 | From               | To                  | Method           |
 +--------------------+---------------------+------------------+
 | TradingView        | Webhook Ingest      | HTTP POST        |
 | Webhook Ingest     | Control API         | HTTP POST (httpx)|
 | Portal UI          | Control API         | HTTP GET (CORS)  |
 | Control API        | Execution Engine    | In-process call  |
 | Gateway            | MT5 EA              | TLS (future)     |
 +--------------------+---------------------+------------------+
```
