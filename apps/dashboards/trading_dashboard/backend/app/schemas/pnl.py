from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PnlSummary(BaseModel):
    total_profit: float
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_profit_per_trade: float
    best_trade: float
    worst_trade: float


class PnlByCategory(BaseModel):
    category_id: Optional[int]
    category_name: str
    category_type: str
    total_profit: float
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_profit_per_trade: float
    best_trade: float
    worst_trade: float
    avg_planned_rr: Optional[float]
    avg_realised_rr: Optional[float]
    no_risk_data_count: int


class RiskSummary(BaseModel):
    avg_planned_rr: Optional[float]
    avg_realised_rr: Optional[float]
    avg_rr_deviation: Optional[float]
    no_risk_data_count: int
    trades_with_risk: int


class TradeRow(BaseModel):
    id: int
    open_time: datetime
    close_time: Optional[datetime]
    symbol: str
    type: str
    lots: float
    open_price: float
    close_price: Optional[float]
    sl: Optional[float]
    tp: Optional[float]
    profit: float
    commission: float
    swap: float
    net_profit: float
    planned_rr: Optional[float]
    realised_rr: Optional[float]
    rr_deviation: Optional[float]
    attribution_level: int
