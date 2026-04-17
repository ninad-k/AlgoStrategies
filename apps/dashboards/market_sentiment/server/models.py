"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel
from typing import Optional


class PriceSummary(BaseModel):
    symbol: str
    ticker: str
    display_name: str
    current_price: float
    open_price: float
    day_high: float
    day_low: float
    prev_close: float
    change: float          # absolute change
    change_pct: float      # % change
    volume: Optional[int]
    week_52_high: float
    week_52_low: float
    currency: str


class TechnicalLevels(BaseModel):
    pivot: float
    supports: list[float]   # S1, S2, S3
    resistances: list[float]  # R1, R2, R3
    swing_supports: list[float]
    swing_resistances: list[float]
    rsi_14: Optional[float]
    macd_signal: Optional[str]   # "BULLISH" | "BEARISH" | "NEUTRAL"
    trend_signal: Optional[str]  # "UPTREND" | "DOWNTREND" | "SIDEWAYS"
    atr: Optional[float]


class NewsArticle(BaseModel):
    title: str
    summary: str
    source: str
    published: str
    url: str


class EconomicEvent(BaseModel):
    title: str
    country: str
    impact: str           # "HIGH" | "MEDIUM" | "LOW"
    scheduled_time: str
    forecast: Optional[str]
    previous: Optional[str]
    url: Optional[str]


class PredictionDetail(BaseModel):
    direction: str         # "UP" | "DOWN" | "SIDEWAYS"
    timeframe: str
    target: Optional[float]
    stop_loss: Optional[float]
    confidence: int        # 0–100


class SymbolAnalysis(BaseModel):
    symbol: str
    display_name: str
    group: str
    price: PriceSummary
    technical: TechnicalLevels
    sentiment: str         # "BULLISH" | "BEARISH" | "NEUTRAL"
    confidence: int        # 0–100
    summary: str
    key_reasons: list[str]
    prediction: PredictionDetail
    risks: list[str]
    news_sentiment: str    # "POSITIVE" | "NEGATIVE" | "NEUTRAL"
    event_impact: str      # "HIGH" | "MEDIUM" | "LOW"
    news: list[NewsArticle]
    analyzed_at: str


class DashboardResponse(BaseModel):
    symbols: list[SymbolAnalysis]
    events: list[EconomicEvent]
    generated_at: str
    cache_hit: bool
