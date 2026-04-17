from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class TeleTraderSettings(BaseSettings):
    mode: Literal["local", "aws"] = "local"

    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Telegram Forwarder (Telethon user account)
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_phone: str = ""
    forwarder_channels: str = ""  # comma-separated channel usernames or IDs

    # Local API
    api_port: int = 8100

    # Storage
    store_backend: Literal["memory", "sqlite"] = "sqlite"
    db_path: str = "teletrader.db"

    # Logging
    log_file: str = "teletrader.log"
    log_level: str = "INFO"

    # AWS (only when mode="aws")
    aws_region: str = "us-east-1"
    dynamodb_table: str = "teletrader-signals"

    model_config = {"env_prefix": "TELETRADER_", "env_file": ".env", "extra": "ignore"}


settings = TeleTraderSettings()
