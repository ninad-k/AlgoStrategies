"""Assembles the full MQL5-style backtest report."""

from __future__ import annotations

import json
import logging

import pandas as pd

from .. import database as db
from ..engine.metrics import compute_metrics

log = logging.getLogger(__name__)


def generate_report(bt_id: int, req, df: pd.DataFrame) -> dict:
    from ..parser import parse_pinescript
    from ..engine.backtest import run_backtest

    # Parse strategy
    strategy_def = None
    if req.pinescript and req.pinescript.strip():
        try:
            strategy_def = parse_pinescript(req.pinescript)
            strategy_name = strategy_def.get("strategy_name", "")
        except Exception as e:
            log.warning("Parse failed, using strategy_config: %s", e)
            strategy_def = None
            strategy_name = ""

    if strategy_def is None and req.strategy_config:
        strategy_def = req.strategy_config
        strategy_name = strategy_def.get("strategy_name", req.name)
    elif strategy_def is None:
        raise ValueError("No valid strategy provided (PineScript parse failed and no strategy_config)")

    # Apply input overrides
    if req.input_overrides:
        inputs = strategy_def.get("inputs", [])
        for inp in inputs:
            name = inp.get("name", "")
            if name in req.input_overrides:
                inp["default"] = req.input_overrides[name]

    # Update backtest record with strategy name
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE backtests SET strategy_name=?, strategy_config=? WHERE id=?",
            (strategy_name, json.dumps(strategy_def), bt_id),
        )

    db.update_backtest_status(bt_id, "running", 50, "Running backtest simulation...")

    # Run backtest
    settings = {
        "initial_capital": req.initial_capital,
        "leverage": req.leverage,
        "commission_pct": req.commission_pct,
        "slippage_points": req.slippage_points,
        "symbol": req.symbol,
    }

    result = run_backtest(df, strategy_def, settings)

    db.update_backtest_status(bt_id, "running", 80, "Computing metrics...")

    # Compute metrics
    metrics = compute_metrics(
        result["trades"],
        result["equity_curve"],
        req.initial_capital,
        result.get("bars", len(df)),
    )

    db.update_backtest_status(bt_id, "running", 90, "Saving results...")

    # Save to database
    db.save_trades(bt_id, result["trades"])
    db.save_orders(bt_id, result["orders"])
    db.save_deals(bt_id, result["deals"])
    db.save_equity_curve(bt_id, result["equity_curve"])
    db.save_metrics(bt_id, metrics)

    return {
        "metrics": metrics,
        "trades": result["trades"],
        "orders": result["orders"],
        "deals": result["deals"],
        "equity_curve": result["equity_curve"],
    }
