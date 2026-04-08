from __future__ import annotations

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from reyconnector.application.stores import connection_store, signal_log_store
from reyconnector.contracts import ConnectionSummary, IncomingAlertEnvelope

app = FastAPI(title="ReyConnector Control API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "https://localhost:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "reyconnector.control_api"}


@app.get("/api/v1/connections")
def list_connections() -> list[ConnectionSummary]:
    return connection_store.list_connections()


@app.get("/api/v1/signals")
def list_signals(take: int = 100) -> list[IncomingAlertEnvelope]:
    return signal_log_store.recent(take)


@app.post("/api/internal/v1/signals", status_code=status.HTTP_202_ACCEPTED)
def ingest_signal(envelope: IncomingAlertEnvelope) -> dict[str, str]:
    signal_log_store.append(envelope)
    return {"id": envelope.id}
