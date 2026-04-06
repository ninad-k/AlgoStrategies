"""Telegram notifications — fire-and-forget with 5s timeout."""

from __future__ import annotations

import logging

import aiohttp

from . import config
from .models import ExecutionResult, StateUpdate

log = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    """Non-blocking Telegram alerts. All methods are no-ops if unconfigured."""

    def __init__(self) -> None:
        self.enabled = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
        if not self.enabled:
            log.info("Telegram notifications disabled (no token/chat_id)")

    async def notify_trade_opened(self, result: ExecutionResult) -> None:
        if not self.enabled:
            return
        text = (
            f"Trade Opened\n"
            f"Ticket: {result.ticket}\n"
            f"Price: {result.executed_price:.5f}\n"
            f"Lot: {result.executed_lot:.2f}\n"
            f"Signal: {result.signal_id}"
        )
        await self._send(text)

    async def notify_trade_closed(self, signal_id: str, ticket: int, profit: float) -> None:
        if not self.enabled:
            return
        emoji = "+" if profit >= 0 else ""
        text = (
            f"Trade Closed\n"
            f"Ticket: {ticket}\n"
            f"PnL: {emoji}{profit:.2f}\n"
            f"Signal: {signal_id}"
        )
        await self._send(text)

    async def notify_partial_tp(self, update: StateUpdate) -> None:
        if not self.enabled:
            return
        d = update.details
        text = (
            f"Partial TP{d.get('tp_level', '?')}\n"
            f"Symbol: {update.symbol}\n"
            f"Closed: {d.get('closed_lot', 0):.2f} lots\n"
            f"Remaining: {d.get('remaining_lot', 0):.2f} lots\n"
            f"Profit: {d.get('profit_pips', 0):.1f} pips"
        )
        await self._send(text)

    async def notify_error(self, result: ExecutionResult) -> None:
        if not self.enabled:
            return
        text = (
            f"Execution Error\n"
            f"Code: {result.error_code}\n"
            f"Message: {result.error_message}\n"
            f"Signal: {result.signal_id}"
        )
        await self._send(text)

    async def notify_risk_rejection(self, action: str, symbol: str, reason: str) -> None:
        if not self.enabled:
            return
        text = f"Risk Rejected\n{action} {symbol}\nReason: {reason}"
        await self._send(text)

    async def _send(self, text: str) -> None:
        url = _TELEGRAM_API.format(token=config.TELEGRAM_BOT_TOKEN)
        payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        log.warning("Telegram send failed: %d %s", resp.status, body[:200])
        except Exception as e:
            log.warning("Telegram send error: %s", e)
