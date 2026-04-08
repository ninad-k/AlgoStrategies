from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TraderBase(BaseModel):
    name: str
    default_lot_size: Optional[float] = None
    linked_user_id: Optional[int] = None


class TraderCreate(TraderBase):
    pass


class TraderUpdate(BaseModel):
    name: Optional[str] = None
    default_lot_size: Optional[float] = None
    linked_user_id: Optional[int] = None


class TraderRead(TraderBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
