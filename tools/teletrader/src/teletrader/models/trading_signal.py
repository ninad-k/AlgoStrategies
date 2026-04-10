from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TradingSignal(BaseModel):
    signal_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    seq: int = 0  # assigned by the store
    symbol: str
    direction: Literal["buy", "sell"]
    order_type: Literal["buy_stop", "sell_stop", "buy_limit", "sell_limit"]
    entry_price: float
    stop_loss: float
    take_profits: list[float]
    raw_text: str
    parsed_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_ea_dict(self) -> dict:
        """Serialize for the MT5 EA JSON response."""
        return {
            "signalId": self.signal_id,
            "seq": self.seq,
            "symbol": self.symbol,
            "direction": self.direction,
            "orderType": self.order_type,
            "entryPrice": self.entry_price,
            "stopLoss": self.stop_loss,
            "takeProfits": self.take_profits,
            "parsedAtUtc": self.parsed_at_utc.isoformat(),
        }
