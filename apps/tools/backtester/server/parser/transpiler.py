"""Transpiler: walks the PineScript AST and produces a strategy definition dict.

The output dict is designed to be consumed by the backtesting engine and
matches the ParseResult / InputParam schemas from models.py.
"""

from __future__ import annotations

from typing import Any

from .lexer import tokenize
from .parser import PineScriptParser
from .ast_nodes import (
    BinaryOp,
    BoolLit,
    DestructAssign,
    Expr,
    FuncCall,
    Identifier,
    IfBlock,
    IndexAccess,
    InputDecl,
    NumberLit,
    PlotCall,
    ReassignStatement,
    SecurityCall,
    StrategyCall,
    StrategyDecl,
    StringLit,
    SwitchBlock,
    Ternary,
    UnaryOp,
    VarAssign,
)

# Mapping from ta.* function names to human-readable indicator names
_INDICATOR_NAMES: dict[str, str] = {
    "ta.ema": "EMA",
    "ta.sma": "SMA",
    "ta.rsi": "RSI",
    "ta.macd": "MACD",
    "ta.atr": "ATR",
    "ta.vwap": "VWAP",
    "ta.wma": "WMA",
    "ta.hma": "HMA",
    "ta.rma": "RMA",
    "ta.stoch": "Stochastic",
    "ta.bb": "Bollinger Bands",
    "ta.cci": "CCI",
    "ta.mfi": "MFI",
    "ta.obv": "OBV",
    "ta.adx": "ADX",
    "ta.supertrend": "SuperTrend",
    "ta.pivothigh": "Pivot High",
    "ta.pivotlow": "Pivot Low",
    "ta.crossover": "Crossover",
    "ta.crossunder": "Crossunder",
    "ta.highest": "Highest",
    "ta.lowest": "Lowest",
    "ta.tr": "True Range",
    "ta.change": "Change",
    "ta.cum": "Cumulative",
    "ta.valuewhen": "Value When",
    "ta.barssince": "Bars Since",
}


def expr_to_str(expr: Any) -> str:
    """Convert an AST expression to a human-readable / evaluable string."""
    if expr is None:
        return "na"
    if isinstance(expr, NumberLit):
        v = expr.value
        return str(int(v)) if v == int(v) else str(v)
    if isinstance(expr, StringLit):
        return f'"{expr.value}"'
    if isinstance(expr, BoolLit):
        return "true" if expr.value else "false"
    if isinstance(expr, Identifier):
        return expr.name
    if isinstance(expr, BinaryOp):
        left = expr_to_str(expr.left)
        right = expr_to_str(expr.right)
        # Add parens for clarity on nested binary ops
        if isinstance(expr.left, BinaryOp) and _prec(expr.left.op) < _prec(expr.op):
            left = f"({left})"
        if isinstance(expr.right, BinaryOp) and _prec(expr.right.op) <= _prec(expr.op):
            right = f"({right})"
        return f"{left} {expr.op} {right}"
    if isinstance(expr, UnaryOp):
        operand = expr_to_str(expr.operand)
        if expr.op == "-":
            return f"-{operand}"
        return f"{expr.op} {operand}"
    if isinstance(expr, FuncCall):
        # Simplify well-known function names for the engine
        short_name = _shorten_func(expr.name)
        parts: list[str] = [expr_to_str(a) for a in expr.args]
        parts.extend(f"{k}={expr_to_str(v)}" for k, v in expr.kwargs.items())
        return f"{short_name}({', '.join(parts)})"
    if isinstance(expr, IndexAccess):
        return f"{expr_to_str(expr.expr)}[{expr_to_str(expr.index)}]"
    if isinstance(expr, Ternary):
        cond = expr_to_str(expr.condition)
        tv = expr_to_str(expr.true_val)
        fv = expr_to_str(expr.false_val)
        return f"{cond} ? {tv} : {fv}"
    if isinstance(expr, SwitchBlock):
        parts_list = ["switch"]
        if expr.expr is not None:
            parts_list[0] = f"switch {expr_to_str(expr.expr)}"
        for match_val, body in expr.cases:
            body_str = expr_to_str(body[0]) if body else "na"
            parts_list.append(f"  {expr_to_str(match_val)} => {body_str}")
        if expr.default:
            parts_list.append(f"  => {expr_to_str(expr.default[0])}")
        return " | ".join(parts_list)
    return str(expr)


def _prec(op: str) -> int:
    """Return precedence level of a binary operator."""
    return {
        "or": 1, "and": 2,
        "==": 3, "!=": 3, ">": 3, "<": 3, ">=": 3, "<=": 3,
        "+": 4, "-": 4,
        "*": 5, "/": 5,
    }.get(op, 0)


def _shorten_func(name: str) -> str:
    """Shorten ta.crossover -> crossover, math.max -> max, etc."""
    if name.startswith("ta."):
        return name[3:]
    if name.startswith("math."):
        return name[5:]
    if name.startswith("str."):
        return name[4:]
    return name


def _expr_to_value(expr: Any) -> Any:
    """Extract a plain Python value from a literal expression."""
    if isinstance(expr, NumberLit):
        v = expr.value
        return int(v) if v == int(v) else v
    if isinstance(expr, StringLit):
        return expr.value
    if isinstance(expr, BoolLit):
        return expr.value
    if isinstance(expr, Identifier):
        if expr.name == "true":
            return True
        if expr.name == "false":
            return False
        return expr.name
    if isinstance(expr, UnaryOp) and expr.op == "-" and isinstance(expr.operand, NumberLit):
        v = -expr.operand.value
        return int(v) if v == int(v) else v
    return expr_to_str(expr)


class _ASTWalker:
    """Walks the AST and collects strategy components."""

    def __init__(self) -> None:
        self.strategy_name: str = ""
        self.strategy_settings: dict[str, Any] = {}
        self.inputs: list[dict[str, Any]] = []
        self.indicators: list[dict[str, Any]] = []
        self.variables: dict[str, str] = {}
        self.entry_long: list[dict[str, Any]] = []
        self.entry_short: list[dict[str, Any]] = []
        self.exit_rules: list[dict[str, Any]] = []
        self.indicators_found: list[str] = []
        self.entry_conditions: list[str] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

        # Internal tracking
        self._var_vars: set[str] = set()  # variables declared with 'var'
        self._security_vars: dict[str, dict] = {}  # var_name -> security info

    def walk(self, nodes: list) -> None:
        for node in nodes:
            self._visit(node)

    def _visit(self, node: Any) -> None:
        if isinstance(node, StrategyDecl):
            self._visit_strategy_decl(node)
        elif isinstance(node, InputDecl):
            self._visit_input_decl(node)
        elif isinstance(node, VarAssign):
            self._visit_var_assign(node)
        elif isinstance(node, DestructAssign):
            self._visit_destruct_assign(node)
        elif isinstance(node, SecurityCall):
            self._visit_security_call(node)
        elif isinstance(node, IfBlock):
            self._visit_if_block(node)
        elif isinstance(node, StrategyCall):
            self._visit_strategy_call(node, condition_str="")
        elif isinstance(node, ReassignStatement):
            self._visit_reassign(node)
        elif isinstance(node, PlotCall):
            pass  # ignored
        elif isinstance(node, FuncCall):
            # Standalone function call at top level -- record as variable if meaningful
            pass
        elif isinstance(node, SwitchBlock):
            pass  # switch at statement level without assignment is unusual
        else:
            pass  # skip unknown nodes

    # ----- Strategy declaration -----

    def _visit_strategy_decl(self, node: StrategyDecl) -> None:
        self.strategy_name = node.name
        self.strategy_settings = dict(node.args)

    # ----- Input declarations -----

    def _visit_input_decl(self, node: InputDecl) -> None:
        if node.input_type == "color":
            # Color inputs are display-only; skip for backtesting
            return

        inp: dict[str, Any] = {
            "name": node.var_name,
            "type": node.input_type,
            "default": node.default,
            "title": node.title or node.var_name,
        }
        if node.min_val is not None:
            inp["min_val"] = node.min_val
        if node.max_val is not None:
            inp["max_val"] = node.max_val
        if node.step is not None:
            inp["step"] = node.step
        if node.options is not None:
            inp["options"] = node.options
        if node.group:
            inp["group"] = node.group
        self.inputs.append(inp)

    # ----- Variable assignments -----

    def _visit_var_assign(self, node: VarAssign) -> None:
        if node.is_var:
            self._var_vars.add(node.name)

        expr = node.expr
        # Check if the expression is a ta.* indicator call
        if isinstance(expr, FuncCall) and expr.name.startswith("ta."):
            self._record_indicator(node.name, expr)
        elif isinstance(expr, Identifier) and expr.name.startswith("ta."):
            # e.g., vwapValue = ta.vwap  (property, not function call)
            self._record_indicator(node.name, FuncCall(expr.name, [], {}))
        elif isinstance(expr, FuncCall) and expr.name in ("hour", "minute", "time", "dayofweek"):
            # Time functions -- record as variable
            self.variables[node.name] = expr_to_str(expr)
        elif isinstance(expr, SwitchBlock):
            # Switch expression assigned to variable
            self.variables[node.name] = expr_to_str(expr)
        else:
            # General variable -- record the expression string
            self.variables[node.name] = expr_to_str(expr)

    def _visit_reassign(self, node: ReassignStatement) -> None:
        # Reassignments update tracked variable values
        # We just note them; runtime handles actual mutation
        pass

    def _record_indicator(self, var_name: str, call: FuncCall) -> None:
        func_name = call.name
        human_name = _INDICATOR_NAMES.get(func_name, func_name.replace("ta.", "").upper())

        args_dict: dict[str, Any] = {}
        # Map positional args by indicator type
        if func_name in ("ta.ema", "ta.sma", "ta.wma", "ta.hma", "ta.rma"):
            if call.args:
                args_dict["source"] = expr_to_str(call.args[0])
            if len(call.args) > 1:
                args_dict["period"] = _expr_to_value(call.args[1])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        elif func_name == "ta.atr":
            if call.args:
                args_dict["period"] = _expr_to_value(call.args[0])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        elif func_name == "ta.rsi":
            if call.args:
                args_dict["source"] = expr_to_str(call.args[0])
            if len(call.args) > 1:
                args_dict["period"] = _expr_to_value(call.args[1])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        elif func_name == "ta.vwap":
            if call.args:
                args_dict["source"] = expr_to_str(call.args[0])

        elif func_name in ("ta.crossover", "ta.crossunder"):
            if len(call.args) >= 2:
                args_dict["source1"] = expr_to_str(call.args[0])
                args_dict["source2"] = expr_to_str(call.args[1])
            args_dict.update({k: expr_to_str(v) for k, v in call.kwargs.items()})

        elif func_name == "ta.macd":
            if call.args:
                args_dict["source"] = expr_to_str(call.args[0])
            if len(call.args) > 1:
                args_dict["fast_length"] = _expr_to_value(call.args[1])
            if len(call.args) > 2:
                args_dict["slow_length"] = _expr_to_value(call.args[2])
            if len(call.args) > 3:
                args_dict["signal_length"] = _expr_to_value(call.args[3])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        elif func_name == "ta.stoch":
            if call.args:
                args_dict["close"] = expr_to_str(call.args[0])
            if len(call.args) > 1:
                args_dict["high"] = expr_to_str(call.args[1])
            if len(call.args) > 2:
                args_dict["low"] = expr_to_str(call.args[2])
            if len(call.args) > 3:
                args_dict["period"] = _expr_to_value(call.args[3])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        elif func_name == "ta.bb":
            if call.args:
                args_dict["source"] = expr_to_str(call.args[0])
            if len(call.args) > 1:
                args_dict["length"] = _expr_to_value(call.args[1])
            if len(call.args) > 2:
                args_dict["std_dev"] = _expr_to_value(call.args[2])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        elif func_name == "ta.dmi":
            if len(call.args) >= 1:
                args_dict["period"] = _expr_to_value(call.args[0])
            if len(call.args) >= 2:
                args_dict["smoothing"] = _expr_to_value(call.args[1])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        elif func_name in ("ta.highest", "ta.lowest"):
            if call.args:
                args_dict["source"] = expr_to_str(call.args[0])
            if len(call.args) > 1:
                args_dict["period"] = _expr_to_value(call.args[1])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        elif func_name == "ta.supertrend":
            if len(call.args) >= 2:
                args_dict["factor"] = _expr_to_value(call.args[0])
                args_dict["atr_period"] = _expr_to_value(call.args[1])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        elif func_name == "ta.adx":
            if len(call.args) >= 4:
                args_dict["high"] = expr_to_str(call.args[0])
                args_dict["low"] = expr_to_str(call.args[1])
                args_dict["close"] = expr_to_str(call.args[2])
                args_dict["period"] = _expr_to_value(call.args[3])
            elif len(call.args) >= 1:
                args_dict["period"] = _expr_to_value(call.args[0])
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        else:
            # Generic indicator -- store all args
            for i, a in enumerate(call.args):
                args_dict[f"arg{i}"] = _expr_to_value(a)
            args_dict.update({k: _expr_to_value(v) for k, v in call.kwargs.items()})

        indicator = {
            "name": _shorten_func(func_name).lower(),
            "var": var_name,
            "func": func_name,
            "args": args_dict,
        }
        self.indicators.append(indicator)

        if human_name not in self.indicators_found:
            self.indicators_found.append(human_name)

    # ----- Destructuring / Security -----

    def _visit_destruct_assign(self, node: DestructAssign) -> None:
        expr = node.expr
        if isinstance(expr, FuncCall) and expr.name == "ta.supertrend":
            args_dict: dict[str, Any] = {}
            if len(expr.args) >= 2:
                args_dict["factor"] = _expr_to_value(expr.args[0])
                args_dict["atr_period"] = _expr_to_value(expr.args[1])
            args_dict.update({k: _expr_to_value(v) for k, v in expr.kwargs.items()})
            line_var = node.names[0] if node.names else "st"
            dir_var = node.names[1] if len(node.names) > 1 else None
            self.indicators.append({
                "name": "supertrend",
                "var": line_var,
                "direction_var": dir_var,
                "func": "ta.supertrend",
                "args": args_dict,
            })
            if "SuperTrend" not in self.indicators_found:
                self.indicators_found.append("SuperTrend")
            return

        if isinstance(expr, FuncCall) and expr.name.startswith("ta.") and node.names:
            self._record_indicator(node.names[0], expr)
            # Store ALL destructured variable names so the engine can
            # map sub-outputs (e.g. macd → signal → histogram) to them.
            if len(node.names) > 1:
                self.indicators[-1]["destruct_names"] = list(node.names)
            return

        for name in node.names:
            self.variables[name] = f"destructured from {expr_to_str(expr)}"

    def _visit_security_call(self, node: SecurityCall) -> None:
        info = {
            "symbol": expr_to_str(node.symbol),
            "timeframe": expr_to_str(node.timeframe),
            "expression": expr_to_str(node.expression),
            "target_vars": node.target_vars,
        }
        for name in node.target_vars:
            self._security_vars[name] = info
            self.variables[name] = f"security({info['symbol']}, {info['timeframe']})"

        # Record as an indicator-like entry
        self.indicators.append({
            "name": "security",
            "var": ", ".join(node.target_vars),
            "func": "request.security",
            "args": {
                "symbol": info["symbol"],
                "timeframe": info["timeframe"],
                "expression": info["expression"],
            },
        })
        if "Daily Pivot Data (request.security)" not in self.indicators_found:
            self.indicators_found.append("Daily Pivot Data (request.security)")

    # ----- If blocks (entry / exit detection) -----

    def _visit_if_block(self, node: IfBlock, parent_condition: str = "") -> None:
        """Walk if-block and extract strategy calls within."""
        condition_str = expr_to_str(node.condition)
        if parent_condition:
            condition_str = f"{parent_condition} and {condition_str}"

        # Look for strategy calls in the body
        has_strategy_calls = False
        for stmt in node.body:
            if isinstance(stmt, StrategyCall):
                has_strategy_calls = True
                self._visit_strategy_call(stmt, condition_str)
            elif isinstance(stmt, IfBlock):
                self._visit_if_block(stmt, parent_condition=condition_str)
            elif isinstance(stmt, ReassignStatement):
                self._visit_reassign(stmt)
            elif isinstance(stmt, VarAssign):
                self._visit_var_assign(stmt)

        # Also walk else body
        for stmt in node.else_body:
            if isinstance(stmt, IfBlock):
                self._visit_if_block(stmt)
            elif isinstance(stmt, StrategyCall):
                else_cond = f"not ({condition_str})"
                self._visit_strategy_call(stmt, else_cond)

    def _visit_strategy_call(self, node: StrategyCall, condition_str: str = "") -> None:
        method = node.method
        args = node.args

        if method == "entry":
            entry_id = _expr_to_value(args.get("id", StringLit("")))
            direction_expr = args.get("direction")
            direction = _expr_to_value(direction_expr) if direction_expr else ""

            is_long = "long" in str(direction).lower() or "long" in str(entry_id).lower()
            is_short = "short" in str(direction).lower() or "short" in str(entry_id).lower()

            entry_info: dict[str, Any] = {
                "id": entry_id,
                "direction": "long" if is_long else "short" if is_short else str(direction),
                "condition": condition_str,
            }
            # Add optional kwargs
            for k in ("qty", "qty_percent", "comment", "when", "alert_message"):
                if k in args:
                    entry_info[k] = _expr_to_value(args[k])

            if is_long:
                self.entry_long.append(entry_info)
                desc = f"Long entry '{entry_id}': {condition_str}" if condition_str else f"Long entry '{entry_id}'"
                if desc not in self.entry_conditions:
                    self.entry_conditions.append(desc)
            elif is_short:
                self.entry_short.append(entry_info)
                desc = f"Short entry '{entry_id}': {condition_str}" if condition_str else f"Short entry '{entry_id}'"
                if desc not in self.entry_conditions:
                    self.entry_conditions.append(desc)

        elif method == "exit":
            exit_id = _expr_to_value(args.get("id", StringLit("")))
            from_entry = _expr_to_value(args.get("from_entry", StringLit("")))

            exit_info: dict[str, Any] = {
                "type": "exit",
                "id": exit_id,
                "from_entry": from_entry,
                "condition": condition_str,
            }
            for k in ("stop", "limit", "qty_percent", "qty", "comment",
                       "trail_price", "trail_points", "trail_offset",
                       "loss", "profit", "alert_message"):
                if k in args:
                    exit_info[k] = expr_to_str(args[k])

            self.exit_rules.append(exit_info)


        elif method == "close":
            close_id = _expr_to_value(args.get("id", StringLit("")))
            close_info = {
                "type": "close",
                "id": close_id,
                "condition": condition_str,
            }
            for k in ("qty_percent", "qty", "comment", "when", "alert_message"):
                if k in args:
                    close_info[k] = _expr_to_value(args[k])
            self.exit_rules.append(close_info)

        elif method == "close_all":
            close_all_info = {
                "type": "close_all",
                "condition": condition_str,
            }
            if "comment" in args:
                close_all_info["comment"] = _expr_to_value(args["comment"])
            self.exit_rules.append(close_all_info)

    # ----- Build output -----

    def build_result(self):
        """Construct the final output dict."""
        return {
            "strategy_name": self.strategy_name,
            "inputs": self.inputs,
            "indicators": self.indicators,
            "variables": self.variables,
            "entry_long": self.entry_long,
            "entry_short": self.entry_short,
            "exit_rules": self.exit_rules,
            "strategy_settings": self.strategy_settings,
            "indicators_found": self.indicators_found,
            "entry_conditions": self.entry_conditions,
            "errors": self.errors,
            "warnings": self.warnings,
        }


import re as _re
import logging as _logging

_fb_log = _logging.getLogger(__name__)


def _fallback_extract(source: str, result: dict) -> dict:
    """Regex-based enrichment: fix truncated multi-line variables,
    fill in missing indicators/inputs, and add strategy calls if AST missed them."""
    lines = source.split("\n")

    # ---- strategy name ----
    if not result.get("strategy_name"):
        m = _re.search(r'strategy\s*\(\s*"([^"]*)"', source)
        if m:
            result["strategy_name"] = m.group(1)

    # ---- inputs ----
    existing_input_names = {inp["name"] for inp in result.get("inputs", [])}
    for m in _re.finditer(
        r'(\w+)\s*=\s*input\.(int|float|bool|string|color)\s*\(([^)]*)\)',
        source,
    ):
        var_name, inp_type, args_str = m.group(1), m.group(2), m.group(3)
        if var_name in existing_input_names or inp_type == "color":
            continue
        default = None
        title = var_name
        dm = _re.match(r'\s*(-?[\d.]+|true|false|"[^"]*")', args_str)
        if dm:
            raw = dm.group(1)
            if raw in ("true", "false"):
                default = raw == "true"
            elif raw.startswith('"'):
                default = raw.strip('"')
            else:
                try:
                    default = int(raw) if "." not in raw else float(raw)
                except ValueError:
                    default = raw
        tm = _re.search(r'"([^"]+)"', args_str)
        if tm and dm and tm.group(0) != dm.group(0):
            title = tm.group(1)
        result["inputs"].append({
            "name": var_name,
            "type": inp_type,
            "default": default,
            "title": title,
        })
        existing_input_names.add(var_name)

    # ---- indicators (ta.*) ----
    existing_ind_vars = {ind["var"] for ind in result.get("indicators", [])}
    for m in _re.finditer(r'(\w+)\s*=\s*(ta\.\w+)\s*\(([^)]*)\)', source):
        var_name, func_name, args_str = m.group(1), m.group(2), m.group(3)
        if var_name in existing_ind_vars:
            continue
        short = func_name.replace("ta.", "").lower()
        args_dict = _parse_indicator_args(func_name, args_str)
        result["indicators"].append({
            "name": short,
            "var": var_name,
            "func": func_name,
            "args": args_dict,
        })
        existing_ind_vars.add(var_name)
        human = _INDICATOR_NAMES.get(func_name, short.upper())
        if human not in result["indicators_found"]:
            result["indicators_found"].append(human)

    # Destructured: [a, b] = ta.supertrend(...)
    for m in _re.finditer(r'\[([^\]]+)\]\s*=\s*(ta\.\w+)\s*\(([^)]*)\)', source):
        names_str, func_name, args_str = m.group(1), m.group(2), m.group(3)
        names = [n.strip() for n in names_str.split(",")]
        primary = names[0]
        if primary in existing_ind_vars:
            continue
        short = func_name.replace("ta.", "").lower()
        args_dict = _parse_indicator_args(func_name, args_str)
        ind = {
            "name": short,
            "var": primary,
            "func": func_name,
            "args": args_dict,
        }
        if len(names) > 1:
            ind["destruct_names"] = names
            if short == "supertrend":
                ind["direction_var"] = names[1]
        result["indicators"].append(ind)
        existing_ind_vars.add(primary)
        human = _INDICATOR_NAMES.get(func_name, short.upper())
        if human not in result["indicators_found"]:
            result["indicators_found"].append(human)

    # crossover / crossunder
    for m in _re.finditer(r'(\w+)\s*=\s*(ta\.cross(?:over|under))\s*\(([^)]*)\)', source):
        var_name, func_name, args_str = m.group(1), m.group(2), m.group(3)
        if var_name in existing_ind_vars:
            continue
        parts = [p.strip() for p in args_str.split(",")]
        args_dict = {}
        if len(parts) >= 2:
            args_dict["source1"] = parts[0]
            args_dict["source2"] = parts[1]
        short = func_name.replace("ta.", "").lower()
        result["indicators"].append({
            "name": short,
            "var": var_name,
            "func": func_name,
            "args": args_dict,
        })
        existing_ind_vars.add(var_name)
        human = _INDICATOR_NAMES.get(func_name, short.upper())
        if human not in result["indicators_found"]:
            result["indicators_found"].append(human)

    # ---- variables (override truncated AST versions with longer regex versions) ----
    existing_vars = result.get("variables", {})
    joined_source = _join_continuation_lines(source)
    for m in _re.finditer(r'^(\w+)\s*=\s*(.+)$', joined_source, _re.MULTILINE):
        var_name, expr_str = m.group(1), m.group(2).strip()
        if _re.match(r'(input\.|ta\.|request\.|strategy\s*\(|array\.|/)', expr_str):
            continue
        if _re.match(r'\w+\[\]', expr_str):
            continue
        old_val = existing_vars.get(var_name)
        if old_val is None or len(expr_str) > len(str(old_val)):
            result["variables"][var_name] = expr_str

    # ---- strategy calls (only if AST didn't already find them) ----
    if not result.get("entry_long") and not result.get("entry_short"):
        _extract_strategy_calls_from_source(lines, result)

    # ---- exit rules from regex (only if AST didn't find them) ----
    if not result.get("exit_rules"):
        _extract_strategy_calls_from_source(lines, result)

    # ---- last-resort: infer entries from variable names if still empty ----
    if not result.get("entry_long") and not result.get("entry_short"):
        _infer_entries_from_variables(result)

    return result


def _join_continuation_lines(source):
    """Join PineScript continuation lines."""
    out = []
    for line in source.split("\n"):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("//"):
            out.append(line)
            continue
        if line and line[0] in (" ", "\t") and out:
            if stripped.startswith(("and ", "or ", "and(", "or(")):
                out[-1] = out[-1] + " " + stripped
                continue
        out.append(line)
    return "\n".join(out)


def _parse_indicator_args(func_name, args_str):
    args_dict = {}
    parts = _split_args(args_str)
    positional = []
    for part in parts:
        part = part.strip()
        kv = _re.match(r'(\w+)\s*=\s*(.*)', part)
        if kv:
            args_dict[kv.group(1)] = _try_numeric(kv.group(2).strip())
        else:
            positional.append(part)
    short = func_name.replace("ta.", "")
    if short in ("ema", "sma", "wma", "hma", "rma"):
        if len(positional) > 0:
            args_dict.setdefault("source", positional[0])
        if len(positional) > 1:
            args_dict.setdefault("period", _try_numeric(positional[1]))
    elif short == "rsi":
        if len(positional) > 0:
            args_dict.setdefault("source", positional[0])
        if len(positional) > 1:
            args_dict.setdefault("period", _try_numeric(positional[1]))
    elif short == "macd":
        if len(positional) > 0:
            args_dict.setdefault("source", positional[0])
        if len(positional) > 1:
            args_dict.setdefault("fast_length", _try_numeric(positional[1]))
        if len(positional) > 2:
            args_dict.setdefault("slow_length", _try_numeric(positional[2]))
        if len(positional) > 3:
            args_dict.setdefault("signal_length", _try_numeric(positional[3]))
    elif short == "atr":
        if len(positional) > 0:
            args_dict.setdefault("period", _try_numeric(positional[0]))
    elif short == "supertrend":
        if len(positional) > 0:
            args_dict.setdefault("factor", _try_numeric(positional[0]))
        if len(positional) > 1:
            args_dict.setdefault("atr_period", _try_numeric(positional[1]))
    elif short == "adx":
        if len(positional) > 0:
            args_dict.setdefault("period", _try_numeric(positional[0]))
    elif short in ("dmi",):
        if len(positional) > 0:
            args_dict.setdefault("period", _try_numeric(positional[0]))
        if len(positional) > 1:
            args_dict.setdefault("smoothing", _try_numeric(positional[1]))
    else:
        for i, p in enumerate(positional):
            args_dict["arg{}".format(i)] = _try_numeric(p)
    return args_dict


def _split_args(s):
    parts = []
    depth = 0
    current = []
    for ch in s:
        if ch in ("(", "["):
            depth += 1
        elif ch in (")", "]"):
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _try_numeric(s):
    s = str(s).strip()
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def _infer_entries_from_variables(result):
    """Last-resort: if strategy.entry calls were not found by AST or regex,
    look for variables named buyEntry/sellEntry/longEntry/shortEntry etc.
    and create synthetic entry records so the backtest engine can evaluate them."""
    variables = result.get("variables", {})
    if not variables:
        return

    # Patterns that suggest a long entry condition variable
    long_patterns = ["buyEntry", "buySignal", "longEntry", "longSignal",
                     "enterLong", "goLong", "buy_entry", "long_entry",
                     "buy_signal", "long_signal", "filteredBuy"]
    short_patterns = ["sellEntry", "sellSignal", "shortEntry", "shortSignal",
                      "enterShort", "goShort", "sell_entry", "short_entry",
                      "sell_signal", "short_signal", "filteredSell"]

    for var_name in variables:
        for pat in long_patterns:
            if var_name == pat or var_name.lower() == pat.lower():
                result["entry_long"].append({
                    "id": "Buy",
                    "direction": "long",
                    "condition": var_name,
                    "comment": f"inferred from variable {var_name}",
                })
                desc = "Long entry (inferred): {}".format(var_name)
                if desc not in result["entry_conditions"]:
                    result["entry_conditions"].append(desc)
                break
        for pat in short_patterns:
            if var_name == pat or var_name.lower() == pat.lower():
                result["entry_short"].append({
                    "id": "Sell",
                    "direction": "short",
                    "condition": var_name,
                    "comment": f"inferred from variable {var_name}",
                })
                desc = "Short entry (inferred): {}".format(var_name)
                if desc not in result["entry_conditions"]:
                    result["entry_conditions"].append(desc)
                break

    # Also look for close/exit variables if exit_rules are empty
    if not result.get("exit_rules"):
        exit_long_patterns = ["exitLong", "closeLong", "exit_long", "close_long"]
        exit_short_patterns = ["exitShort", "closeShort", "exit_short", "close_short"]
        for var_name in variables:
            for pat in exit_long_patterns:
                if var_name == pat or var_name.lower() == pat.lower():
                    result["exit_rules"].append({
                        "type": "close",
                        "id": f"close_{var_name}",
                        "condition": var_name,
                        "comment": f"inferred from variable {var_name}",
                    })
                    break
            for pat in exit_short_patterns:
                if var_name == pat or var_name.lower() == pat.lower():
                    result["exit_rules"].append({
                        "type": "close",
                        "id": f"close_{var_name}",
                        "condition": var_name,
                        "comment": f"inferred from variable {var_name}",
                    })
                    break


def _extract_strategy_calls_from_source(lines, result):
    """Walk source lines to find if-blocks containing strategy.* calls."""
    i = 0
    n = len(lines)
    while i < n:
        stripped = lines[i].lstrip()
        m = _re.match(r'^if\s+(.+)$', stripped)
        if m:
            condition = m.group(1).strip()
            if_indent = len(lines[i]) - len(lines[i].lstrip())
            i += 1
            # Collect all body lines, joining multi-line calls
            body_lines = []
            accum = ""
            while i < n:
                line = lines[i]
                if not line.strip() or line.strip().startswith("//"):
                    i += 1
                    continue
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= if_indent:
                    break
                body_stripped = line.strip()
                # Join continuation: if we're accumulating a multi-line strategy call
                if accum:
                    accum += " " + body_stripped
                    # Check if parens are balanced
                    depth = sum(1 for c in accum if c == '(') - sum(1 for c in accum if c == ')')
                    if depth <= 0:
                        body_lines.append(accum)
                        accum = ""
                elif body_stripped.startswith("strategy.") and body_stripped.count("(") > body_stripped.count(")"):
                    accum = body_stripped
                else:
                    body_lines.append(body_stripped)
                i += 1
            if accum:
                body_lines.append(accum)
            for bl in body_lines:
                _process_strategy_line(bl, condition, result)
            continue
        if stripped.startswith("strategy."):
            # Handle standalone strategy calls, possibly multi-line
            accum = stripped
            depth = sum(1 for c in accum if c == '(') - sum(1 for c in accum if c == ')')
            while depth > 0 and i + 1 < n:
                i += 1
                accum += " " + lines[i].strip()
                depth = sum(1 for c in accum if c == '(') - sum(1 for c in accum if c == ')')
            _process_strategy_line(accum, "", result)
        i += 1


def _process_strategy_line(line, condition, result):
    # Strip trailing comments
    comment_pos = -1
    in_str = False
    str_char = None
    for ci, ch in enumerate(line):
        if not in_str and ch in ('"', "'"):
            in_str = True
            str_char = ch
        elif in_str and ch == str_char:
            in_str = False
        elif not in_str and ch == '/' and ci + 1 < len(line) and line[ci + 1] == '/':
            comment_pos = ci
            break
    if comment_pos > 0:
        line = line[:comment_pos].rstrip()

    m = _re.match(r'strategy\.entry\s*\((.+)\)\s*$', line)
    if m:
        args_str = m.group(1)
        parts = _split_args(args_str)
        kw = _parse_kw_args(parts)
        entry_id = _unquote(kw.get("_pos0", kw.get("id", "")))
        direction_raw = kw.get("_pos1", kw.get("direction", ""))
        is_long = "long" in str(direction_raw).lower() or "long" in entry_id.lower() or "buy" in entry_id.lower()
        is_short = "short" in str(direction_raw).lower() or "short" in entry_id.lower() or "sell" in entry_id.lower()
        entry_info = {
            "id": entry_id,
            "direction": "long" if is_long else "short" if is_short else str(direction_raw),
            "condition": condition,
        }
        for k in ("qty", "comment", "qty_percent", "when", "alert_message"):
            if k in kw:
                entry_info[k] = _try_numeric(_unquote(kw[k]))
        if is_long:
            result["entry_long"].append(entry_info)
            desc = "Long entry '{}': {}".format(entry_id, condition) if condition else "Long entry '{}'".format(entry_id)
            if desc not in result["entry_conditions"]:
                result["entry_conditions"].append(desc)
        elif is_short:
            result["entry_short"].append(entry_info)
            desc = "Short entry '{}': {}".format(entry_id, condition) if condition else "Short entry '{}'".format(entry_id)
            if desc not in result["entry_conditions"]:
                result["entry_conditions"].append(desc)
        return

    m = _re.match(r'strategy\.exit\s*\((.+)\)\s*$', line)
    if m:
        args_str = m.group(1)
        parts = _split_args(args_str)
        kw = _parse_kw_args(parts)
        exit_id = _unquote(kw.get("_pos0", kw.get("id", "")))
        from_entry = _unquote(kw.get("_pos1", kw.get("from_entry", "")))
        exit_info = {
            "type": "exit",
            "id": exit_id,
            "from_entry": from_entry,
            "condition": condition,
        }
        for k in ("stop", "limit", "qty_percent", "qty", "comment",
                   "trail_price", "trail_points", "trail_offset",
                   "loss", "profit", "alert_message"):
            if k in kw:
                exit_info[k] = kw[k]
        result["exit_rules"].append(exit_info)
        return

    m = _re.match(r'strategy\.close\s*\((.+)\)\s*$', line)
    if m:
        args_str = m.group(1)
        parts = _split_args(args_str)
        kw = _parse_kw_args(parts)
        close_id = _unquote(kw.get("_pos0", kw.get("id", "")))
        close_info = {
            "type": "close",
            "id": close_id,
            "condition": condition,
        }
        for k in ("comment", "qty", "qty_percent", "when", "alert_message"):
            if k in kw:
                close_info[k] = _unquote(kw[k])
        result["exit_rules"].append(close_info)
        return

    m = _re.match(r'strategy\.close_all\s*\((.+)\)\s*$', line)
    if m:
        args_str = m.group(1)
        parts = _split_args(args_str)
        kw = _parse_kw_args(parts)
        close_all_info = {
            "type": "close_all",
            "condition": condition,
        }
        if "comment" in kw:
            close_all_info["comment"] = _unquote(kw["comment"])
        result["exit_rules"].append(close_all_info)
        return


def _parse_kw_args(parts):
    kw = {}
    pos_idx = 0
    for part in parts:
        part = part.strip()
        m = _re.match(r'(\w+)\s*=\s*(.*)', part)
        if m:
            kw[m.group(1)] = m.group(2).strip()
        else:
            kw["_pos{}".format(pos_idx)] = part
            pos_idx += 1
    return kw


def _unquote(s):
    s = str(s).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def parse_pinescript(source):
    """Main entry point: parse PineScript source and return a strategy definition dict."""
    result = {
        "strategy_name": "",
        "inputs": [],
        "indicators": [],
        "variables": {},
        "entry_long": [],
        "entry_short": [],
        "exit_rules": [],
        "strategy_settings": {},
        "indicators_found": [],
        "entry_conditions": [],
        "errors": [],
        "warnings": [],
    }

    try:
        tokens = tokenize(source)
    except Exception as e:
        result["errors"].append("Lexer error: {}".format(e))
        return result

    try:
        parser = PineScriptParser(tokens)
        ast_nodes = parser.parse()
        result["warnings"].extend(parser.warnings)
    except Exception as e:
        result["errors"].append("Parser error: {}".format(e))
        return result

    try:
        walker = _ASTWalker()
        walker.walk(ast_nodes)
        output = walker.build_result()
        output["warnings"] = result["warnings"] + walker.warnings
    except Exception as e:
        output = result
        output["errors"].append("Transpiler error: {}".format(e))

    # ------- FALLBACK / ENRICHMENT -------
    # Always run regex-based enrichment to fix truncated multi-line variables,
    # fill in missing indicators/inputs, and add strategy calls if AST missed them.
    _fallback_extract(source, output)

    return output
