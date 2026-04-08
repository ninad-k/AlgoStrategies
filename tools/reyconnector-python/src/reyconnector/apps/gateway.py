from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="ReyConnector Gateway", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "reyconnector.gateway"}


@app.get("/info")
def info() -> dict[str, str]:
    return {
        "product": "ReyConnector",
        "role": "Session gateway (WebSocket / gRPC in a later iteration)",
        "stack": "python",
    }
