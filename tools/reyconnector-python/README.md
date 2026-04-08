# ReyConnector (Python)

Python implementation of **ReyConnector** (Rey Capital): the same roles as [`tools/reyconnector`](../reyconnector) — **Control API**, **Webhook ingest**, **Gateway**, and pluggable **execution engine** — using **FastAPI**, **Pydantic v2**, and **httpx**.

## Layout

| Service | Port | Module |
|---------|------|--------|
| Control API | 5241 | `reyconnector.apps.control_api` |
| Webhook ingest | 5242 | `reyconnector.apps.webhook_ingest` |
| Gateway | 5243 | `reyconnector.apps.gateway` |

## Setup

```bash
cd tools/reyconnector-python
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run locally (three terminals)

```bash
# Terminal 1
uvicorn reyconnector.apps.control_api:app --host 0.0.0.0 --port 5241 --reload

# Terminal 2
uvicorn reyconnector.apps.webhook_ingest:app --host 0.0.0.0 --port 5242 --reload

# Terminal 3
uvicorn reyconnector.apps.gateway:app --host 0.0.0.0 --port 5243 --reload
```

Or: `./scripts/start-local.sh`

**Portal UI:** use the Angular app in [`../reyconnector/portal`](../reyconnector/portal) — it proxies `/api` to port **5241** (same API shape as the .NET Control API).

## Smoke test

```bash
curl -X POST "http://localhost:5242/v1/webhook?connection_id=conn-demo-001" \
  -H "Content-Type: text/plain" \
  -d "demo,buy,EURUSD"
```

Then open the portal → **Signal log**, or:

```bash
curl -s http://localhost:5241/api/v1/signals | python -m json.tool
```

## Configuration

Webhook forwards to Control API. Override base URL (see `reyconnector.config.WebhookSettings`):

```bash
export REYCONNECTOR_CONTROL_API_BASE_URL=http://localhost:5241
```

## Package structure

- `src/reyconnector/contracts/` — Pydantic models shared across services
- `src/reyconnector/application/` — in-memory stores (replace with PostgreSQL in production)
- `src/reyconnector/execution/` — `ExecutionEngine` protocol + default stub (Phase 6)
