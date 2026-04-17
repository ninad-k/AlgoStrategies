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
    TELETRADER_FORWARDER_CHANNELS   — comma-separated channel usernames, IDs, or
                                      display names (searched via dialogs)
                                      e.g. "drd_signals,-1001234567890,Dr Devendra"
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
    from telethon.tl.types import Channel
except ImportError:
    print("Telethon is required: pip install teletrader[forwarder]")
    sys.exit(1)


async def _forward_to_api(raw_text: str, source: str = "unknown") -> None:
    """Forward raw signal text to the TeleTrader local API with source tracking."""
    url = f"http://127.0.0.1:{settings.api_port}/api/v1/signal/ingest"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, json={"raw_text": raw_text, "source": source})
        if response.status_code == 201:
            data = response.json()
            logger.info(
                "[FORWARD] Signal sent [%s]: %s %s @ %s",
                source,
                data.get("symbol", "?"),
                data.get("direction", "?"),
                data.get("entryPrice", "?"),
            )
        elif response.status_code == 422:
            logger.debug("[FORWARD] Message not a valid signal, skipped")
        else:
            logger.warning("[FORWARD] API returned %s: %s", response.status_code, response.text)


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


async def _resolve_channels(client: TelegramClient, channels: list[str | int]) -> tuple[list[int], dict[int, str]]:
    """Resolve channel names/usernames/IDs to numeric entity IDs.

    For each channel specifier:
      - Numeric ID: use directly
      - @username: resolve via get_entity
      - Display name (e.g. "Dr Devendra's Crypto Advisory"): search through
        the user's dialogs to find a matching channel by title
    """
    resolved_ids: list[int] = []
    resolved_names: dict[int, str] = {}

    for ch in channels:
        # Already a numeric ID
        if isinstance(ch, int):
            try:
                entity = await client.get_entity(ch)
                title = getattr(entity, "title", str(ch))
                resolved_ids.append(entity.id)
                resolved_names[entity.id] = title
                logger.info("[RESOLVE] Channel ID %d -> %s", ch, title)
            except Exception as e:
                logger.warning("[RESOLVE] Could not resolve channel ID %d: %s", ch, e)
            continue

        # Try direct resolution first (works for @usernames)
        try:
            entity = await client.get_entity(ch)
            title = getattr(entity, "title", ch)
            resolved_ids.append(entity.id)
            resolved_names[entity.id] = title
            logger.info("[RESOLVE] '%s' -> %s (ID: %d)", ch, title, entity.id)
            continue
        except Exception:
            logger.info("[RESOLVE] Direct lookup failed for '%s', searching dialogs...", ch)

        # Search through dialogs for a title match (handles display names)
        found = False
        search_lower = ch.lower()
        async for dialog in client.iter_dialogs():
            if not isinstance(dialog.entity, Channel):
                continue
            dialog_title = dialog.title or ""
            if search_lower in dialog_title.lower():
                resolved_ids.append(dialog.entity.id)
                resolved_names[dialog.entity.id] = dialog_title
                logger.info("[RESOLVE] Found '%s' via dialog search -> %s (ID: %d)",
                            ch, dialog_title, dialog.entity.id)
                found = True
                break

        if not found:
            logger.warning("[RESOLVE] Could not find channel '%s' in your dialogs. "
                           "Make sure you are subscribed to it.", ch)

    return resolved_ids, resolved_names


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
    logger.info("[INIT] Configured channels: %s", channels)

    # Create Telethon client with session file stored in working directory
    client = TelegramClient(
        "teletrader_forwarder",
        int(settings.telegram_api_id),
        settings.telegram_api_hash,
    )

    # Connect and start
    if settings.telegram_phone:
        await client.start(phone=settings.telegram_phone)
    else:
        await client.start()

    me = await client.get_me()
    logger.info("[INIT] Forwarder connected as: %s (ID: %s)", me.first_name, me.id)

    # Resolve all channels to numeric IDs (handles display names, usernames, IDs)
    resolved_ids, resolved_names = await _resolve_channels(client, channels)

    if not resolved_ids:
        logger.error("[INIT] No channels could be resolved. Exiting.")
        print("\nERROR: No channels resolved. Check TELETRADER_FORWARDER_CHANNELS.")
        print("Use @username, numeric ID (-100...), or a partial display name.")
        await client.disconnect()
        sys.exit(1)

    logger.info("[INIT] Listening to %d channel(s): %s", len(resolved_ids),
                [f"{resolved_names.get(cid, '?')} ({cid})" for cid in resolved_ids])

    # Register event handler with resolved numeric IDs
    @client.on(events.NewMessage(chats=resolved_ids))
    async def handler(event: events.NewMessage.Event) -> None:
        """Handle new messages from monitored channels."""
        text = event.message.text
        if not text:
            return

        # Quick filter — skip non-signal messages
        if not _SIGNAL_KEYWORDS_RE.search(text):
            return

        # Build source tag from channel info
        chat = await event.get_chat()
        channel_name = getattr(chat, "title", None) or getattr(chat, "username", None) or str(chat.id)
        source = f"channel:{channel_name}"

        logger.info("[SIGNAL] Detected from %s: %s", source, text[:80])

        try:
            await _forward_to_api(text, source)
        except Exception:
            logger.exception("[SIGNAL] Failed to forward signal to API")

    logger.info("[INIT] Forwarder is running. Waiting for signals...")
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
