from __future__ import annotations

from datetime import datetime

from reyconnector.contracts.base import CamelModel


class PartialTPConfig(CamelModel):
    """Default partial take-profit configuration for a connection."""

    tp1_close_percent: float = 40.0
    tp2_close_percent: float = 30.0
    tp3_close_percent: float = 30.0


class ConnectionConfig(CamelModel):
    """Per-connection trading configuration with risk and partial profit defaults."""

    default_lots: float = 0.10
    default_magic: int = 0
    partial_tp: PartialTPConfig = PartialTPConfig()
    enabled_strategies: list[str] | None = None


class ConnectionSummary(CamelModel):
    id: str
    display_name: str
    is_enabled: bool
    created_at_utc: datetime
    last_seen_at_utc: datetime | None = None
    config: ConnectionConfig = ConnectionConfig()
