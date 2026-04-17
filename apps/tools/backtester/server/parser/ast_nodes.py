"""AST node definitions for the PineScript subset parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union


@dataclass
class StrategyDecl:
    """strategy("name", ...) declaration."""
    name: str
    args: dict[str, Any]  # overlay, initial_capital, commission_value, etc.


@dataclass
class InputDecl:
    """input.int(...), input.float(...), input.bool(...), input.string(...) declaration."""
    var_name: str
    input_type: str  # int, float, bool, string, color
    default: Any
    title: str = ""
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    options: Optional[list[str]] = None
    group: str = ""


@dataclass
class VarAssign:
    """Variable assignment: name = expr  or  var bool name = expr."""
    name: str
    expr: Expr
    is_var: bool = False       # var keyword (persistent across bars)
    is_reassign: bool = False  # := operator
    type_hint: str = ""        # bool, float, etc. if specified


@dataclass
class DestructAssign:
    """Destructuring assignment: [a, b, c] = expr."""
    names: list[str]
    expr: Expr


@dataclass
class FuncCall:
    """Function call: ta.ema(close, 20) or strategy.entry("Long", strategy.long)."""
    name: str  # e.g. "ta.ema", "strategy.entry"
    args: list[Expr] = field(default_factory=list)
    kwargs: dict[str, Expr] = field(default_factory=dict)


@dataclass
class BinaryOp:
    """Binary operation: left op right."""
    left: Expr
    op: str  # +, -, *, /, >, <, >=, <=, ==, !=, and, or
    right: Expr


@dataclass
class UnaryOp:
    """Unary operation: not x  or  -x."""
    op: str  # not, -
    operand: Expr


@dataclass
class Ternary:
    """Ternary expression: condition ? true_val : false_val."""
    condition: Expr
    true_val: Expr
    false_val: Expr


@dataclass
class IndexAccess:
    """Index/history access: close[1]."""
    expr: Expr
    index: Expr


@dataclass
class Identifier:
    """Variable or constant reference."""
    name: str


@dataclass
class NumberLit:
    """Numeric literal."""
    value: float


@dataclass
class StringLit:
    """String literal."""
    value: str


@dataclass
class BoolLit:
    """Boolean literal."""
    value: bool


@dataclass
class IfBlock:
    """if/else block."""
    condition: Expr
    body: list  # list of statements (AST nodes)
    else_body: list = field(default_factory=list)


@dataclass
class SwitchBlock:
    """switch block."""
    expr: Optional[Expr]
    cases: list[tuple[Expr, list]]  # (match_value, body statements)
    default: Optional[list] = None


@dataclass
class StrategyCall:
    """strategy.entry/exit/close/close_all call."""
    method: str  # entry, exit, close, close_all
    args: dict[str, Expr] = field(default_factory=dict)


@dataclass
class SecurityCall:
    """request.security(...) call, optionally with destructuring."""
    symbol: Expr
    timeframe: Expr
    expression: Expr
    kwargs: dict[str, Expr] = field(default_factory=dict)
    target_vars: list[str] = field(default_factory=list)


@dataclass
class PlotCall:
    """plot/plotshape/bgcolor/table.*/alertcondition -- ignored during backtesting."""
    func_name: str = ""


@dataclass
class ReassignStatement:
    """Standalone reassignment: name := expr."""
    name: str
    expr: Expr


# Union type for all expression nodes
Expr = Union[
    FuncCall, BinaryOp, UnaryOp, Ternary, IndexAccess,
    Identifier, NumberLit, StringLit, BoolLit
]

# Union type for all statement nodes
Statement = Union[
    StrategyDecl, InputDecl, VarAssign, DestructAssign,
    IfBlock, SwitchBlock, StrategyCall, SecurityCall, PlotCall,
    ReassignStatement, FuncCall
]
