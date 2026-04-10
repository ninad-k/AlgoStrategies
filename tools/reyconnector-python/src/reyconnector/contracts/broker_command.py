from __future__ import annotations

from typing import Literal

from reyconnector.contracts.base import CamelModel


class NoopCommand(CamelModel):
    kind: Literal["noop"] = "noop"
    reason: str


class MarketOrderCommand(CamelModel):
    kind: Literal["market_order"] = "market_order"
    symbol: str
    action: Literal["buy", "sell"]
    lots: float
    stop_loss: float | None = None
    take_profit: float | None = None
    magic: int = 0
    comment: str = ""


class PartialCloseCommand(CamelModel):
    kind: Literal["partial_close"] = "partial_close"
    symbol: str
    action: Literal["buy", "sell"]
    close_percent: float
    trigger_price: float
    magic: int = 0
    comment: str = ""


class TrailingStopCommand(CamelModel):
    kind: Literal["trailing_stop"] = "trailing_stop"
    symbol: str
    action: Literal["buy", "sell"]
    activation_price: float
    trailing_distance: float
    magic: int = 0
    comment: str = ""


BrokerCommand = NoopCommand | MarketOrderCommand | PartialCloseCommand | TrailingStopCommand
