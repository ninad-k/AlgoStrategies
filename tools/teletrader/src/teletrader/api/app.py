"""TeleTrader local API — FastAPI server for signal ingestion and EA polling."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status

from teletrader.models.trading_signal import TradingSignal
from teletrader.parsing.signal_parser import parse_signal
from teletrader.store.memory_store import InMemorySignalStore

app = FastAPI(title="TeleTrader API", version="0.1.0")

signal_store = InMemorySignalStore()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "teletrader"}


@app.post("/api/v1/signal", status_code=status.HTTP_201_CREATED)
async def ingest_raw_signal(request: Request) -> dict:
    """Accept raw Telegram message text, parse it, and store the signal."""
    raw_text = (await request.body()).decode("utf-8").strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="Empty message body")

    signal = parse_signal(raw_text)
    if signal is None:
        raise HTTPException(
            status_code=422,
            detail="Could not parse trading signal from message",
        )

    stored = signal_store.append(signal)
    return stored.to_ea_dict()


@app.post("/api/v1/signal/json", status_code=status.HTTP_201_CREATED)
async def ingest_json_signal(signal: TradingSignal) -> dict:
    """Accept a pre-structured TradingSignal JSON (for testing)."""
    stored = signal_store.append(signal)
    return stored.to_ea_dict()


@app.get("/api/v1/signals")
def get_signals(since: int = 0) -> dict:
    """Return signals with seq > since, for EA cursor-based polling.

    The EA maintains a lastSeq and passes it here. Only new signals are returned.
    """
    signals = signal_store.since(since)
    return {
        "signals": [s.to_ea_dict() for s in signals],
    }
