from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class StrategyBase(BaseModel):
    name: str
    magic_number: Optional[int] = None
    symbol_filter: list[str] = []
    lot_size: Optional[float] = None
    time_offset_min: int = 0


class StrategyCreate(StrategyBase):
    pass


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    magic_number: Optional[int] = None
    symbol_filter: Optional[list[str]] = None
    lot_size: Optional[float] = None
    time_offset_min: Optional[int] = None


class StrategyRead(StrategyBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
