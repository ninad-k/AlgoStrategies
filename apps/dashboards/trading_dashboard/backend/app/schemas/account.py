from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AccountCreate(BaseModel):
    account_id: str
    broker: Optional[str] = None
    currency: str = "USD"


class AccountRead(AccountCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
