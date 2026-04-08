from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class AttributionRuleCreate(BaseModel):
    category_type: str
    category_id: int
    rule_type: str   # magic | comment_prefix | lot_size | symbol_list
    rule_value: dict[str, Any]
    priority: int = 100


class AttributionRuleUpdate(BaseModel):
    rule_value: Optional[dict[str, Any]] = None
    priority: Optional[int] = None


class AttributionRuleRead(AttributionRuleCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
