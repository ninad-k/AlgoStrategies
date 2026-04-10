# ReyConnector - Setup & Run Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | >= 3.11 | Runtime for all services |
| pip | Latest | Package installation |
| Docker | >= 24 | Production deployment (optional) |
| MetaTrader 5 | Latest | MT5 EA client (optional) |
| MetaEditor | Latest | Compiling MQL5 EA (optional) |
| TradingView | Pro+ | Webhook alerts (Pro+ required for webhooks) |

---

## 1. Local Development Setup

### 1.1 Clone & Navigate

```bash
cd tools/reyconnector-python
```

### 1.2 Create Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 1.3 Install Dependencies

```bash
# Production dependencies
pip install -e .

# Production + development tools (ruff, mypy)
pip install -e ".[dev]"
```

**Installed packages:**
| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | >= 0.115.0 | Web framework for all 3 services |
| `uvicorn[standard]` | >= 0.32.0 | ASGI server |
| `httpx` | >= 0.28.0 | Async HTTP client (Webhook -> Control API) |
| `pydantic` | >= 2.10.0 | Data validation & serialization |
| `pydantic-settings` | >= 2.6.0 | Environment variable config |
| `ruff` | >= 0.8.0 | Linter & formatter (dev only) |
| `mypy` | >= 1.13.0 | Static type checker (dev only) |

### 1.4 Configure Environment (Optional)

Create a `.env` file in the project root:

```env
# Only needed if changing defaults
REYCONNECTOR_CONTROL_API_BASE_URL=http://localhost:5241
```

This is read by the Webhook Ingest service to know where to forward signals. The default (`http://localhost:5241`) works out of the box for local development.

---

## 2. Running the Services

ReyConnector consists of **3 independent FastAPI services**. Each runs in its own process.

### 2.1 Quick Start (All 3 Services)

The `start-local.sh` script prints the commands for each terminal:

```bash
./scripts/start-local.sh
```

Then open **3 separate terminals** and run:

**Terminal 1 - Control API (port 5241):**
```bash
uvicorn reyconnector.apps.control_api:app --host 0.0.0.0 --port 5241 --reload
```

**Terminal 2 - Webhook Ingest (port 5242):**
```bash
uvicorn reyconnector.apps.webhook_ingest:app --host 0.0.0.0 --port 5242 --reload
```

**Terminal 3 - Gateway (port 5243):**
```bash
uvicorn reyconnector.apps.gateway:app --host 0.0.0.0 --port 5243 --reload
```

> **Note:** The `--reload` flag enables hot-reload on file changes. Remove it for production.

### 2.2 Verify Services Are Running

```bash
# Health checks for all 3 services
curl http://localhost:5241/health
# {"status":"ok","service":"reyconnector.control_api"}

curl http://localhost:5242/health
# {"status":"ok","service":"reyconnector.webhook_ingest"}

curl http://localhost:5243/health
# {"status":"ok","service":"reyconnector.gateway"}
```

### 2.3 Service Startup Order

| Order | Service | Port | Reason |
|-------|---------|------|--------|
| 1 | Control API | 5241 | Must be up before Webhook Ingest can forward signals |
| 2 | Webhook Ingest | 5242 | Forwards to Control API; returns 503 if Control API is down |
| 3 | Gateway | 5243 | Independent; no dependencies on other services |

> If Control API is down when Webhook Ingest receives an alert, the webhook still returns a response (503 with error detail). The signal is **not lost silently** - the caller is informed.

---

## 3. Testing the Webhook Pipeline

### 3.1 Send a Test Alert

```bash
curl -X POST "http://localhost:5242/v1/webhook?connection_id=conn-demo-001" \
  -H "Content-Type: text/plain" \
  -d "ema200squeeze,buy,EURUSD"
```

**Expected response (202 Accepted):**
```json
{
  "signalId": "a1b2c3d4e5f67890abcdef1234567890",
  "receivedAtUtc": "2026-04-09T12:00:00.123456+00:00"
}
```

### 3.2 Send with Idempotency Key

```bash
curl -X POST "http://localhost:5242/v1/webhook?connection_id=conn-demo-001" \
  -H "Content-Type: text/plain" \
  -H "X-Idempotency-Key: tv-alert-unique-123" \
  -d "goldFib,sell,XAUUSD"
```

### 3.3 Send with camelCase Query Parameter

```bash
curl -X POST "http://localhost:5242/v1/webhook?connectionId=conn-demo-001" \
  -H "Content-Type: text/plain" \
  -d "smartmoney,buy,GBPUSD"
```

### 3.4 Retrieve Signal Log

```bash
# Last 100 signals (default)
curl http://localhost:5241/api/v1/signals

# Last 10 signals
curl "http://localhost:5241/api/v1/signals?take=10"
```

**Expected response:**
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

### 3.5 List Connections

```bash
curl http://localhost:5241/api/v1/connections
```

**Expected response:**
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

### 3.6 Gateway Info

```bash
curl http://localhost:5243/info
```

**Expected response:**
```json
{
  "product": "ReyConnector",
  "role": "Session gateway (WebSocket / gRPC in a later iteration)",
  "stack": "python"
}
```

---

## 4. Docker Deployment (Production)

### 4.1 Build the Control API Image

```bash
cd tools/reyconnector-python

docker build -f infra/docker/Dockerfile.control-api -t reyconnector-py-control-api .
```

**Dockerfile details:**
- Base image: `python:3.12-slim`
- Working directory: `/app`
- Environment: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`
- Exposed port: `8080`
- Command: `uvicorn reyconnector.apps.control_api:app --host 0.0.0.0 --port 8080`

### 4.2 Run the Container

```bash
docker run -d \
  --name reyconnector-control-api \
  -p 5241:8080 \
  reyconnector-py-control-api
```

### 4.3 Run with Custom Environment

```bash
docker run -d \
  --name reyconnector-control-api \
  -p 5241:8080 \
  -e REYCONNECTOR_CONTROL_API_BASE_URL=http://control-api:8080 \
  reyconnector-py-control-api
```

### 4.4 Render Deployment

The repository root `render.yaml` includes a service definition. Configure these environment variables in the Render dashboard:

| Variable | Value |
|----------|-------|
| `REYCONNECTOR_CONTROL_API_BASE_URL` | Your Render service URL |

---

## 5. TradingView Webhook Configuration

### 5.1 Prerequisites

- TradingView **Pro** plan or higher (webhooks require paid plan)
- ReyConnector Webhook Ingest accessible from the internet (via Render, ngrok, or public server)

### 5.2 Create Alert with Webhook

1. Open your Pine Script strategy chart in TradingView
2. Click **"Alerts"** (clock icon) -> **"Create Alert"**
3. Set **Condition** to your strategy
4. Under **Notifications**, check **"Webhook URL"**
5. Enter your webhook URL:
   ```
   https://your-domain.com/v1/webhook?connection_id=conn-demo-001
   ```
6. Set **Alert message** (this becomes `rawBody`):
   ```
   {{strategy.order.action}},{{ticker}},{{close}}
   ```
   Or a custom format:
   ```
   ema200squeeze,{{strategy.order.action}},{{ticker}}
   ```
7. Click **"Create"**

### 5.3 Alert Message Format

The `rawBody` is passed through as-is. You define your own format. Common patterns:

| Format | Example | Description |
|--------|---------|-------------|
| CSV | `strategy,action,symbol` | Simple comma-separated |
| JSON | `{"s":"ema200","a":"buy","sym":"EURUSD"}` | Structured JSON |
| TradingView vars | `{{strategy.order.action}},{{ticker}}` | TradingView placeholders |

---

## 6. MT5 Expert Advisor Setup

### 6.1 Install the EA

1. Open MetaTrader 5 -> **File** -> **Open Data Folder**
2. Navigate to `MQL5/Experts/`
3. Copy `clients/mql5-ea/ReyConnector.mq5` into the `Experts` folder
4. Open **MetaEditor** (F4 in MT5)
5. Open `ReyConnector.mq5` -> **Compile** (F7)
6. Back in MT5: **Navigator** panel -> **Expert Advisors** -> Drag `ReyConnector` onto any chart

### 6.2 Configure the EA

In the EA properties dialog:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `InpConnectionId` | `"conn-demo-001"` | Connection ID matching your ReyConnector setup |

### 6.3 Current Status

The MT5 EA is currently a **stub** (Phase 1). It:
- Prints initialization message with connection ID
- Does NOT connect to the Gateway yet
- Does NOT execute orders

Future phases will add:
- Outbound TLS connection to Gateway (:5243)
- Command receive loop
- Order execution via `CTrade` library

---

## 7. Development Tools

### 7.1 Linting

```bash
# Check code style
ruff check src/

# Auto-fix issues
ruff check src/ --fix
```

**Ruff configuration** (from `pyproject.toml`):
- Line length: 100
- Target: Python 3.11
- Rules: E (pycodestyle errors), F (pyflakes), I (isort), UP (pyupgrade)

### 7.2 Type Checking

```bash
mypy src/
```

### 7.3 Interactive API Docs

When services are running, FastAPI auto-generates interactive docs:

| Service | Swagger UI | ReDoc |
|---------|-----------|-------|
| Control API | http://localhost:5241/docs | http://localhost:5241/redoc |
| Webhook Ingest | http://localhost:5242/docs | http://localhost:5242/redoc |
| Gateway | http://localhost:5243/docs | http://localhost:5243/redoc |

---

## 8. Troubleshooting

### Webhook returns 503

**Cause:** Control API is not running or unreachable.
**Fix:** Start the Control API first (`uvicorn reyconnector.apps.control_api:app --port 5241`).

### "ModuleNotFoundError: No module named 'reyconnector'"

**Cause:** Package not installed in editable mode.
**Fix:** Run `pip install -e .` from the `reyconnector-python/` directory.

### CORS errors in browser

**Cause:** Portal running on a port not in the allowed origins list.
**Current allowed origins:** `http://localhost:4200`, `https://localhost:4200`
**Fix:** Update `allow_origins` in `src/reyconnector/apps/control_api.py`.

### Signals not appearing in GET /api/v1/signals

**Cause:** Webhook Ingest might be forwarding to wrong Control API URL.
**Fix:** Check `REYCONNECTOR_CONTROL_API_BASE_URL` in `.env` (default: `http://localhost:5241`).

### Signal log is empty after restart

**Cause:** Signal log is in-memory only (not persisted).
**Expected behavior:** All signals are lost on service restart. This is by design for the current phase.
