"""Regex-based tokenizer for a subset of TradingView PineScript v5."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Keywords
    STRATEGY = auto()
    INPUT = auto()
    IF = auto()
    ELSE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    TRUE = auto()
    FALSE = auto()
    VAR = auto()
    SWITCH = auto()

    # Identifiers & literals
    IDENT = auto()
    NUMBER = auto()
    STRING = auto()

    # Operators
    ASSIGN = auto()       # =
    REASSIGN = auto()     # :=
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    GT = auto()
    LT = auto()
    GTE = auto()
    LTE = auto()
    EQ = auto()           # ==
    NEQ = auto()          # !=
    QUESTION = auto()     # ?
    COLON = auto()        # :

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    DOT = auto()

    # Special
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()
    COMMENT = auto()


KEYWORDS: dict[str, TokenType] = {
    "strategy": TokenType.STRATEGY,
    "input": TokenType.INPUT,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "var": TokenType.VAR,
    "switch": TokenType.SWITCH,
}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:{self.col})"


# Order matters: longer operators must come before shorter ones.
_TOKEN_SPEC: list[tuple[str, str]] = [
    ("COMMENT",   r"//.*"),
    ("STRING_DQ", r'"[^"]*"'),
    ("STRING_SQ", r"'[^']*'"),
    ("NUMBER",    r"\d+\.?\d*"),
    ("REASSIGN",  r":="),
    ("GTE",       r">="),
    ("LTE",       r"<="),
    ("EQ",        r"=="),
    ("NEQ",       r"!="),
    ("ASSIGN",    r"="),
    ("GT",        r">"),
    ("LT",        r"<"),
    ("PLUS",      r"\+"),
    ("MINUS",     r"-"),
    ("STAR",      r"\*"),
    ("SLASH",     r"/"),
    ("QUESTION",  r"\?"),
    ("COLON",     r":"),
    ("LPAREN",    r"\("),
    ("RPAREN",    r"\)"),
    ("LBRACKET",  r"\["),
    ("RBRACKET",  r"\]"),
    ("COMMA",     r","),
    ("DOT",       r"\."),
    ("IDENT",     r"[A-Za-z_#][A-Za-z0-9_]*"),
    ("WS",        r"[ \t]+"),
    ("MISMATCH",  r"."),
]

_MASTER_PAT = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in _TOKEN_SPEC))

_SIMPLE_MAP: dict[str, TokenType] = {
    "REASSIGN": TokenType.REASSIGN,
    "GTE": TokenType.GTE,
    "LTE": TokenType.LTE,
    "EQ": TokenType.EQ,
    "NEQ": TokenType.NEQ,
    "ASSIGN": TokenType.ASSIGN,
    "GT": TokenType.GT,
    "LT": TokenType.LT,
    "PLUS": TokenType.PLUS,
    "MINUS": TokenType.MINUS,
    "STAR": TokenType.STAR,
    "SLASH": TokenType.SLASH,
    "QUESTION": TokenType.QUESTION,
    "COLON": TokenType.COLON,
    "LPAREN": TokenType.LPAREN,
    "RPAREN": TokenType.RPAREN,
    "LBRACKET": TokenType.LBRACKET,
    "RBRACKET": TokenType.RBRACKET,
    "COMMA": TokenType.COMMA,
    "DOT": TokenType.DOT,
}


def _tokenize_line(line: str, line_num: int) -> list[Token]:
    """Tokenize a single source line (no newline character)."""
    tokens: list[Token] = []
    for mo in _MASTER_PAT.finditer(line):
        kind = mo.lastgroup
        value = mo.group()
        col = mo.start() + 1  # 1-based

        if kind == "WS":
            continue

        if kind == "COMMENT":
            tokens.append(Token(TokenType.COMMENT, value, line_num, col))
            continue

        if kind in ("STRING_DQ", "STRING_SQ"):
            # Strip surrounding quotes
            tokens.append(Token(TokenType.STRING, value[1:-1], line_num, col))
            continue

        if kind == "NUMBER":
            tokens.append(Token(TokenType.NUMBER, value, line_num, col))
            continue

        if kind == "IDENT":
            # Check if it's a keyword
            low = value.lower()
            if low in KEYWORDS:
                tokens.append(Token(KEYWORDS[low], value, line_num, col))
            else:
                tokens.append(Token(TokenType.IDENT, value, line_num, col))
            continue

        if kind in _SIMPLE_MAP:
            tokens.append(Token(_SIMPLE_MAP[kind], value, line_num, col))
            continue

        if kind == "MISMATCH":
            # Skip unknown characters silently
            continue

    return tokens


def _measure_indent(line: str) -> int:
    """Return the number of leading spaces (tabs count as 4 spaces)."""
    count = 0
    for ch in line:
        if ch == " ":
            count += 1
        elif ch == "\t":
            count += 4
        else:
            break
    return count


def tokenize(source: str) -> list[Token]:
    """Tokenize PineScript source code into a flat list of tokens.

    - Tracks indentation and emits INDENT / DEDENT tokens for block detection.
    - Filters out COMMENT tokens.
    - Preserves NEWLINE tokens between logical lines.
    - Handles multi-line expressions connected by trailing operators or
      continuation (line ending with a comma or binary operator).
    """
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    all_tokens: list[Token] = []

    indent_stack: list[int] = [0]
    paren_depth = 0  # track nested () [] for continuation lines
    prev_was_newline = True

    for line_num_0, raw_line in enumerate(lines):
        line_num = line_num_0 + 1

        # Strip trailing whitespace but keep leading whitespace
        stripped = raw_line.rstrip()

        # Completely blank or comment-only lines
        if stripped == "" or stripped.lstrip().startswith("//"):
            # Still emit a newline so the parser knows lines are separated
            if all_tokens and all_tokens[-1].type != TokenType.NEWLINE:
                all_tokens.append(Token(TokenType.NEWLINE, "\\n", line_num, 1))
            prev_was_newline = True
            continue

        # Measure indentation
        indent_level = _measure_indent(raw_line)

        # Continuation lines inside parentheses or brackets skip indent logic
        if paren_depth > 0:
            line_tokens = _tokenize_line(stripped, line_num)
            # Update paren depth
            for t in line_tokens:
                if t.type in (TokenType.LPAREN, TokenType.LBRACKET):
                    paren_depth += 1
                elif t.type in (TokenType.RPAREN, TokenType.RBRACKET):
                    paren_depth -= 1
            # Filter comments
            all_tokens.extend(t for t in line_tokens if t.type != TokenType.COMMENT)
            continue

        # Check if the previous line ended with a continuation operator
        # (and, or, +, -, *, /, comma, =, :=, comparison ops)
        is_continuation = False
        if all_tokens:
            # Walk backwards past NEWLINEs to find last real token
            last_real = None
            prev_real = None
            for t in reversed(all_tokens):
                if t.type != TokenType.NEWLINE:
                    if last_real is None:
                        last_real = t
                    else:
                        prev_real = t
                        break
            # Do not treat Pine function arrows (`=>`) as line continuation.
            if last_real and last_real.type == TokenType.GT and prev_real and prev_real.type == TokenType.ASSIGN:
                last_real = None
            if last_real and last_real.type in (
                TokenType.AND, TokenType.OR,
                TokenType.PLUS, TokenType.MINUS,
                TokenType.STAR, TokenType.SLASH,
                TokenType.COMMA,
                TokenType.GT, TokenType.LT, TokenType.GTE, TokenType.LTE,
                TokenType.EQ, TokenType.NEQ,
                TokenType.ASSIGN, TokenType.REASSIGN,
                TokenType.QUESTION, TokenType.COLON,
            ):
                is_continuation = True

        if is_continuation:
            # This line continues the previous statement; skip indent/dedent.
            line_tokens = _tokenize_line(stripped, line_num)
            for t in line_tokens:
                if t.type in (TokenType.LPAREN, TokenType.LBRACKET):
                    paren_depth += 1
                elif t.type in (TokenType.RPAREN, TokenType.RBRACKET):
                    paren_depth -= 1
            all_tokens.extend(t for t in line_tokens if t.type != TokenType.COMMENT)
            continue

        # Emit indentation changes
        if indent_level > indent_stack[-1]:
            indent_stack.append(indent_level)
            all_tokens.append(Token(TokenType.INDENT, "", line_num, 1))
        else:
            while indent_level < indent_stack[-1]:
                indent_stack.pop()
                all_tokens.append(Token(TokenType.DEDENT, "", line_num, 1))
                # Emit a newline before dedent if needed
            # Ensure there's a NEWLINE separator between statements at same level
            if all_tokens and all_tokens[-1].type not in (
                TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT
            ):
                all_tokens.append(Token(TokenType.NEWLINE, "\\n", line_num, 1))

        # Tokenize the line
        line_tokens = _tokenize_line(stripped, line_num)
        for t in line_tokens:
            if t.type in (TokenType.LPAREN, TokenType.LBRACKET):
                paren_depth += 1
            elif t.type in (TokenType.RPAREN, TokenType.RBRACKET):
                paren_depth -= 1

        # Filter comments
        all_tokens.extend(t for t in line_tokens if t.type != TokenType.COMMENT)

        # Add trailing newline
        all_tokens.append(Token(TokenType.NEWLINE, "\\n", line_num, 0))
        prev_was_newline = True

    # Close any remaining indentation levels
    while len(indent_stack) > 1:
        indent_stack.pop()
        all_tokens.append(Token(TokenType.DEDENT, "", len(lines), 1))

    all_tokens.append(Token(TokenType.EOF, "", len(lines), 0))

    return all_tokens
