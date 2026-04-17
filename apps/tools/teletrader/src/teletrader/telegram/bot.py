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
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except ImportError:
    print("python-telegram-bot is required: pip install teletrader[telegram]")
    sys.exit(1)


async def _handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if update.message:
        await update.message.reply_text(
            "TeleTrader Bot is running!\n\n"
            "Send or forward a trading signal to place an order.\n"
            "Example:\n"
            "XAUUSD Buy Above 2400\n"
            "SL 2380\n"
            "Target 2410 2420 2440\n"
            "Lot 0.05"
        )


async def _handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command — check API connectivity."""
    if not update.message:
        return

    try:
        url = f"http://127.0.0.1:{settings.api_port}/health"
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            if response.status_code == 200:
                await update.message.reply_text("API: Connected\nStatus: Ready to receive signals")
            else:
                await update.message.reply_text(f"API: Error (HTTP {response.status_code})")
    except Exception as e:
        await update.message.reply_text(f"API: Disconnected ({e})")


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process incoming text messages for trading signals."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not _SIGNAL_KEYWORDS_RE.search(text):
        logger.debug("Skipping non-signal message: %s", text[:50])
        if update.message:
            await update.message.reply_text(
                "No trading signal detected.\n"
                "Message must contain: buy, sell, long, or short"
            )
        return

    # Determine source: forwarded message or manual
    source = "forwarded" if update.message.forward_date else "manual"
    logger.info("[BOT] Received message (%d chars), source=%s", len(text), source)

    # Try to parse
    signal = parse_signal(text)
    if signal is None:
        logger.warning("[BOT] Could not parse signal from message: %s", text[:120])
        if update.message:
            await update.message.reply_text(
                "Could not parse trading signal.\n\n"
                "Expected format:\n"
                "SYMBOL BUY/SELL ABOVE/BELOW PRICE\n"
                "SL PRICE\n"
                "TARGET PRICE1 PRICE2 PRICE3\n\n"
                f"Your message: {text[:100]}"
            )
        return

    logger.info(
        "[BOT] Parsed signal [%s]: %s %s %s @ %.5f, SL=%.5f, TPs=%s, Lot=%s",
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
            lot_info = f"\nLot: {signal.lot_size}" if signal.lot_size else ""
            await update.message.reply_text(
                f"Signal received!\n"
                f"{signal.symbol} {signal.direction.upper()} @ {signal.entry_price}\n"
                f"SL: {signal.stop_loss}\n"
                f"TPs: {signal.take_profits}"
                f"{lot_info}\n"
                f"Source: {source}"
            )
    except Exception as e:
        logger.exception("[BOT] Failed to forward signal")
        if update.message:
            await update.message.reply_text(
                f"Failed to forward signal to API.\n"
                f"Error: {e}\n\n"
                f"Is the API server running on port {settings.api_port}?"
            )


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

    # Command handlers
    app.add_handler(CommandHandler("start", _handle_start))
    app.add_handler(CommandHandler("status", _handle_status))

    # Handle all text messages (including forwarded ones)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))

    logger.info("Bot is polling for messages...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
