"""Pydantic models shared between Python and Rust (via JSON over ZMQ)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SignalAction(str, Enum):
    buy = "buy"
    sell = "sell"
    closebuy = "closebuy"
    closesell = "closesell"
    closeall = "closeall"
    buylimit = "buylimit"
    selllimit = "selllimit"
    buystop = "buystop"
    sellstop = "sellstop"
    modify = "modify"
    breakeven = "breakeven"
    trailing = "trailing"
    cancel_buylimit = "cancel_buylimit"
    cancel_selllimit = "cancel_selllimit"


class PartialTPConfig(BaseModel):
    tp1_pips: float = 0
    tp1_percent: float = 50.0
    tp2_pips: float = 0
    tp2_percent: float = 30.0
    tp3_pips: float = 0
    tp3_percent: float = 100.0
    move_sl_to_be_on_tp1: bool = True
    trail_after_tp2: bool = False
    trail_distance_pips: float = 10.0


class TrailingConfig(BaseModel):
    enabled: bool = False
    activation_pips: float = 20.0
    distance_pips: float = 10.0
    step_pips: float = 1.0


class WebhookAlert(BaseModel):
    """Incoming alert from TradingView (or manual curl)."""

    token: str = ""
    action: SignalAction
    symbol: str
    lot: float = Field(default=0.01, ge=0.01)
    sl: float = 0
    tp: float = 0
    sl_pips: float = 0
    tp_pips: float = 0
    price: float = 0  # for pending orders
    comment: str = ""
    magic: int = 0
    partial_tp: Optional[PartialTPConfig] = None
    trailing: Optional[TrailingConfig] = None
    time_exit_minutes: int = 0
    risk_percent: float = 0


class ValidatedSignal(BaseModel):
    """Signal after risk checks, sent to Rust via ZMQ."""

    signal_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    action: SignalAction
    symbol: str  # mapped MT5 symbol
    tv_symbol: str = ""  # original TradingView symbol
    lot: float = 0.01
    sl: float = 0
    tp: float = 0
    sl_pips: float = 0
    tp_pips: float = 0
    price: float = 0
    comment: str = ""
    magic: int = 0
    partial_tp: Optional[PartialTPConfig] = None
    trailing: Optional[TrailingConfig] = None
    time_exit_minutes: int = 0
    risk_percent: float = 0
    dry_run: bool = False


class ExecutionCommand(BaseModel):
    """Rust sends to MT5 bridge."""

    command_id: str = Field(default_factory=lambda: f"cmd_{uuid.uuid4().hex[:12]}")
    signal_id: str = ""
    action: str = "place_order"  # place_order, close_order, modify_order
    symbol: str = ""
    order_type: str = ""  # market_buy, market_sell, buy_limit, etc.
    lot: float = 0.0
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    ticket: int = 0
    comment: str = ""
    magic: int = 0


class ExecutionResult(BaseModel):
    """MT5 bridge sends back to Python."""

    command_id: str = ""
    signal_id: str = ""
    success: bool = False
    ticket: int = 0
    executed_price: float = 0.0
    executed_lot: float = 0.0
    error_code: int = 0
    error_message: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class StateUpdate(BaseModel):
    """Rust publishes state changes to Python."""

    update_type: str = ""  # partial_tp, trailing, breakeven, time_exit, error
    signal_id: str = ""
    symbol: str = ""
    details: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "pineconnector"
    rust_engine: str = "unknown"  # connected, disconnected
    mt5_connected: bool = False
    zmq_connected: bool = False
    uptime_seconds: float = 0.0
    trades_today: int = 0
    dry_run: bool = False
