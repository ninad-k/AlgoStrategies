from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class TeleTraderSettings(BaseSettings):
    mode: Literal["local", "aws"] = "local"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Local API
    api_port: int = 8100

    # AWS (only when mode="aws")
    aws_region: str = "us-east-1"
    dynamodb_table: str = "teletrader-signals"

    model_config = {"env_prefix": "TELETRADER_", "env_file": ".env", "extra": "ignore"}


settings = TeleTraderSettings()
