# reyconnector-python — layout

| Path | Purpose |
|------|---------|
| `src/reyconnector/contracts/` | Pydantic models (camelCase JSON for portal parity) |
| `src/reyconnector/application/` | In-memory stores (dev); replace with PostgreSQL later |
| `src/reyconnector/execution/` | `ExecutionEngineProtocol` + `DefaultExecutionEngine` stub |
| `src/reyconnector/apps/control_api.py` | FastAPI — connections + signal log — **:5241** |
| `src/reyconnector/apps/webhook_ingest.py` | FastAPI — `POST /v1/webhook` — **:5242** |
| `src/reyconnector/apps/gateway.py` | FastAPI — health/info — **:5243** |
| `clients/mql5-ea/` | MT5 EA skeleton (language-agnostic) |
| `infra/docker/` | Container image for Control API |
| `scripts/start-local.sh` | Print uvicorn commands |

**Portal:** reuse [`../reyconnector/portal`](../reyconnector/portal) — same REST paths and CORS.
