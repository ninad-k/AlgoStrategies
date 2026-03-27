"""Pydantic schemas for the backtester API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    name: str = ""
    pinescript: str = ""
    strategy_config: Optional[dict[str, Any]] = None
    symbol: str = "XAUUSD"
    timeframe: str = "1d"
    start_date: str = "2020-01-01"
    end_date: str = ""
    initial_capital: float = 10000.0
    leverage: float = 1.0
    commission_pct: float = 0.0
    slippage_points: float = 0.0
    input_overrides: dict[str, Any] = Field(default_factory=dict)


class BacktestStatus(BaseModel):
    id: int
    status: str  # pending | downloading | computing | running | complete | error
    progress: float = 0.0
    phase: str = ""
    error: Optional[str] = None


class InputParam(BaseModel):
    name: str
    type: str  # int, float, bool, string
    default: Any
    title: str = ""
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    options: Optional[list[str]] = None
    group: str = ""


class ParseResult(BaseModel):
    strategy_name: str = ""
    inputs: list[InputParam] = []
    indicators_found: list[str] = []
    entry_conditions: list[str] = []
    exit_rules: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []


class TradeRecord(BaseModel):
    order_num: int
    deal_num: int
    open_time: str
    close_time: str
    symbol: str
    type: str  # buy / sell
    direction: str  # long / short
    volume: float
    entry_price: float
    exit_price: float
    sl: float = 0.0
    tp: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0
    balance: float = 0.0
    comment: str = ""
    mfe: float = 0.0
    mae: float = 0.0


class OrderRecord(BaseModel):
    open_time: str
    order_num: int
    symbol: str
    type: str
    volume: str
    price: float
    sl: float = 0.0
    tp: float = 0.0
    time: str = ""
    state: str = "filled"
    comment: str = ""


class DealRecord(BaseModel):
    time: str
    deal_num: int
    symbol: str
    type: str
    direction: str  # in / out / balance
    volume: float
    price: float
    order_num: int
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0
    balance: float = 0.0
    comment: str = ""


class EquityPoint(BaseModel):
    timestamp: str
    balance: float
    equity: float
    drawdown: float = 0.0
    drawdown_pct: float = 0.0


class MetricsReport(BaseModel):
    total_net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    recovery_factor: float = 0.0
    expected_payoff: float = 0.0
    sharpe_ratio: float = 0.0
    ahpr: float = 0.0
    ahpr_pct: float = 0.0
    ghpr: float = 0.0
    ghpr_pct: float = 0.0

    balance_dd_absolute: float = 0.0
    balance_dd_maximal: float = 0.0
    balance_dd_maximal_pct: float = 0.0
    balance_dd_relative_pct: float = 0.0
    balance_dd_relative_val: float = 0.0
    equity_dd_absolute: float = 0.0
    equity_dd_maximal: float = 0.0
    equity_dd_maximal_pct: float = 0.0
    equity_dd_relative_pct: float = 0.0
    equity_dd_relative_val: float = 0.0

    total_trades: int = 0
    short_trades: int = 0
    short_trades_won_pct: float = 0.0
    long_trades: int = 0
    long_trades_won_pct: float = 0.0
    profit_trades: int = 0
    profit_trades_pct: float = 0.0
    loss_trades: int = 0
    loss_trades_pct: float = 0.0
    largest_profit_trade: float = 0.0
    largest_loss_trade: float = 0.0
    average_profit_trade: float = 0.0
    average_loss_trade: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_wins_money: float = 0.0
    max_consecutive_losses: int = 0
    max_consecutive_losses_money: float = 0.0
    max_consecutive_profit: float = 0.0
    max_consecutive_profit_count: int = 0
    max_consecutive_loss: float = 0.0
    max_consecutive_loss_count: int = 0
    avg_consecutive_wins: float = 0.0
    avg_consecutive_losses: float = 0.0

    corr_profits_mfe: float = 0.0
    corr_profits_mae: float = 0.0
    corr_mfe_mae: float = 0.0
    min_holding_time: str = ""
    max_holding_time: str = ""
    avg_holding_time: str = ""

    lr_correlation: float = 0.0
    lr_standard_error: float = 0.0
    z_score: float = 0.0
    z_score_pct: float = 0.0

    bars: int = 0
    total_deals: int = 0


class BacktestReport(BaseModel):
    id: int
    name: str
    symbol: str
    timeframe: str
    period: str
    initial_capital: float
    leverage: float
    commission_pct: float
    currency: str = "USD"
    strategy_name: str = ""
    inputs: list[InputParam] = []
    metrics: MetricsReport = Field(default_factory=MetricsReport)
    equity_curve: list[EquityPoint] = []
    orders: list[OrderRecord] = []
    deals: list[DealRecord] = []
    summary: dict[str, float] = Field(default_factory=dict)
    created_at: str = ""


class BacktestSummary(BaseModel):
    id: int
    name: str
    symbol: str
    timeframe: str
    period: str
    strategy_name: str
    total_net_profit: float
    profit_factor: float
    total_trades: int
    win_rate: float
    max_drawdown_pct: float
    status: str
    created_at: str
