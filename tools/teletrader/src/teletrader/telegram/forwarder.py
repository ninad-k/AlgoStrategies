"""TeleTrader Channel Forwarder — monitors Telegram channels and forwards signals.

Uses Telethon (Telegram user client) to listen to channels you're subscribed to
and automatically forwards messages containing trading signals to the TeleTrader API.

Usage:
    python -m teletrader.telegram.forwarder

First-time setup:
    1. Go to https://my.telegram.org/apps and create an app
    2. Copy the api_id and api_hash
    3. Set environment variables (see below)

Environment variables:
    TELETRADER_TELEGRAM_API_ID      — from my.telegram.org
    TELETRADER_TELEGRAM_API_HASH    — from my.telegram.org
    TELETRADER_TELEGRAM_PHONE       — your phone number (e.g. +919876543210)
    TELETRADER_FORWARDER_CHANNELS   — comma-separated channel usernames or IDs
                                      e.g. "drd_signals,forex_vip,-1001234567890"
    TELETRADER_API_PORT             — local API port (default: 8100)
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys

import httpx

from teletrader.config import settings

logger = logging.getLogger("teletrader.forwarder")

# Quick filter: only forward messages that look like trading signals
_SIGNAL_KEYWORDS_RE = re.compile(
    r"\b(buy|sell|long|short)\b", re.IGNORECASE
)

try:
    from telethon import TelegramClient, events
except ImportError:
    print("Telethon is required: pip install teletrader[forwarder]")
    sys.exit(1)


async def _forward_to_api(raw_text: str) -> None:
    """Forward raw signal text to the TeleTrader local API."""
    url = f"http://127.0.0.1:{settings.api_port}/api/v1/signal"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, content=raw_text)
        if response.status_code == 201:
            data = response.json()
            logger.info(
                "Signal forwarded: %s %s @ %s",
                data.get("symbol", "?"),
                data.get("direction", "?"),
                data.get("entryPrice", "?"),
            )
        elif response.status_code == 422:
            logger.debug("Message not a valid signal, skipped")
        else:
            logger.warning("API returned %s: %s", response.status_code, response.text)


def _parse_channel_list(channels_str: str) -> list[str | int]:
    """Parse comma-separated channel usernames/IDs."""
    result: list[str | int] = []
    for ch in channels_str.split(","):
        ch = ch.strip()
        if not ch:
            continue
        # If it looks like a numeric ID (possibly negative), convert to int
        try:
            result.append(int(ch))
        except ValueError:
            # Remove @ prefix if present
            result.append(ch.lstrip("@"))
    return result


async def run_forwarder() -> None:
    """Main forwarder loop."""
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("Error: TELETRADER_TELEGRAM_API_ID and TELETRADER_TELEGRAM_API_HASH required")
        print("Get them from https://my.telegram.org/apps")
        sys.exit(1)

    if not settings.forwarder_channels:
        print("Error: TELETRADER_FORWARDER_CHANNELS not set")
        print("Set comma-separated channel usernames, e.g.: drd_signals,forex_vip")
        sys.exit(1)

    channels = _parse_channel_list(settings.forwarder_channels)
    logger.info("Monitoring channels: %s", channels)

    # Create Telethon client with session file stored in working directory
    client = TelegramClient(
        "teletrader_forwarder",
        int(settings.telegram_api_id),
        settings.telegram_api_hash,
    )

    @client.on(events.NewMessage(chats=channels))
    async def handler(event: events.NewMessage.Event) -> None:
        """Handle new messages from monitored channels."""
        text = event.message.text
        if not text:
            return

        # Quick filter — skip non-signal messages
        if not _SIGNAL_KEYWORDS_RE.search(text):
            return

        logger.info("Signal detected from channel: %s", text[:80])

        try:
            await _forward_to_api(text)
        except Exception:
            logger.exception("Failed to forward signal to API")

    # Connect and start
    if settings.telegram_phone:
        await client.start(phone=settings.telegram_phone)
    else:
        await client.start()

    me = await client.get_me()
    logger.info("Forwarder connected as: %s (ID: %s)", me.first_name, me.id)

    # Resolve and validate channels
    for ch in channels:
        try:
            entity = await client.get_entity(ch)
            logger.info("Listening to: %s (ID: %s)", getattr(entity, 'title', ch), entity.id)
        except Exception as e:
            logger.warning("Could not resolve channel '%s': %s", ch, e)

    logger.info("Forwarder is running. Waiting for signals...")
    await client.run_until_disconnected()


def main() -> None:
    """Entry point for the channel forwarder."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(run_forwarder())


if __name__ == "__main__":
    main()
