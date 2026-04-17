from __future__ import annotations

import logging

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from reyconnector.application.stores import connection_store, signal_log_store
from reyconnector.contracts import BrokerCommand, ConnectionSummary, IncomingAlertEnvelope
from reyconnector.execution.engine import DefaultExecutionEngine

log = logging.getLogger(__name__)

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

_engine = DefaultExecutionEngine()


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
async def ingest_signal(envelope: IncomingAlertEnvelope) -> dict:
    signal_log_store.append(envelope)

    connection = connection_store.get(envelope.connection_id) if envelope.connection_id else None

    commands = await _engine.process(
        connection_id=envelope.connection_id or "unknown",
        alert=envelope,
        connection=connection,
    )

    log.info(
        "Processed signal %s -> %d command(s): %s",
        envelope.id,
        len(commands),
        [c.kind for c in commands],
    )

    return {
        "id": envelope.id,
        "commands": [_serialize_command(c) for c in commands],
    }


def _serialize_command(cmd: BrokerCommand) -> dict:
    return cmd.model_dump(mode="json", by_alias=True)
