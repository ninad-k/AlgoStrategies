"""TeleTrader local API -- FastAPI server for signal ingestion, EA polling, and dashboard."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from teletrader.api.dashboard import html_router, router as dashboard_router
from teletrader.config import settings
from teletrader.models.trading_signal import TradingSignal
from teletrader.parsing.signal_parser import parse_signal

logger = logging.getLogger("teletrader.api")

app = FastAPI(title="TeleTrader API", version="0.2.0")

# --- Dashboard routes ---
app.include_router(dashboard_router)
app.include_router(html_router)

# --- Store initialization based on config ---
if settings.store_backend == "sqlite":
    from teletrader.store.sqlite_store import SQLiteSignalStore
    signal_store = SQLiteSignalStore(settings.db_path)
    logger.info("Using SQLite store: %s", settings.db_path)
else:
    from teletrader.store.memory_store import InMemorySignalStore
    signal_store = InMemorySignalStore()
    logger.info("Using in-memory store")

# Expose store on app.state for dashboard router
app.state.signal_store = signal_store


class SignalIngestRequest(BaseModel):
    raw_text: str
    source: str = "unknown"


class NotifyRequest(BaseModel):
    message: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "teletrader"}


@app.post("/api/v1/signal", status_code=status.HTTP_201_CREATED)
async def ingest_raw_signal(request: Request) -> dict:
    """Accept raw Telegram message text, parse it, and store the signal.

    Backward-compatible endpoint (source defaults to 'unknown').
    """
    raw_text = (await request.body()).decode("utf-8").strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="Empty message body")

    logger.info("[SIGNAL_RECEIVED] raw text (%d chars), source=unknown", len(raw_text))

    signal = parse_signal(raw_text)
    if signal is None:
        logger.warning("[SIGNAL_PARSE_FAILED] Could not parse: %s", raw_text[:80])
        raise HTTPException(
            status_code=422,
            detail="Could not parse trading signal from message",
        )

    signal.source = "unknown"
    signal.received_at_utc = datetime.now(UTC)

    logger.info(
        "[SIGNAL_PARSED] %s %s %s @ %.5f SL=%.5f TPs=%s lot=%s",
        signal.symbol, signal.direction, signal.order_type,
        signal.entry_price, signal.stop_loss, signal.take_profits, signal.lot_size,
    )

    stored = signal_store.append(signal)
    logger.info("[SIGNAL_STORED] id=%s seq=%d", stored.signal_id, stored.seq)
    return stored.to_ea_dict()


@app.post("/api/v1/signal/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_signal_with_source(body: SignalIngestRequest) -> dict:
    """Accept JSON with raw_text and source, parse and store the signal.

    Used by the bot and forwarder for source-tracked signal ingestion.
    """
    raw_text = body.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="Empty raw_text")

    logger.info(
        "[SIGNAL_RECEIVED] raw text (%d chars), source=%s", len(raw_text), body.source
    )

    signal = parse_signal(raw_text)
    if signal is None:
        logger.warning("[SIGNAL_PARSE_FAILED] Could not parse: %s", raw_text[:80])
        raise HTTPException(
            status_code=422,
            detail="Could not parse trading signal from message",
        )

    signal.source = body.source
    signal.received_at_utc = datetime.now(UTC)

    logger.info(
        "[SIGNAL_PARSED] %s %s %s @ %.5f SL=%.5f TPs=%s lot=%s source=%s",
        signal.symbol, signal.direction, signal.order_type,
        signal.entry_price, signal.stop_loss, signal.take_profits,
        signal.lot_size, signal.source,
    )

    stored = signal_store.append(signal)
    logger.info("[SIGNAL_STORED] id=%s seq=%d source=%s", stored.signal_id, stored.seq, stored.source)
    return stored.to_ea_dict()


@app.post("/api/v1/signal/json", status_code=status.HTTP_201_CREATED)
async def ingest_json_signal(signal: TradingSignal) -> dict:
    """Accept a pre-structured TradingSignal JSON (for testing)."""
    stored = signal_store.append(signal)
    return stored.to_ea_dict()


@app.get("/api/v1/signals")
def get_signals(since: int = 0) -> dict:
    """Return signals with seq > since, for EA cursor-based polling."""
    signals = signal_store.since(since)
    logger.debug("[SIGNAL_POLLED] since=%d, returning %d signals", since, len(signals))
    return {
        "signals": [s.to_ea_dict() for s in signals],
    }


@app.post("/api/v1/notify")
async def send_notification(body: NotifyRequest) -> dict:
    """Send a notification message to Telegram via the bot.

    Called by the EA to report trade events back to the user.
    """
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("[NOTIFY] Bot token or chat ID not configured")
        raise HTTPException(status_code=503, detail="Telegram bot not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": body.message,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("[NOTIFY] Telegram message sent: %s", body.message[:80])
                return {"status": "sent"}
            else:
                logger.warning("[NOTIFY] Telegram API error: %s", resp.text)
                return {"status": "error", "detail": resp.text}
    except Exception as e:
        logger.exception("[NOTIFY] Failed to send Telegram message")
        raise HTTPException(status_code=502, detail=str(e))
