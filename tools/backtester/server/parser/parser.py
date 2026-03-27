"""Recursive-descent parser for a subset of TradingView PineScript v5.

Converts a token stream from the lexer into an AST defined in ast_nodes.
"""

from __future__ import annotations

from typing import Any, Optional

from .lexer import Token, TokenType
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

# PineScript functions that are purely visual / ignored during backtesting
_PLOT_FUNCTIONS = {
    "plot", "plotshape", "plotchar", "plotarrow", "plotbar", "plotcandle",
    "bgcolor", "barcolor", "fill", "hline",
    "alertcondition", "alert",
    "label.new", "label.set_text", "label.delete",
    "line.new", "line.delete",
    "box.new", "box.delete",
}

# Prefixes for table / visual calls that are always ignored
_PLOT_PREFIXES = ("table.", "label.", "line.", "box.")


class ParseError(Exception):
    """Raised when an unrecoverable parse error occurs."""


class PineScriptParser:
    """Recursive-descent parser for PineScript v5 subset."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.warnings: list[str] = []

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _cur(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, "", 0, 0)

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return Token(TokenType.EOF, "", 0, 0)

    def _advance(self) -> Token:
        tok = self._cur()
        self.pos += 1
        return tok

    def _match(self, *types: TokenType) -> Optional[Token]:
        if self._cur().type in types:
            return self._advance()
        return None

    def _expect(self, tt: TokenType) -> Token:
        tok = self._cur()
        if tok.type != tt:
            raise ParseError(
                f"Expected {tt.name} but got {tok.type.name} ({tok.value!r}) "
                f"at line {tok.line}:{tok.col}"
            )
        return self._advance()

    def _skip_newlines(self) -> None:
        while self._cur().type == TokenType.NEWLINE:
            self._advance()

    def _at_end(self) -> bool:
        return self._cur().type == TokenType.EOF

    # ------------------------------------------------------------------
    # Lookahead helpers
    # ------------------------------------------------------------------

    def _is_func_call_ahead(self) -> bool:
        """Check if current position starts  ident.ident.ident...(..."""
        save = self.pos
        try:
            if self._cur().type != TokenType.IDENT:
                return False
            self._advance()
            while self._cur().type == TokenType.DOT:
                self._advance()
                if self._cur().type == TokenType.IDENT:
                    self._advance()
                else:
                    break
            return self._cur().type == TokenType.LPAREN
        finally:
            self.pos = save

    def _is_ident_like(self, tok: Token = None) -> bool:
        """Check if token is an identifier or a keyword used as identifier (e.g. strategy.long)."""
        if tok is None:
            tok = self._cur()
        return tok.type in (TokenType.IDENT, TokenType.STRATEGY, TokenType.SWITCH, TokenType.VAR)

    def _read_dotted_name(self) -> str:
        """Read an identifier possibly joined with dots: ta.ema, strategy.long."""
        if not self._is_ident_like():
            raise ParseError(
                f"Expected identifier but got {self._cur().type.name} ({self._cur().value!r}) "
                f"at line {self._cur().line}:{self._cur().col}"
            )
        parts = [self._advance().value]
        while self._cur().type == TokenType.DOT:
            self._advance()
            if self._is_ident_like():
                parts.append(self._advance().value)
            else:
                break
        return ".".join(parts)

    # ------------------------------------------------------------------
    # Top-level parse
    # ------------------------------------------------------------------

    def parse(self) -> list:
        """Parse the full token stream and return a list of AST statement nodes."""
        nodes: list = []
        self._skip_newlines()
        while not self._at_end():
            try:
                node = self._parse_statement()
                if node is not None:
                    nodes.append(node)
            except ParseError as e:
                self.warnings.append(str(e))
                # Skip to next newline or dedent to recover
                self._skip_to_next_statement()
            self._skip_newlines()
        return nodes

    def _skip_to_next_statement(self) -> None:
        """Advance past the current (broken) statement to recover."""
        depth = 0
        while not self._at_end():
            t = self._cur().type
            if t == TokenType.INDENT:
                depth += 1
                self._advance()
            elif t == TokenType.DEDENT:
                if depth > 0:
                    depth -= 1
                    self._advance()
                else:
                    break
            elif t == TokenType.NEWLINE:
                self._advance()
                if depth == 0:
                    break
            else:
                self._advance()

    # ------------------------------------------------------------------
    # Statement parsing
    # ------------------------------------------------------------------

    def _parse_statement(self):
        """Parse one top-level statement."""
        tok = self._cur()

        # strategy(...) declaration -- only when directly followed by '('
        if tok.type == TokenType.STRATEGY and self._peek(1).type == TokenType.LPAREN:
            return self._parse_strategy_decl()

        # strategy.entry/exit/close/... -- treat as ident statement
        if tok.type == TokenType.STRATEGY and self._peek(1).type == TokenType.DOT:
            return self._parse_ident_statement()

        # var declaration: var bool x = ...
        if tok.type == TokenType.VAR:
            return self._parse_var_decl()

        # if block
        if tok.type == TokenType.IF:
            return self._parse_if_block()

        # switch block -- can appear as statement or expression; at statement level
        # it's always  varName = switch expr ...
        # But standalone switch is also possible, handled via assignment path.

        # Destructuring: [a, b, c] = ...
        if tok.type == TokenType.LBRACKET:
            return self._parse_destruct_assign()

        # Identifier-led statements (assignments, function calls, strategy.*, etc.)
        if tok.type == TokenType.IDENT:
            return self._parse_ident_statement()

        # Unknown -- skip
        self.warnings.append(
            f"Unexpected token {tok.type.name} ({tok.value!r}) at line {tok.line}"
        )
        self._advance()
        return None

    # ------------------------------------------------------------------
    # strategy(...) declaration
    # ------------------------------------------------------------------

    def _parse_strategy_decl(self) -> StrategyDecl:
        self._expect(TokenType.STRATEGY)
        self._expect(TokenType.LPAREN)
        args_list, kwargs = self._parse_call_args()
        self._expect(TokenType.RPAREN)

        name = ""
        if args_list:
            first = args_list[0]
            if isinstance(first, StringLit):
                name = first.value

        # Convert remaining positional args and kwargs to plain dict
        settings: dict[str, Any] = {}
        for k, v in kwargs.items():
            settings[k] = self._expr_to_value(v)

        return StrategyDecl(name=name, args=settings)

    # ------------------------------------------------------------------
    # var declaration
    # ------------------------------------------------------------------

    def _parse_var_decl(self) -> VarAssign:
        self._expect(TokenType.VAR)
        type_hint = ""
        # Optional type hint (bool, float, int, string, table)
        if self._cur().type == TokenType.IDENT:
            # Could be a type hint or the variable name itself.
            # PineScript type hints: bool, float, int, string, color, table
            candidate = self._cur().value.lower()
            if candidate in ("bool", "float", "int", "string", "color", "table", "array", "matrix"):
                type_hint = self._advance().value
            # Special case: if next token is an ident + assign, this was a type hint
            # Otherwise it's the variable name.

        var_name = self._expect(TokenType.IDENT).value
        self._expect(TokenType.ASSIGN)
        expr = self._parse_expression()
        return VarAssign(name=var_name, expr=expr, is_var=True, type_hint=type_hint)

    # ------------------------------------------------------------------
    # if block
    # ------------------------------------------------------------------

    def _parse_if_block(self) -> IfBlock:
        self._expect(TokenType.IF)
        condition = self._parse_expression()
        self._skip_newlines()

        body = self._parse_indented_block()

        else_body: list = []
        # Check for else
        self._skip_newlines()
        if self._cur().type == TokenType.ELSE:
            self._advance()
            # else if ...
            if self._cur().type == TokenType.IF:
                else_body = [self._parse_if_block()]
            else:
                self._skip_newlines()
                else_body = self._parse_indented_block()

        return IfBlock(condition=condition, body=body, else_body=else_body)

    def _parse_indented_block(self) -> list:
        """Parse an INDENT ... DEDENT block and return the list of statements."""
        stmts: list = []
        if self._cur().type != TokenType.INDENT:
            # Single-line body (no indent) -- parse one statement
            self._skip_newlines()
            s = self._parse_statement()
            if s is not None:
                stmts.append(s)
            return stmts

        self._expect(TokenType.INDENT)
        self._skip_newlines()
        while self._cur().type not in (TokenType.DEDENT, TokenType.EOF):
            try:
                s = self._parse_statement()
                if s is not None:
                    stmts.append(s)
            except ParseError as e:
                self.warnings.append(str(e))
                self._skip_to_next_statement()
            self._skip_newlines()

        self._match(TokenType.DEDENT)
        return stmts

    # ------------------------------------------------------------------
    # Destructuring: [a, b, c] = request.security(...)
    # ------------------------------------------------------------------

    def _parse_destruct_assign(self):
        self._expect(TokenType.LBRACKET)
        names: list[str] = []
        names.append(self._expect(TokenType.IDENT).value)
        while self._match(TokenType.COMMA):
            names.append(self._expect(TokenType.IDENT).value)
        self._expect(TokenType.RBRACKET)
        self._expect(TokenType.ASSIGN)
        expr = self._parse_expression()

        # If it's a request.security call, wrap as SecurityCall
        if isinstance(expr, FuncCall) and expr.name in ("request.security", "request.security_lower_tf"):
            return self._build_security_call(expr, names)

        return DestructAssign(names=names, expr=expr)

    def _build_security_call(self, call: FuncCall, target_vars: list[str]) -> SecurityCall:
        args = call.args
        symbol = args[0] if len(args) > 0 else Identifier("syminfo.tickerid")
        timeframe = args[1] if len(args) > 1 else StringLit("D")
        expression = args[2] if len(args) > 2 else Identifier("close")
        return SecurityCall(
            symbol=symbol,
            timeframe=timeframe,
            expression=expression,
            kwargs=call.kwargs,
            target_vars=target_vars,
        )

    # ------------------------------------------------------------------
    # Identifier-led statement
    # ------------------------------------------------------------------

    def _parse_ident_statement(self):
        """Parse statement starting with an identifier.

        Could be:
          - varName = expr            (assignment)
          - varName := expr           (reassignment)
          - strategy.entry(...)       (strategy call)
          - strategy.exit(...)        (strategy call)
          - ta.ema(close, 20)         (function call as statement)
          - plot(...)                 (plot call)
          - input.int(...)            (probably part of an assignment, handled above)
        """
        # Check for dotted name followed by '(' -- function call or strategy/plot call
        # First, see if this is an assignment:  ident = expr  or  ident := expr
        # We need to look past a potential dotted name to check.

        # Save position for backtracking
        save = self.pos

        # Read a dotted name
        name = self._read_dotted_name()

        # Check what follows
        cur = self._cur()

        # Assignment: name = expr
        if cur.type == TokenType.ASSIGN:
            self._advance()
            expr = self._parse_expression()
            # Check if it's an input.* call
            if isinstance(expr, FuncCall) and expr.name.startswith("input."):
                return self._build_input_decl(name, expr)
            # Check if it's a request.security call without destructuring
            if isinstance(expr, FuncCall) and expr.name == "request.security":
                sc = self._build_security_call(expr, [name])
                return sc
            return VarAssign(name=name, expr=expr)

        # Reassignment: name := expr
        if cur.type == TokenType.REASSIGN:
            self._advance()
            expr = self._parse_expression()
            return ReassignStatement(name=name, expr=expr)

        # Function call: name(...)
        if cur.type == TokenType.LPAREN:
            self.pos = save
            expr = self._parse_expression()
            if isinstance(expr, FuncCall):
                return self._categorize_func_call(expr)
            return expr

        # If it's just an identifier reference at statement level -- probably leftover
        self.pos = save
        expr = self._parse_expression()
        if isinstance(expr, FuncCall):
            return self._categorize_func_call(expr)
        # Expression as statement (uncommon but valid)
        return VarAssign(name="_", expr=expr)

    def _categorize_func_call(self, call: FuncCall):
        """Convert a FuncCall to the appropriate AST node type."""
        name = call.name

        # strategy.entry/exit/close/close_all
        if name.startswith("strategy."):
            method = name.split(".", 1)[1]
            if method in ("entry", "exit", "close", "close_all"):
                # Build kwargs from positional + keyword args
                kw: dict[str, Expr] = dict(call.kwargs)
                # For entry/exit/close the first positional arg is the ID
                if call.args:
                    kw.setdefault("id", call.args[0])
                if len(call.args) > 1:
                    if method == "entry":
                        kw.setdefault("direction", call.args[1])
                    elif method == "exit":
                        kw.setdefault("from_entry", call.args[1])
                return StrategyCall(method=method, args=kw)

        # Plot functions
        if name in _PLOT_FUNCTIONS or any(name.startswith(p) for p in _PLOT_PREFIXES):
            return PlotCall(func_name=name)

        # Generic function call as statement
        return call

    def _build_input_decl(self, var_name: str, call: FuncCall) -> InputDecl:
        """Convert input.int/float/bool/string call to InputDecl."""
        input_type = call.name.split(".")[-1]  # int, float, bool, string, color
        args = call.args
        kw = call.kwargs

        default = self._expr_to_value(args[0]) if args else None
        title = self._expr_to_value(kw.get("title", args[1] if len(args) > 1 else StringLit("")))
        if isinstance(title, str) and title == "":
            title = var_name

        min_val = self._expr_to_value(kw.get("minval")) if "minval" in kw else None
        max_val = self._expr_to_value(kw.get("maxval")) if "maxval" in kw else None
        step = self._expr_to_value(kw.get("step")) if "step" in kw else None
        group = self._expr_to_value(kw.get("group", StringLit("")))

        options = None
        if "options" in kw:
            opt_expr = kw["options"]
            # options is typically a FuncCall wrapping a list -- we stored it as-is
            # We'll try to extract string list from it
            options = self._extract_options(opt_expr)

        return InputDecl(
            var_name=var_name,
            input_type=input_type,
            default=default,
            title=str(title) if title else var_name,
            min_val=float(min_val) if min_val is not None else None,
            max_val=float(max_val) if max_val is not None else None,
            step=float(step) if step is not None else None,
            options=options,
            group=str(group) if group else "",
        )

    def _extract_options(self, expr) -> Optional[list[str]]:
        """Try to extract a list of string options from an expression."""
        if isinstance(expr, FuncCall):
            # Could be list literal parsed as FuncCall
            return [str(self._expr_to_value(a)) for a in expr.args]
        if isinstance(expr, Identifier):
            return None
        return None

    def _expr_to_value(self, expr) -> Any:
        """Convert a simple expression to a Python value."""
        if expr is None:
            return None
        if isinstance(expr, NumberLit):
            v = expr.value
            return int(v) if v == int(v) else v
        if isinstance(expr, StringLit):
            return expr.value
        if isinstance(expr, BoolLit):
            return expr.value
        if isinstance(expr, Identifier):
            name = expr.name
            if name == "true":
                return True
            if name == "false":
                return False
            return name
        if isinstance(expr, UnaryOp) and expr.op == "-" and isinstance(expr.operand, NumberLit):
            v = -expr.operand.value
            return int(v) if v == int(v) else v
        # For complex expressions, return a string representation
        return self._expr_to_str(expr)

    def _expr_to_str(self, expr) -> str:
        """Convert expression to a string representation."""
        if isinstance(expr, NumberLit):
            v = expr.value
            return str(int(v)) if v == int(v) else str(v)
        if isinstance(expr, StringLit):
            return expr.value
        if isinstance(expr, BoolLit):
            return str(expr.value).lower()
        if isinstance(expr, Identifier):
            return expr.name
        if isinstance(expr, BinaryOp):
            return f"{self._expr_to_str(expr.left)} {expr.op} {self._expr_to_str(expr.right)}"
        if isinstance(expr, UnaryOp):
            return f"{expr.op} {self._expr_to_str(expr.operand)}"
        if isinstance(expr, FuncCall):
            args_str = ", ".join(self._expr_to_str(a) for a in expr.args)
            kw_str = ", ".join(f"{k}={self._expr_to_str(v)}" for k, v in expr.kwargs.items())
            all_args = ", ".join(filter(None, [args_str, kw_str]))
            return f"{expr.name}({all_args})"
        if isinstance(expr, IndexAccess):
            return f"{self._expr_to_str(expr.expr)}[{self._expr_to_str(expr.index)}]"
        if isinstance(expr, Ternary):
            return (
                f"{self._expr_to_str(expr.condition)} ? "
                f"{self._expr_to_str(expr.true_val)} : "
                f"{self._expr_to_str(expr.false_val)}"
            )
        return str(expr)

    # ------------------------------------------------------------------
    # Switch block (expression or statement level)
    # ------------------------------------------------------------------

    def _parse_switch_block(self) -> SwitchBlock:
        """Parse: switch expr \\n INDENT case1 => result \\n ... DEDENT"""
        self._expect(TokenType.SWITCH)
        expr = self._parse_expression()
        self._skip_newlines()

        cases: list[tuple[Expr, list]] = []
        default: Optional[list] = None

        if self._cur().type == TokenType.INDENT:
            self._expect(TokenType.INDENT)
            self._skip_newlines()

            while self._cur().type not in (TokenType.DEDENT, TokenType.EOF):
                # Default case: => result (no match value)
                if self._cur().type == TokenType.ASSIGN and self._peek(1).type == TokenType.GT:
                    # => is ASSIGN followed by GT
                    self._advance()  # =
                    self._advance()  # >
                    result_expr = self._parse_expression()
                    default = [result_expr]
                else:
                    match_val = self._parse_expression()
                    # Expect =>
                    self._expect(TokenType.ASSIGN)
                    self._expect(TokenType.GT)
                    result_expr = self._parse_expression()
                    cases.append((match_val, [result_expr]))
                self._skip_newlines()

            self._match(TokenType.DEDENT)

        return SwitchBlock(expr=expr, cases=cases, default=default)

    # ------------------------------------------------------------------
    # Expression parsing (precedence climbing)
    # ------------------------------------------------------------------

    def _parse_expression(self) -> Expr:
        """Entry point for expression parsing. Handles ternary at the top."""
        return self._parse_ternary()

    def _parse_ternary(self) -> Expr:
        """condition ? true_val : false_val"""
        expr = self._parse_or()
        if self._cur().type == TokenType.QUESTION:
            self._advance()
            true_val = self._parse_ternary()
            self._expect(TokenType.COLON)
            false_val = self._parse_ternary()
            return Ternary(condition=expr, true_val=true_val, false_val=false_val)
        return expr

    def _parse_or(self) -> Expr:
        left = self._parse_and()
        while self._cur().type == TokenType.OR:
            self._advance()
            right = self._parse_and()
            left = BinaryOp(left, "or", right)
        return left

    def _parse_and(self) -> Expr:
        left = self._parse_not()
        while self._cur().type == TokenType.AND:
            self._advance()
            right = self._parse_not()
            left = BinaryOp(left, "and", right)
        return left

    def _parse_not(self) -> Expr:
        if self._cur().type == TokenType.NOT:
            self._advance()
            operand = self._parse_not()
            return UnaryOp("not", operand)
        return self._parse_comparison()

    def _parse_comparison(self) -> Expr:
        left = self._parse_additive()
        comp_types = {
            TokenType.GT: ">",
            TokenType.LT: "<",
            TokenType.GTE: ">=",
            TokenType.LTE: "<=",
            TokenType.EQ: "==",
            TokenType.NEQ: "!=",
        }
        while self._cur().type in comp_types:
            op = comp_types[self._cur().type]
            self._advance()
            right = self._parse_additive()
            left = BinaryOp(left, op, right)
        return left

    def _parse_additive(self) -> Expr:
        left = self._parse_multiplicative()
        while self._cur().type in (TokenType.PLUS, TokenType.MINUS):
            op = "+" if self._cur().type == TokenType.PLUS else "-"
            self._advance()
            right = self._parse_multiplicative()
            left = BinaryOp(left, op, right)
        return left

    def _parse_multiplicative(self) -> Expr:
        left = self._parse_unary()
        while self._cur().type in (TokenType.STAR, TokenType.SLASH):
            op = "*" if self._cur().type == TokenType.STAR else "/"
            self._advance()
            right = self._parse_unary()
            left = BinaryOp(left, op, right)
        return left

    def _parse_unary(self) -> Expr:
        if self._cur().type == TokenType.MINUS:
            self._advance()
            operand = self._parse_unary()
            return UnaryOp("-", operand)
        if self._cur().type == TokenType.NOT:
            self._advance()
            operand = self._parse_unary()
            return UnaryOp("not", operand)
        return self._parse_postfix()

    def _parse_postfix(self) -> Expr:
        """Parse primary expression followed by optional [index] access."""
        expr = self._parse_primary()
        while self._cur().type == TokenType.LBRACKET:
            self._advance()
            index = self._parse_expression()
            self._expect(TokenType.RBRACKET)
            expr = IndexAccess(expr, index)
        return expr

    def _parse_primary(self) -> Expr:
        tok = self._cur()

        # Number literal
        if tok.type == TokenType.NUMBER:
            self._advance()
            val = float(tok.value)
            return NumberLit(val)

        # String literal
        if tok.type == TokenType.STRING:
            self._advance()
            return StringLit(tok.value)

        # Boolean literals
        if tok.type == TokenType.TRUE:
            self._advance()
            return BoolLit(True)
        if tok.type == TokenType.FALSE:
            self._advance()
            return BoolLit(False)

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        # List literal [a, b, c] -- used in request.security
        if tok.type == TokenType.LBRACKET:
            self._advance()
            elements: list[Expr] = []
            if self._cur().type != TokenType.RBRACKET:
                elements.append(self._parse_expression())
                while self._match(TokenType.COMMA):
                    elements.append(self._parse_expression())
            self._expect(TokenType.RBRACKET)
            # Represent as a FuncCall to a pseudo-function "__list__"
            return FuncCall("__list__", elements, {})

        # switch as expression
        if tok.type == TokenType.SWITCH:
            return self._parse_switch_block()

        # na keyword (PineScript null/NaN)
        if tok.type == TokenType.IDENT and tok.value == "na":
            self._advance()
            return Identifier("na")

        # Identifier or function call (possibly dotted)
        if tok.type == TokenType.IDENT:
            return self._parse_ident_or_call()

        # Strategy keyword used as part of expression (strategy.long, strategy.position_size)
        if tok.type == TokenType.STRATEGY:
            self._advance()
            if self._cur().type == TokenType.DOT:
                self._advance()
                member = self._expect(TokenType.IDENT).value
                name = f"strategy.{member}"
                # strategy.entry(...) etc. at expression level
                if self._cur().type == TokenType.LPAREN:
                    return self._parse_func_call(name)
                return Identifier(name)
            return Identifier("strategy")

        # Input keyword used in expression (input.int, etc.)
        if tok.type == TokenType.INPUT:
            self._advance()
            if self._cur().type == TokenType.DOT:
                self._advance()
                member = self._expect(TokenType.IDENT).value
                name = f"input.{member}"
                if self._cur().type == TokenType.LPAREN:
                    return self._parse_func_call(name)
                return Identifier(name)
            return Identifier("input")

        # If nothing matches, return an error identifier
        self.warnings.append(
            f"Unexpected token in expression: {tok.type.name} ({tok.value!r}) "
            f"at line {tok.line}:{tok.col}"
        )
        self._advance()
        return Identifier(f"__error_{tok.value}__")

    def _parse_ident_or_call(self) -> Expr:
        """Parse identifier, possibly dotted, possibly followed by (args)."""
        name = self._read_dotted_name()

        # Function call
        if self._cur().type == TokenType.LPAREN:
            return self._parse_func_call(name)

        return Identifier(name)

    def _parse_func_call(self, name: str) -> FuncCall:
        """Parse function call arguments: name(arg1, arg2, key=val)."""
        self._expect(TokenType.LPAREN)
        args, kwargs = self._parse_call_args()
        self._expect(TokenType.RPAREN)
        return FuncCall(name, args, kwargs)

    def _parse_call_args(self) -> tuple[list[Expr], dict[str, Expr]]:
        """Parse comma-separated call arguments (positional and keyword).

        Returns (positional_args, keyword_args).
        """
        args: list[Expr] = []
        kwargs: dict[str, Expr] = {}

        if self._cur().type == TokenType.RPAREN:
            return args, kwargs

        self._skip_newlines()

        while True:
            self._skip_newlines()
            if self._cur().type == TokenType.RPAREN:
                break

            # Check for keyword argument: ident = expr
            # Need to distinguish from positional expr that starts with ident
            if (self._cur().type == TokenType.IDENT
                    and self._peek(1).type == TokenType.ASSIGN
                    and self._peek(2).type != TokenType.ASSIGN):
                # keyword arg
                key = self._advance().value
                self._advance()  # skip =
                val = self._parse_expression()
                kwargs[key] = val
            else:
                # positional arg
                val = self._parse_expression()
                args.append(val)

            self._skip_newlines()
            if not self._match(TokenType.COMMA):
                break

        self._skip_newlines()
        return args, kwargs
