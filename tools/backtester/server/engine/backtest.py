import pandas as pd
import numpy as np
from typing import Any

from . import indicators as ind
from .position import PositionManager


INDICATOR_FUNCTIONS: dict[str, callable] = {
    "ema": ind.ema,
    "sma": ind.sma,
    "rsi": ind.rsi,
    "macd": ind.macd,
    "atr": ind.atr,
    "vwap": ind.vwap,
    "bollinger_bands": ind.bollinger_bands,
    "stochastic": ind.stochastic,
    "pivot_points": ind.pivot_points,
    "crossover": ind.crossover,
    "crossunder": ind.crossunder,
    "highest": ind.highest,
    "lowest": ind.lowest,
}

OHLCV_FIELDS = {"open", "high", "low", "close", "volume"}


_ARG_NAME_MAP = {
    "source": "series",
    "src": "series",
    "source1": "series_a",
    "source2": "series_b",
    "length": "period",
    "timeperiod": "period",
    "fast_length": "fast",
    "slow_length": "slow",
    "signal_length": "signal",
    "std_dev": "std_dev",
}


def _resolve_series_arg(key: str, df: pd.DataFrame, computed: dict[str, pd.Series]) -> pd.Series:
    if key in OHLCV_FIELDS:
        return df[key]
    if key in computed:
        return computed[key]
    raise ValueError(f"Unknown series reference: {key}")


def _resolve_input_value(val: Any, inputs: dict[str, Any]) -> Any:
    if isinstance(val, str) and val in inputs:
        return inputs[val]
    return val


def _compute_indicators(
    df: pd.DataFrame, indicator_defs: list[dict], inputs: dict[str, Any] = None
) -> dict[str, pd.Series]:
    computed: dict[str, pd.Series] = {}
    inputs = inputs or {}

    for ind_def in indicator_defs:
        name = ind_def["name"]
        var = ind_def["var"]
        raw_args = ind_def.get("args", {})
        func = INDICATOR_FUNCTIONS.get(name)
        if func is None:
            continue  # skip unknown indicators

        resolved_args: dict[str, Any] = {}
        for arg_name, arg_val in raw_args.items():
            mapped_name = _ARG_NAME_MAP.get(arg_name, arg_name)
            val = _resolve_input_value(arg_val, inputs)

            if isinstance(val, str) and (val in OHLCV_FIELDS or val in computed):
                resolved_args[mapped_name] = _resolve_series_arg(val, df, computed)
            elif isinstance(val, str) and val in inputs:
                resolved_args[mapped_name] = inputs[val]
            else:
                if isinstance(val, str):
                    try:
                        val = float(val)
                        if val == int(val):
                            val = int(val)
                    except ValueError:
                        pass
                resolved_args[mapped_name] = val

        # Special handling for indicators that need OHLCV but args don't specify
        if name == "atr" and "high" not in resolved_args:
            resolved_args = {"high": df["high"], "low": df["low"], "close": df["close"]}
            if "period" in raw_args:
                resolved_args["period"] = int(_resolve_input_value(raw_args["period"], inputs))
        elif name == "vwap" and "high" not in resolved_args:
            resolved_args = {"high": df["high"], "low": df["low"], "close": df["close"], "volume": df["volume"]}

        try:
            result = func(**resolved_args)
        except TypeError as e:
            continue  # skip indicators with unresolvable args

        if isinstance(result, dict):
            for sub_key, sub_series in result.items():
                computed[f"{var}_{sub_key}"] = sub_series
            computed[var] = next(iter(result.values()))
        else:
            computed[var] = result

    return computed


def _get_bar_values(
    df: pd.DataFrame, computed: dict[str, pd.Series], idx: int
) -> dict[str, float]:
    values: dict[str, float] = {}
    for col in OHLCV_FIELDS:
        values[col] = float(df[col].iat[idx])
    for key, series in computed.items():
        val = series.iat[idx]
        values[key] = float(val) if not pd.isna(val) else float("nan")
    return values


def _eval_condition(condition: str, values: dict[str, float], computed: dict[str, pd.Series], idx: int) -> bool:
    condition = condition.strip()

    if " and " in condition:
        parts = condition.split(" and ")
        return all(_eval_condition(p, values, computed, idx) for p in parts)

    if " or " in condition:
        parts = condition.split(" or ")
        return any(_eval_condition(p, values, computed, idx) for p in parts)

    if condition.startswith("not "):
        return not _eval_condition(condition[4:], values, computed, idx)

    if condition.startswith("crossover(") and condition.endswith(")"):
        inner = condition[10:-1]
        a_name, b_name = [s.strip() for s in inner.split(",")]
        a_series = computed.get(a_name)
        b_series = computed.get(b_name)
        if a_series is None or b_series is None:
            return False
        if idx < 1:
            return False
        prev_a = float(a_series.iat[idx - 1])
        prev_b = float(b_series.iat[idx - 1])
        curr_a = float(a_series.iat[idx])
        curr_b = float(b_series.iat[idx])
        return prev_a <= prev_b and curr_a > curr_b

    if condition.startswith("crossunder(") and condition.endswith(")"):
        inner = condition[11:-1]
        a_name, b_name = [s.strip() for s in inner.split(",")]
        a_series = computed.get(a_name)
        b_series = computed.get(b_name)
        if a_series is None or b_series is None:
            return False
        if idx < 1:
            return False
        prev_a = float(a_series.iat[idx - 1])
        prev_b = float(b_series.iat[idx - 1])
        curr_a = float(a_series.iat[idx])
        curr_b = float(b_series.iat[idx])
        return prev_a >= prev_b and curr_a < curr_b

    for op in [">=", "<=", "!=", ">", "<", "=="]:
        if op in condition:
            left_str, right_str = condition.split(op, 1)
            left_val = _resolve_value(left_str.strip(), values)
            right_val = _resolve_value(right_str.strip(), values)
            if np.isnan(left_val) or np.isnan(right_val):
                return False
            if op == ">":
                return left_val > right_val
            if op == "<":
                return left_val < right_val
            if op == ">=":
                return left_val >= right_val
            if op == "<=":
                return left_val <= right_val
            if op == "==":
                return left_val == right_val
            if op == "!=":
                return left_val != right_val

    val = values.get(condition)
    if val is not None:
        return bool(val)

    return False


def _resolve_value(token: str, values: dict[str, float]) -> float:
    if token in values:
        return values[token]
    try:
        return float(token)
    except ValueError:
        return float("nan")


def _evaluate_conditions(
    conditions: list,
    values: dict[str, float],
    computed: dict[str, pd.Series],
    idx: int,
) -> bool:
    if not conditions:
        return False
    for c in conditions:
        # conditions can be strings or dicts with a "condition" key
        cond_str = c.get("condition", "") if isinstance(c, dict) else str(c)
        if not cond_str:
            continue
        if not _eval_condition(cond_str, values, computed, idx):
            return False
    return True


def _get_exit_prices(
    exit_rules: list[dict], entry_price: float, direction: str
) -> tuple[float, float]:
    sl = 0.0
    tp = 0.0

    for rule in exit_rules:
        rule_type = rule.get("type", "")

        if rule_type == "sl":
            val = rule.get("value", 0)
            mode = rule.get("mode", "points")
            if mode == "percent":
                offset = entry_price * val / 100
            else:
                offset = val
            if direction == "long":
                sl = entry_price - offset
            else:
                sl = entry_price + offset

        elif rule_type == "tp":
            val = rule.get("value", 0)
            mode = rule.get("mode", "points")
            if mode == "percent":
                offset = entry_price * val / 100
            else:
                offset = val
            if direction == "long":
                tp = entry_price + offset
            else:
                tp = entry_price - offset

    return sl, tp


def run_backtest(df: pd.DataFrame, strategy_def: dict, settings: dict) -> dict:
    initial_capital = settings.get("initial_capital", 10000)
    commission_pct = settings.get("commission_pct", 0.0)
    slippage = settings.get("slippage_points", 0.0)
    symbol = settings.get("symbol", "UNKNOWN")

    indicator_defs = strategy_def.get("indicators", [])
    entry_long = strategy_def.get("entry_long", [])
    entry_short = strategy_def.get("entry_short", [])
    exit_rules = strategy_def.get("exit_rules", [])
    strat_settings = strategy_def.get("strategy_settings", strategy_def.get("settings", {}))
    initial_capital = strat_settings.get("initial_capital", initial_capital)
    commission_pct = strat_settings.get("commission_pct", commission_pct)

    # Build inputs dict from strategy input parameters
    inputs_dict: dict[str, Any] = {}
    for inp in strategy_def.get("inputs", []):
        inputs_dict[inp["name"]] = inp.get("default", 0)

    # Also add computed variables from the parser
    variables = strategy_def.get("variables", {})
    for var_name, var_expr in variables.items():
        if var_name not in inputs_dict:
            inputs_dict[var_name] = var_expr

    computed = _compute_indicators(df, indicator_defs, inputs_dict)
    pm = PositionManager(initial_capital)
    equity_curve: list[dict] = []
    n_bars = len(df)

    for i in range(n_bars):
        bar_time = str(df.index[i])
        high_val = float(df["high"].iat[i])
        low_val = float(df["low"].iat[i])
        close_val = float(df["close"].iat[i])

        values = _get_bar_values(df, computed, i)

        if pm.has_position:
            pm.update_mfe_mae(high_val, low_val)

            # Check SL/TP first
            closed_by_exit = pm.check_sl_tp(high_val, low_val, bar_time, commission_pct)

            # Check condition-based exits (strategy.close / strategy.close_all)
            if not closed_by_exit and pm.has_position:
                for rule in exit_rules:
                    rule_type = rule.get("type", "")
                    cond = rule.get("condition", "")
                    if rule_type in ("close", "close_all") and cond:
                        if _eval_condition(cond, values, computed, i):
                            comment = rule.get("comment", rule.get("id", "close"))
                            qty_pct = rule.get("qty_percent", 100)
                            if isinstance(qty_pct, str):
                                try:
                                    qty_pct = float(qty_pct)
                                except ValueError:
                                    qty_pct = 100
                            pm.close_position(bar_time, close_val, qty_pct / 100.0, commission_pct, str(comment))
                            if not pm.has_position:
                                break

        if not pm.has_position:
            if entry_long and _evaluate_conditions(entry_long, values, computed, i):
                entry_price = close_val + slippage
                sl, tp = _get_exit_prices(exit_rules, entry_price, "long")
                volume = 1.0
                pm.open_position(
                    bar_time, symbol, "long", volume, entry_price,
                    sl, tp, commission_pct, strategy_def.get("name", ""),
                )

            elif entry_short and _evaluate_conditions(entry_short, values, computed, i):
                entry_price = close_val - slippage
                sl, tp = _get_exit_prices(exit_rules, entry_price, "short")
                volume = 1.0
                pm.open_position(
                    bar_time, symbol, "short", volume, entry_price,
                    sl, tp, commission_pct, strategy_def.get("name", ""),
                )

        unrealized = 0.0
        if pm.has_position:
            pos = pm.current_position
            if pos.direction == "long":
                unrealized = (close_val - pos.entry_price) * pos.volume
            else:
                unrealized = (pos.entry_price - close_val) * pos.volume

        equity_curve.append(
            {
                "timestamp": bar_time,
                "balance": pm.balance,
                "equity": pm.balance + unrealized,
                "drawdown": 0.0,
            }
        )

    if pm.has_position:
        last_time = str(df.index[-1])
        last_close = float(df["close"].iat[-1])
        pm.close_position(last_time, last_close, 1.0, commission_pct, "end_of_data")

    peak = 0.0
    for point in equity_curve:
        eq = point["equity"]
        if eq > peak:
            peak = eq
        dd_pct = (peak - eq) / peak * 100 if peak > 0 else 0.0
        point["drawdown"] = peak - eq
        point["drawdown_pct"] = dd_pct

    orders_out = [
        {
            "order_num": o.order_num,
            "symbol": o.symbol,
            "type": o.type,
            "volume": o.volume,
            "price": o.price,
            "sl": o.sl,
            "tp": o.tp,
            "open_time": o.open_time,
            "state": o.state,
            "comment": o.comment,
        }
        for o in pm.all_orders
    ]

    deals_out = [
        {
            "deal_num": d.deal_num,
            "order_num": d.order_num,
            "time": d.time,
            "symbol": d.symbol,
            "type": d.type,
            "direction": d.direction,
            "volume": d.volume,
            "price": d.price,
            "commission": d.commission,
            "swap": d.swap,
            "profit": d.profit,
            "balance": d.balance,
            "comment": d.comment,
        }
        for d in pm.all_deals
    ]

    return {
        "orders": orders_out,
        "deals": deals_out,
        "trades": pm.closed_trades,
        "equity_curve": equity_curve,
        "bars": n_bars,
    }
