from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from reyconnector.config import WebhookSettings
from reyconnector.contracts import IncomingAlertEnvelope

log = logging.getLogger(__name__)
settings = WebhookSettings()

app = FastAPI(title="ReyConnector Webhook Ingest", version="0.1.0")


@app.post("/v1/webhook")
async def ingest_webhook(
    request: Request,
    connection_id: Annotated[str | None, Query()] = None,
    connection_id_camel: Annotated[str | None, Query(alias="connectionId")] = None,
) -> JSONResponse:
    cid = connection_id or connection_id_camel
    raw = (await request.body()).decode("utf-8", errors="replace")
    idem = request.headers.get("x-idempotency-key") or request.headers.get("X-Idempotency-Key")

    envelope = IncomingAlertEnvelope.new(
        raw_body=raw,
        connection_id=cid,
        idempotency_key=idem,
    )

    base = settings.control_api_base_url.rstrip("/")
    url = f"{base}/api/internal/v1/signals"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                url,
                json=envelope.model_dump(mode="json", by_alias=True),
            )
            if r.status_code >= 400:
                log.warning("Control API returned %s: %s", r.status_code, r.text)
    except Exception as exc:
        log.exception("Failed to forward to Control API")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Signal accepted but forwarding failed; check Control API availability.",
                "error": str(exc),
            },
        )

    return JSONResponse(
        status_code=202,
        content={
            "signalId": envelope.id,
            "receivedAtUtc": envelope.received_at_utc.isoformat(),
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "reyconnector.webhook_ingest"}
