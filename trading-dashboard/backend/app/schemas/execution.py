from pydantic import BaseModel


class LiveTradingStatus(BaseModel):
    live_trading_enabled: bool


class LiveTradingUpdate(BaseModel):
    live_trading_enabled: bool
