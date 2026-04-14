"""TeleTrader Telegram bot — listens for forwarded signal messages.

Usage:
    python -m teletrader.telegram.bot

The bot listens for text messages forwarded to it (or sent directly).
When a message contains trading keywords (buy/sell + target/SL), it
parses the signal and stores it via the configured backend (local API or AWS).

Set environment variables:
    TELETRADER_TELEGRAM_BOT_TOKEN  — your bot token from @BotFather
    TELETRADER_MODE                — "local" (default) or "aws"
    TELETRADER_API_PORT            — local API port (default: 8100)
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys

import httpx

from teletrader.config import settings
from teletrader.parsing.signal_parser import parse_signal

logger = logging.getLogger("teletrader.telegram")

# Quick filter: skip messages that clearly aren't trading signals
_SIGNAL_KEYWORDS_RE = re.compile(
    r"\b(buy|sell|long|short)\b", re.IGNORECASE
)

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        ContextTypes,
        MessageHandler,
        filters,
    )
except ImportError:
    print("python-telegram-bot is required: pip install teletrader[telegram]")
    sys.exit(1)


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process incoming text messages for trading signals."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not _SIGNAL_KEYWORDS_RE.search(text):
        logger.debug("Skipping non-signal message: %s", text[:50])
        return

    # Determine source: forwarded message or manual
    source = "forwarded" if update.message.forward_date else "manual"

    # Try to parse
    signal = parse_signal(text)
    if signal is None:
        logger.info("Could not parse signal from message: %s", text[:80])
        return

    logger.info(
        "Parsed signal [%s]: %s %s %s @ %.5f, SL=%.5f, TPs=%s, Lot=%s",
        source,
        signal.symbol,
        signal.direction,
        signal.order_type,
        signal.entry_price,
        signal.stop_loss,
        signal.take_profits,
        signal.lot_size,
    )

    # Forward to backend
    try:
        await _forward_signal(text, source)
        if update.message:
            await update.message.reply_text(
                f"Signal received: {signal.symbol} {signal.direction.upper()} "
                f"@ {signal.entry_price}"
            )
    except Exception:
        logger.exception("Failed to forward signal")
        if update.message:
            await update.message.reply_text("Failed to process signal. Check logs.")


async def _forward_signal(raw_text: str, source: str = "unknown") -> None:
    """Forward raw signal text to the configured backend with source tracking."""
    if settings.mode == "local":
        url = f"http://127.0.0.1:{settings.api_port}/api/v1/signal/ingest"
    else:
        import os
        api_url = os.environ.get("TELETRADER_AWS_API_URL", "")
        if not api_url:
            raise ValueError("TELETRADER_AWS_API_URL not set for AWS mode")
        url = f"{api_url}/signal"

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, json={"raw_text": raw_text, "source": source})
        response.raise_for_status()
        logger.info("Signal forwarded [%s]: %s", source, response.json())


def main() -> None:
    """Entry point for the Telegram bot."""
    if not settings.telegram_bot_token:
        print("Error: TELETRADER_TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("Starting TeleTrader bot (mode=%s)", settings.mode)

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Handle all text messages (including forwarded ones)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))

    logger.info("Bot is polling for messages...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
