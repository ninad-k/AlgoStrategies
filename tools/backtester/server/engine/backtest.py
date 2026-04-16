from __future__ import annotations

import logging
import pandas as pd
import numpy as np
from typing import Any

from . import indicators as ind
from .position import PositionManager

log = logging.getLogger(__name__)


INDICATOR_FUNCTIONS: dict[str, callable] = {
    "ema": ind.ema,
    "sma": ind.sma,
    "rsi": ind.rsi,
    "macd": ind.macd,
    "atr": ind.atr,
    "vwap": ind.vwap,
    "bollinger_bands": ind.bollinger_bands,
    "bb": ind.bollinger_bands,
    "stochastic": ind.stochastic,
    "stoch": ind.stochastic,
    "pivot_points": ind.pivot_points,
    "crossover": ind.crossover,
    "crossunder": ind.crossunder,
    "highest": ind.highest,
    "lowest": ind.lowest,
    "adx": ind.adx,
    "dmi": ind.dmi,
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


def _resolve_series_arg(key, df, computed):
    if key in OHLCV_FIELDS:
        return df[key]
    if key in computed:
        return computed[key]
    raise ValueError(f"Unknown series reference: {key}")


def _resolve_input_value(val, inputs):
    if isinstance(val, str) and val in inputs:
        return inputs[val]
    return val


def _compute_indicators(df, indicator_defs, inputs=None):
    computed = {}
    inputs = inputs or {}

    for ind_def in indicator_defs:
        name = ind_def["name"]
        var = ind_def["var"]
        raw_args = ind_def.get("args", {})

        if name == "supertrend":
            factor = float(_resolve_input_value(raw_args.get("factor", raw_args.get("arg0", 3)), inputs))
            p = int(_resolve_input_value(raw_args.get("atr_period", raw_args.get("arg1", 10)), inputs))
            try:
                out = ind.supertrend(df["high"], df["low"], df["close"], p, factor)
                computed[var] = out["supertrend"]
                dv = ind_def.get("direction_var")
                if dv:
                    computed[dv] = out["direction"]
            except (TypeError, ValueError, KeyError):
                pass
            continue

        if name in ("bb", "bollinger_bands"):
            source_key = str(_resolve_input_value(
                raw_args.get("source", raw_args.get("arg0", "close")), inputs
            )).strip().strip('"')
            p = int(_resolve_input_value(
                raw_args.get("length", raw_args.get("period", raw_args.get("arg1", 20))), inputs
            ))
            sd = float(_resolve_input_value(
                raw_args.get("std_dev", raw_args.get("mult", raw_args.get("arg2", 2.0))), inputs
            ))
            series = df[source_key] if source_key in OHLCV_FIELDS else computed.get(source_key, df["close"])
            try:
                out = ind.bollinger_bands(series, p, sd)
                computed[var] = out["upper"]
                for sub_key, sub_series in out.items():
                    computed[f"{var}_{sub_key}"] = sub_series
                dnames = ind_def.get("destruct_names", [])
                sub_keys = list(out.keys())
                for di, dname in enumerate(dnames):
                    if di < len(sub_keys):
                        computed[dname] = out[sub_keys[di]]
            except (TypeError, ValueError, KeyError):
                pass
            continue

        if name in ("adx", "dmi"):
            p = int(_resolve_input_value(raw_args.get("period", raw_args.get("arg0", 14)), inputs))
            smoothing = int(_resolve_input_value(raw_args.get("smoothing", raw_args.get("arg1", p)), inputs))

            def _ser(key, default_ohlc):
                k = str(raw_args.get(key, default_ohlc)).strip().strip('"')
                if k in OHLCV_FIELDS:
                    return df[k]
                if k in computed:
                    return computed[k]
                return df[default_ohlc]

            try:
                if name == "dmi":
                    out = ind.dmi(_ser("high", "high"), _ser("low", "low"), _ser("close", "close"), p, smoothing)
                    computed[var] = out["plus"]
                    computed[f"{var}_plus"] = out["plus"]
                    computed[f"{var}_minus"] = out["minus"]
                    computed[f"{var}_adx"] = out["adx"]
                    dnames = ind_def.get("destruct_names", [])
                    sub_keys = ["plus", "minus", "adx"]
                    for di, dname in enumerate(dnames):
                        if di < len(sub_keys):
                            computed[dname] = out[sub_keys[di]]
                else:
                    computed[var] = ind.adx(_ser("high", "high"), _ser("low", "low"), _ser("close", "close"), p)
            except (TypeError, ValueError, KeyError):
                pass
            continue

        func = INDICATOR_FUNCTIONS.get(name)
        if func is None:
            continue

        resolved_args = {}
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

        if name == "atr" and "high" not in resolved_args:
            resolved_args = {"high": df["high"], "low": df["low"], "close": df["close"]}
            if "period" in raw_args:
                resolved_args["period"] = int(_resolve_input_value(raw_args["period"], inputs))
        elif name == "vwap" and "high" not in resolved_args:
            resolved_args = {"high": df["high"], "low": df["low"], "close": df["close"], "volume": df["volume"]}

        # Safety: if any expected series arg remains a raw string we cannot
        # resolve (complex expression or unknown symbol), skip this indicator
        # rather than crash the whole backtest.
        _skip = False
        for _k, _v in resolved_args.items():
            if isinstance(_v, str):
                _skip = True
                break
        if _skip:
            continue

        try:
            result = func(**resolved_args)
        except (TypeError, AttributeError, ValueError):
            continue

        if isinstance(result, dict):
            sub_keys = list(result.keys())
            for sub_key, sub_series in result.items():
                computed[f"{var}_{sub_key}"] = sub_series
            computed[var] = next(iter(result.values()))
            dnames = ind_def.get("destruct_names", [])
            for di, dname in enumerate(dnames):
                if di < len(sub_keys) and dname != var:
                    computed[dname] = result[sub_keys[di]]
        else:
            computed[var] = result

    return computed


def _get_bar_values(df, computed, idx):
    values = {}
    for col in OHLCV_FIELDS:
        values[col] = float(df[col].iat[idx])
    for key, series in computed.items():
        val = series.iat[idx]
        values[key] = float(val) if not pd.isna(val) else float("nan")
    return values


def _eval_condition(condition, values, computed, idx, variables=None):
    condition = condition.strip()
    if not condition or condition == "na":
        return False

    if condition == "true":
        return True
    if condition == "false":
        return False

    # Strip wrapping parentheses
    while condition.startswith("(") and condition.endswith(")"):
        depth = 0
        matched = True
        for i, ch in enumerate(condition):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(condition) - 1:
                matched = False
                break
        if matched:
            condition = condition[1:-1].strip()
        else:
            break

    # Ternary: cond ? true_val : false_val
    ternary = _find_ternary(condition)
    if ternary is not None:
        cond_part, true_val, false_val = ternary
        if _eval_condition(cond_part, values, computed, idx, variables):
            return _eval_condition(true_val, values, computed, idx, variables)
        else:
            return _eval_condition(false_val, values, computed, idx, variables)

    # Split on 'or' first (lower precedence) so 'and' groups bind tighter,
    # matching PineScript/Python operator precedence.
    or_parts = _split_logic(condition, " or ")
    if or_parts is not None:
        return any(_eval_condition(p, values, computed, idx, variables) for p in or_parts)

    and_parts = _split_logic(condition, " and ")
    if and_parts is not None:
        return all(_eval_condition(p, values, computed, idx, variables) for p in and_parts)

    # na(x) / not na(x) — PineScript null/NaN check
    if condition.startswith("na(") and condition.endswith(")"):
        inner = condition[3:-1].strip()
        v = values.get(inner)
        if v is None:
            return True  # missing → is na
        return np.isnan(v) if isinstance(v, float) else False

    if condition.startswith("not "):
        return not _eval_condition(condition[4:], values, computed, idx, variables)

    if condition.startswith("crossover(") and condition.endswith(")"):
        inner = condition[10:-1]
        a_name, b_name = [s.strip() for s in inner.split(",", 1)]
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
        if np.isnan(prev_a) or np.isnan(prev_b) or np.isnan(curr_a) or np.isnan(curr_b):
            return False
        return prev_a <= prev_b and curr_a > curr_b

    if condition.startswith("crossunder(") and condition.endswith(")"):
        inner = condition[11:-1]
        a_name, b_name = [s.strip() for s in inner.split(",", 1)]
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
        if np.isnan(prev_a) or np.isnan(prev_b) or np.isnan(curr_a) or np.isnan(curr_b):
            return False
        return prev_a >= prev_b and curr_a < curr_b

    for op in [">=", "<=", "!=", ">", "<", "=="]:
        pos = _find_operator(condition, op)
        if pos >= 0:
            left_str = condition[:pos].strip()
            right_str = condition[pos + len(op):].strip()
            left_val = _resolve_value(left_str, values, variables)
            right_val = _resolve_value(right_str, values, variables)
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
        if np.isnan(val):
            return False
        return bool(val)

    if variables and condition in variables:
        expr = variables[condition]
        if isinstance(expr, str) and expr != condition:
            return _eval_condition(expr, values, computed, idx, variables)

    return False


def _find_ternary(condition):
    paren_depth = 0
    q_pos = -1
    for i, ch in enumerate(condition):
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
        elif ch == "?" and paren_depth == 0:
            q_pos = i
            break
    if q_pos < 0:
        return None
    cond_part = condition[:q_pos].strip()
    rest = condition[q_pos + 1:]
    # Find the matching ':' accounting for nested ternaries.
    # Each '?' opens a nested ternary; the matching ':' closes it.
    paren_depth = 0
    ternary_depth = 0
    for i, ch in enumerate(rest):
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
        elif ch == "?" and paren_depth == 0:
            ternary_depth += 1
        elif ch == ":" and paren_depth == 0:
            if ternary_depth == 0:
                true_val = rest[:i].strip()
                false_val = rest[i + 1:].strip()
                return (cond_part, true_val, false_val)
            else:
                ternary_depth -= 1
    return None


def _split_logic(condition, sep):
    depth = 0
    parts = []
    start = 0
    i = 0
    while i < len(condition):
        ch = condition[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and condition[i:i + len(sep)] == sep:
            parts.append(condition[start:i].strip())
            i += len(sep)
            start = i
            continue
        i += 1
    if parts:
        parts.append(condition[start:].strip())
        return parts
    return None


def _find_operator(condition, op):
    depth = 0
    for i, ch in enumerate(condition):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and condition[i:i + len(op)] == op:
            if op == ">" and i + 1 < len(condition) and condition[i + 1] == "=":
                continue
            if op == "<" and i + 1 < len(condition) and condition[i + 1] == "=":
                continue
            if op == "!" and i + 1 < len(condition) and condition[i + 1] == "=":
                continue
            if op == "=" and i > 0 and condition[i - 1] in ("!", ">", "<", "="):
                continue
            return i
    return -1


def _resolve_value(token, values, variables=None):
    if token in values:
        return values[token]
    try:
        return float(token)
    except ValueError:
        pass
    if token == "true":
        return 1.0
    if token == "false":
        return 0.0
    if variables and token in variables:
        expr = variables[token]
        if isinstance(expr, str) and expr != token:
            result = _try_resolve_numeric(expr, values)
            if result is not None:
                return result
    result = _try_resolve_numeric(token, values)
    if result is not None:
        return result
    return float("nan")


def _evaluate_conditions(conditions, values, computed, idx, variables=None):
    if not conditions:
        return False
    has_nonempty = False
    for c in conditions:
        cond_str = c.get("condition", "") if isinstance(c, dict) else str(c)
        if not cond_str:
            continue
        has_nonempty = True
        if not _eval_condition(cond_str, values, computed, idx, variables):
            return False
    return has_nonempty


def _evaluate_conditions_any(conditions, values, computed, idx, variables=None):
    if not conditions:
        return False
    for c in conditions:
        cond_str = c.get("condition", "") if isinstance(c, dict) else str(c)
        if not cond_str:
            continue
        if _eval_condition(cond_str, values, computed, idx, variables):
            return True
    return False


def _get_exit_prices(exit_rules, entry_price, direction, values=None):
    sl = 0.0
    tp = 0.0
    values = values or {}
    for rule in exit_rules:
        rule_type = rule.get("type", "")
        if rule_type == "sl":
            val = rule.get("value", 0)
            mode = rule.get("mode", "points")
            offset = entry_price * val / 100 if mode == "percent" else val
            sl = entry_price - offset if direction == "long" else entry_price + offset
        elif rule_type == "tp":
            val = rule.get("value", 0)
            mode = rule.get("mode", "points")
            offset = entry_price * val / 100 if mode == "percent" else val
            tp = entry_price + offset if direction == "long" else entry_price - offset
        elif rule_type == "exit":
            stop_val = _try_resolve_numeric(rule.get("stop"), values)
            if stop_val and stop_val > 0:
                sl = stop_val
            limit_val = _try_resolve_numeric(rule.get("limit"), values)
            if limit_val and limit_val > 0:
                tp = limit_val
            loss_val = _try_resolve_numeric(rule.get("loss"), values)
            if loss_val and loss_val > 0 and sl == 0:
                sl = entry_price - loss_val if direction == "long" else entry_price + loss_val
            profit_val = _try_resolve_numeric(rule.get("profit"), values)
            if profit_val and profit_val > 0 and tp == 0:
                tp = entry_price + profit_val if direction == "long" else entry_price - profit_val
    return sl, tp


def _try_resolve_numeric(val, values=None):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        try:
            return float(val)
        except ValueError:
            pass
        if values and val in values:
            v = values[val]
            if not np.isnan(v):
                return v
        # math.abs(x) / abs(x)
        if (val.startswith("math.abs(") or val.startswith("abs(")) and val.endswith(")"):
            inner_start = val.index("(") + 1
            inner = val[inner_start:-1].strip()
            inner_val = _try_resolve_numeric(inner, values)
            if inner_val is not None:
                return abs(inner_val)
        # math.max(a,b) / math.min(a,b)
        for fn in ("math.max(", "max(", "math.min(", "min("):
            if val.startswith(fn) and val.endswith(")"):
                inner = val[len(fn):-1]
                parts = inner.split(",", 1)
                if len(parts) == 2:
                    a = _try_resolve_numeric(parts[0].strip(), values)
                    b = _try_resolve_numeric(parts[1].strip(), values)
                    if a is not None and b is not None:
                        return max(a, b) if "max" in fn else min(a, b)
        for op_char in ["*", "+", "-", "/"]:
            if op_char in val:
                parts = val.split(op_char, 1)
                left = _try_resolve_numeric(parts[0].strip(), values)
                right = _try_resolve_numeric(parts[1].strip(), values)
                if left is not None and right is not None:
                    if op_char == "*":
                        return left * right
                    if op_char == "+":
                        return left + right
                    if op_char == "-":
                        return left - right
                    if op_char == "/" and right != 0:
                        return left / right
    return None


def _resolve_bar_variables(values, variables, inputs):
    for name, val in inputs.items():
        if name in values:
            continue
        if isinstance(val, bool):
            values[name] = 1.0 if val else 0.0
        elif isinstance(val, (int, float)):
            values[name] = float(val)
    # Iteratively resolve variable expressions. Handles both numeric
    # (volRatio = volume / volSma) and boolean (trendUp = emaFast > emaSlow)
    # expressions, plus ternaries via _eval_condition.
    for _ in range(6):
        resolved_any = False
        for var_name, var_expr in variables.items():
            if var_name in values:
                continue
            if not isinstance(var_expr, str):
                continue
            expr = var_expr.strip()
            # Try numeric first (handles arithmetic like volume / volSma)
            result = _try_resolve_numeric(expr, values)
            if result is not None:
                values[var_name] = result
                resolved_any = True
                continue
            # Try boolean evaluation for comparisons, logical ops, ternaries.
            # Only accept the result if evaluation succeeded without raising
            # and the expression actually contains boolean indicators.
            has_bool_token = any(
                tok in expr
                for tok in (" and ", " or ", " not ", ">", "<", "==", "!=", "?", "true", "false")
            )
            if has_bool_token:
                try:
                    bres = _eval_condition(expr, values, {}, 0, variables)
                    if isinstance(bres, bool):
                        values[var_name] = 1.0 if bres else 0.0
                        resolved_any = True
                        continue
                except Exception:
                    pass
        if not resolved_any:
            break


def run_backtest(df, strategy_def, settings):
    # --- DIAGNOSTIC LOG (written to file to verify code version) ---
    _diag_path = None
    try:
        import os, datetime
        _diag_dir = os.path.dirname(os.path.abspath(__file__))
        _diag_path = os.path.join(_diag_dir, "_backtest_diag.log")
        with open(_diag_path, "w") as _df:
            _df.write(f"run_backtest called at {datetime.datetime.now()}\n")
            _df.write(f"CODE VERSION: v7-full-fix\n")
            _df.write(f"df shape: {df.shape}\n")
            _df.write(f"strategy keys: {list(strategy_def.keys())}\n")
            _df.write(f"entry_long: {strategy_def.get('entry_long', [])}\n")
            _df.write(f"entry_short: {strategy_def.get('entry_short', [])}\n")
            _df.write(f"exit_rules count: {len(strategy_def.get('exit_rules', []))}\n")
            _df.write(f"indicators count: {len(strategy_def.get('indicators', []))}\n")
            _df.write(f"variables: {list(strategy_def.get('variables', {}).keys())}\n")
            _df.write(f"inputs count: {len(strategy_def.get('inputs', []))}\n")
    except Exception:
        pass
    # --- END DIAGNOSTIC ---

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

    inputs_dict = {}
    for inp in strategy_def.get("inputs", []):
        inputs_dict[inp["name"]] = inp.get("default", 0)

    variables = strategy_def.get("variables", {})
    # If sessionOK was not parsed (na/time not supported), default to true
    if "sessionOK" not in variables:
        for vn, ve in variables.items():
            if "sessionOK" in str(ve) and vn not in variables:
                pass
        # Check if any variable references sessionOK but it is missing
        for vn, ve in list(variables.items()):
            if isinstance(ve, str) and "sessionOK" in ve and "sessionOK" not in variables:
                variables["sessionOK"] = "true"
                break
        if "sessionOK" not in variables:
            # Check if filteredBuy/filteredSell reference it
            for vn, ve in variables.items():
                if isinstance(ve, str) and "sessionOK" in ve:
                    variables["sessionOK"] = "true"
                    break
    for var_name, var_expr in variables.items():
        if var_name not in inputs_dict:
            inputs_dict[var_name] = var_expr

    computed = _compute_indicators(df, indicator_defs, inputs_dict)

    # --- Pre-compute simplified support/resistance from rolling pivot data ---
    # This approximates fibonacci levels for strategies using request.security()
    # and array-based level computation that the engine cannot replicate.
    # Compute multiple fib levels and at each bar pick nearest below/above close.
    _pivot_lookback = int(inputs_dict.get("h22Lookback", 30))
    _rolling_high = df["high"].rolling(window=_pivot_lookback, min_periods=1).max()
    _rolling_low = df["low"].rolling(window=_pivot_lookback, min_periods=1).min()
    _fib_levels = [0.236, 0.382, 0.44, 0.50, 0.618, 0.786]
    _rng = _rolling_high - _rolling_low
    # Generate all fib retracement levels from rolling range
    _all_levels = []
    for fl in _fib_levels:
        _all_levels.append(_rolling_high - fl * _rng)  # retracement from high
    # At each bar, find nearest level below close (support) and above (resistance)
    _near_sup = pd.Series(np.nan, index=df.index)
    _near_res = pd.Series(np.nan, index=df.index)
    _next_sup = pd.Series(np.nan, index=df.index)
    _next_res = pd.Series(np.nan, index=df.index)
    for i_bar in range(len(df)):
        c = df["close"].iat[i_bar]
        sups = []
        ress = []
        for lvl_series in _all_levels:
            v = lvl_series.iat[i_bar]
            if pd.isna(v):
                continue
            if v <= c:
                sups.append(v)
            else:
                ress.append(v)
        sups.sort(reverse=True)  # nearest support first (highest below close)
        ress.sort()              # nearest resistance first (lowest above close)
        if sups:
            _near_sup.iat[i_bar] = sups[0]
        if len(sups) > 1:
            _next_sup.iat[i_bar] = sups[1]
        if ress:
            _near_res.iat[i_bar] = ress[0]
        if len(ress) > 1:
            _next_res.iat[i_bar] = ress[1]

    pm = PositionManager(initial_capital)
    equity_curve = []
    n_bars = len(df)
    leverage = max(float(settings.get("leverage", 1) or 1), 1e-9)
    bars_since_exit = 999  # Cooldown counter

    for i in range(n_bars):
        bar_time = str(df.index[i])
        high_val = float(df["high"].iat[i])
        low_val = float(df["low"].iat[i])
        close_val = float(df["close"].iat[i])

        values = _get_bar_values(df, computed, i)
        values["strategy.position_size"] = pm.position_size
        values["strategy.position_avg_price"] = pm.current_position.entry_price if pm.has_position else 0.0

        # Extract hour/minute from bar timestamp for session-based logic
        try:
            ts = df.index[i]
            if hasattr(ts, "hour"):
                values["utcHr"] = float(ts.hour)
                values["utcMn"] = float(ts.minute)
        except Exception:
            pass

        # Inject simplified support/resistance if not already resolved
        if "nearSup" not in values or np.isnan(values.get("nearSup", float("nan"))):
            ns = float(_sup1.iat[i]) if not pd.isna(_sup1.iat[i]) else float("nan")
            values["nearSup"] = ns
        if "nearRes" not in values or np.isnan(values.get("nearRes", float("nan"))):
            nr = float(_res2.iat[i]) if not pd.isna(_res2.iat[i]) else float("nan")
            values["nearRes"] = nr
        if "nextSup" not in values or np.isnan(values.get("nextSup", float("nan"))):
            ns2 = float(_sup2.iat[i]) if not pd.isna(_sup2.iat[i]) else float("nan")
            values["nextSup"] = ns2
        if "nextRes" not in values or np.isnan(values.get("nextRes", float("nan"))):
            nr2 = float(_res1.iat[i]) if not pd.isna(_res1.iat[i]) else float("nan")
            values["nextRes"] = nr2

        # Inject barsSinceExit for cooldown tracking
        values["barsSinceExit"] = float(bars_since_exit)

        # Inject default confluence counts (can't compute array-based overlap)
        if "nearSupC" not in values:
            values["nearSupC"] = 1.0
        if "nearResC" not in values:
            values["nearResC"] = 1.0

        _resolve_bar_variables(values, variables, inputs_dict)

        _was_in_position = pm.has_position
        if pm.has_position:
            pm.update_mfe_mae(high_val, low_val)
            closed_by_exit = pm.check_sl_tp(high_val, low_val, bar_time, commission_pct)
            if closed_by_exit:
                bars_since_exit = 0

            if not closed_by_exit and pm.has_position:
                for rule in exit_rules:
                    rule_type = rule.get("type", "")
                    cond = rule.get("condition", "")
                    if rule_type in ("close", "close_all") and cond:
                        if _eval_condition(cond, values, computed, i, variables):
                            comment = rule.get("comment", rule.get("id", "close"))
                            qty_pct = rule.get("qty_percent", 100)
                            if isinstance(qty_pct, str):
                                try:
                                    qty_pct = float(qty_pct)
                                except ValueError:
                                    qty_pct = 100
                            pm.close_position(bar_time, close_val, qty_pct / 100.0, commission_pct, str(comment))
                            if not pm.has_position:
                                bars_since_exit = 0
                                break
                    elif rule_type == "exit" and cond:
                        if _eval_condition(cond, values, computed, i, variables):
                            comment = rule.get("comment", rule.get("id", "exit"))
                            qty_pct = rule.get("qty_percent", 100)
                            if isinstance(qty_pct, str):
                                try:
                                    qty_pct = float(qty_pct)
                                except ValueError:
                                    qty_pct = 100
                            pm.close_position(bar_time, close_val, qty_pct / 100.0, commission_pct, str(comment))
                            if not pm.has_position:
                                bars_since_exit = 0
                                break

        if not pm.has_position:
            long_hit = entry_long and _evaluate_conditions_any(entry_long, values, computed, i, variables)
            if long_hit:
                log.debug("BAR %d %s LONG entry triggered", i, bar_time)
                entry_price = close_val + slippage
                sl, tp = _get_exit_prices(exit_rules, entry_price, "long", values)
                volume = 1.0
                pm.open_position(
                    bar_time, symbol, "long", volume, entry_price,
                    sl, tp, commission_pct, strategy_def.get("name", ""),
                )
            elif not long_hit and entry_short and _evaluate_conditions_any(entry_short, values, computed, i, variables):
                log.debug("BAR %d %s SHORT entry triggered", i, bar_time)
                entry_price = close_val - slippage
                sl, tp = _get_exit_prices(exit_rules, entry_price, "short", values)
                volume = 1.0
                pm.open_position(
                    bar_time, symbol, "short", volume, entry_price,
                    sl, tp, commission_pct, strategy_def.get("name", ""),
                )

        unrealized = 0.0
        pos = pm.current_position if pm.has_position else None
        if pos is not None:
            if pos.direction == "long":
                unrealized = (close_val - pos.entry_price) * pos.volume
            else:
                unrealized = (pos.entry_price - close_val) * pos.volume

        eq = pm.balance + unrealized
        deposit_load = 0.0
        if pos is not None:
            notional = abs(pos.volume * close_val)
            margin_used = notional / leverage
            deposit_load = min(100.0, (margin_used / eq * 100.0) if eq > 1e-9 else 0.0)

        equity_curve.append({
            "timestamp": bar_time,
            "balance": pm.balance,
            "equity": eq,
            "drawdown": 0.0,
            "deposit_load": deposit_load,
        })

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

    orders_out = [{
        "order_num": o.order_num, "symbol": o.symbol, "type": o.type,
        "volume": o.volume, "price": o.price, "sl": o.sl, "tp": o.tp,
        "open_time": o.open_time, "state": o.state, "comment": o.comment,
    } for o in pm.all_orders]

    deals_out = [{
        "deal_num": d.deal_num, "order_num": d.order_num, "time": d.time,
        "symbol": d.symbol, "type": d.type, "direction": d.direction,
        "volume": d.volume, "price": d.price, "commission": d.commission,
        "swap": d.swap, "profit": d.profit, "balance": d.balance, "comment": d.comment,
    } for d in pm.all_deals]

    # --- DIAGNOSTIC LOG APPEND ---
    if _diag_path:
        try:
            import datetime
            with open(_diag_path, "a") as _df:
                _df.write("\n--- RESULTS at {} ---\n".format(datetime.datetime.now()))
                _df.write("n_bars: {}\n".format(n_bars))
                _df.write("orders: {}\n".format(len(orders_out)))
                _df.write("deals: {}\n".format(len(deals_out)))
                _df.write("trades: {}\n".format(len(pm.closed_trades)))
                _df.write("computed keys: {}\n".format(sorted(computed.keys())))
                mid = n_bars // 2
                vals = _get_bar_values(df, computed, mid)
                vals["strategy.position_size"] = 0.0
                vals["barsSinceExit"] = 999.0
                _resolve_bar_variables(vals, variables, inputs_dict)
                for k in ["close", "ema50", "ema200", "bullishTrend", "bearishTrend", "nearSup", "nearRes", "nearSupport", "nearResistance", "buyEntry", "sellEntry", "stBullish", "barsSinceExit", "bullCandle"]:
                    _df.write("  BAR[{}] {} = {}\n".format(mid, k, vals.get(k, 'MISSING')))
        except Exception:
            pass
    # --- END DIAGNOSTIC ---

    return {
        "orders": orders_out,
        "deals": deals_out,
        "trades": pm.closed_trades,
        "equity_curve": equity_curve,
        "bars": n_bars,
    }
