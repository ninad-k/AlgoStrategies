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

    # --- DIAGNOSTIC: log the parsed strategy to file ---
    import os
    _gen_diag = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_generator_diag.log")

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

    # Log what we got
    try:
        with open(_gen_diag, "w") as gf:
            gf.write(f"pinescript length: {len(req.pinescript) if req.pinescript else 0}\n")
            gf.write(f"pinescript FULL:\n{req.pinescript or ''}\n---END PINESCRIPT---\n")
            gf.write(f"strategy_def is None: {strategy_def is None}\n")
            if strategy_def:
                gf.write(f"entry_long: {strategy_def.get('entry_long', [])}\n")
                gf.write(f"entry_short: {strategy_def.get('entry_short', [])}\n")
                gf.write(f"exit_rules: {len(strategy_def.get('exit_rules', []))}\n")
                gf.write(f"indicators: {len(strategy_def.get('indicators', []))}\n")
                gf.write(f"inputs: {len(strategy_def.get('inputs', []))}\n")
                gf.write(f"variables keys: {list(strategy_def.get('variables', {}).keys())}\n")
                for _vk, _vv in strategy_def.get('variables', {}).items():
                    gf.write(f"  var {_vk} = {_vv}\n")
            gf.write(f"strategy_config present: {req.strategy_config is not None}\n")
            if req.strategy_config:
                gf.write(f"strategy_config keys: {list(req.strategy_config.keys())}\n")
                gf.write(f"strategy_config entry_long: {req.strategy_config.get('entry_long', [])}\n")
    except Exception:
        pass

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
