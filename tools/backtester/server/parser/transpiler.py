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

        elif func_name in ("ta.highest", "ta.lowest"):
            if call.args:
                args_dict["source"] = expr_to_str(call.args[0])
            if len(call.args) > 1:
                args_dict["period"] = _expr_to_value(call.args[1])
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
        # Record variables
        for name in node.names:
            self.variables[name] = f"destructured from {expr_to_str(node.expr)}"

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
            close_info: dict[str, Any] = {
                "type": "close",
                "id": close_id,
                "condition": condition_str,
            }
            for k in ("qty_percent", "qty", "comment", "when", "alert_message"):
                if k in args:
                    close_info[k] = _expr_to_value(args[k])
            self.exit_rules.append(close_info)

        elif method == "close_all":
            close_all_info: dict[str, Any] = {
                "type": "close_all",
                "condition": condition_str,
            }
            if "comment" in args:
                close_all_info["comment"] = _expr_to_value(args["comment"])
            self.exit_rules.append(close_all_info)

    # ----- Build output -----

    def build_result(self) -> dict[str, Any]:
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


def parse_pinescript(source: str) -> dict[str, Any]:
    """Main entry point: parse PineScript source and return a strategy definition dict.

    Returns a dict compatible with the ParseResult model, plus additional
    fields for the backtesting engine (indicators, variables, entry_long, etc.).
    """
    result: dict[str, Any] = {
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
        result["errors"].append(f"Lexer error: {e}")
        return result

    try:
        parser = PineScriptParser(tokens)
        ast_nodes = parser.parse()
        result["warnings"].extend(parser.warnings)
    except Exception as e:
        result["errors"].append(f"Parser error: {e}")
        return result

    try:
        walker = _ASTWalker()
        walker.walk(ast_nodes)
        output = walker.build_result()
        # Merge walker warnings with parser warnings
        output["warnings"] = result["warnings"] + walker.warnings
        return output
    except Exception as e:
        result["errors"].append(f"Transpiler error: {e}")
        return result
