"""
Shared Pydantic models used across the Intelligence Suite.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class MarketRegime(str, Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    BREAKOUT = "BREAKOUT"


class TradeDecision(BaseModel):
    action: TradeAction = TradeAction.HOLD
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sl_distance_atr: float = Field(default=1.0, ge=0.5, le=2.0)
    tp_distance_atr: float = Field(default=1.5, ge=0.75, le=3.0)
    reason: str = ""
    symbol: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    model_name: str = ""
    regime: Optional[MarketRegime] = None
    sentiment_score: Optional[float] = None
    raw_response: Optional[str] = None
    prompt_sent: Optional[str] = None


class EnsembleDecision(BaseModel):
    final_action: TradeAction = TradeAction.HOLD
    final_confidence: float = 0.0
    sl_distance_atr: float = 1.0
    tp_distance_atr: float = 1.5
    reason: str = ""
    symbol: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    regime: Optional[MarketRegime] = None
    sentiment_score: Optional[float] = None
    individual_decisions: list[TradeDecision] = Field(default_factory=list)
    vote_summary: dict = Field(default_factory=dict)
    model_weights: dict = Field(default_factory=dict)


class TradeRecord(BaseModel):
    trade_id: str
    symbol: str
    action: TradeAction
    qty: float
    entry_price: float
    sl: float
    tp: float
    confidence: float
    reason: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    model_name: str = "ensemble"
    regime: Optional[str] = None
    status: str = "OPEN"
    close_price: Optional[float] = None
    profit: Optional[float] = None
    close_time: Optional[str] = None


class PortfolioPosition(BaseModel):
    symbol: str
    direction: str
    volume: float
    entry_price: float
    current_price: float
    profit: float
    swap: float = 0.0
    account_id: Optional[str] = None


class SentimentSignal(BaseModel):
    symbol: str
    score: float = Field(ge=-1.0, le=1.0)
    sources: dict = Field(default_factory=dict)
    headlines: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class VolumeProfileLevel(BaseModel):
    price: float
    volume: float
    tpo_count: int = 0
    is_poc: bool = False
    is_vah: bool = False
    is_val: bool = False
    is_hvn: bool = False
    is_lvn: bool = False
