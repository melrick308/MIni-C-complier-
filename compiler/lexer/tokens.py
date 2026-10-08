"""Token types. A TokenType's value is the terminal name used in the grammar."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..common.source import Span


class TokenType(str, Enum):
    IDENTIFIER = "IDENTIFIER"
    NUMBER = "NUMBER"
    STRING = "STRING"
    # keywords
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    VOID = "void"
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    DO = "do"
    FOR = "for"
    RETURN = "return"
    BREAK = "break"
    CONTINUE = "continue"
    PRINT = "print"
    TRUE = "true"
    FALSE = "false"
    # operators
    PLUS = "PLUS"
    MINUS = "MINUS"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"
    MODULO = "MODULO"
    LESS = "LESS"
    LESS_EQUAL = "LESS_EQUAL"
    GREATER = "GREATER"
    GREATER_EQUAL = "GREATER_EQUAL"
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    ASSIGN = "ASSIGN"
    PLUS_ASSIGN = "PLUS_ASSIGN"
    MINUS_ASSIGN = "MINUS_ASSIGN"
    STAR_ASSIGN = "STAR_ASSIGN"
    SLASH_ASSIGN = "SLASH_ASSIGN"
    INCREMENT = "INCREMENT"
    DECREMENT = "DECREMENT"
    # delimiters
    LEFT_PAREN = "LEFT_PAREN"
    RIGHT_PAREN = "RIGHT_PAREN"
    LEFT_BRACE = "LEFT_BRACE"
    RIGHT_BRACE = "RIGHT_BRACE"
    COMMA = "COMMA"
    SEMICOLON = "SEMICOLON"
    EOF = "EOF"

    def __str__(self) -> str:
        return self.value


T = TokenType

KEYWORDS: dict[str, TokenType] = {
    t.value: t
    for t in (
        T.INT, T.FLOAT, T.BOOL, T.VOID, T.IF, T.ELSE, T.WHILE, T.DO, T.FOR,
        T.RETURN, T.BREAK, T.CONTINUE, T.PRINT, T.TRUE, T.FALSE,
    )
}

# Longest operators first so that maximal munch works by simple prefix matching.
OPERATORS: list[tuple[str, TokenType]] = [
    ("==", T.EQUAL), ("!=", T.NOT_EQUAL), ("<=", T.LESS_EQUAL), (">=", T.GREATER_EQUAL),
    ("&&", T.AND), ("||", T.OR), ("++", T.INCREMENT), ("--", T.DECREMENT),
    ("+=", T.PLUS_ASSIGN), ("-=", T.MINUS_ASSIGN), ("*=", T.STAR_ASSIGN), ("/=", T.SLASH_ASSIGN),
    ("+", T.PLUS), ("-", T.MINUS), ("*", T.MULTIPLY), ("/", T.DIVIDE), ("%", T.MODULO),
    ("<", T.LESS), (">", T.GREATER), ("=", T.ASSIGN), ("!", T.NOT),
    ("(", T.LEFT_PAREN), (")", T.RIGHT_PAREN), ("{", T.LEFT_BRACE), ("}", T.RIGHT_BRACE),
    (",", T.COMMA), (";", T.SEMICOLON),
]

SYMBOL_TEXT: dict[TokenType, str] = {tt: text for text, tt in OPERATORS}

# How a terminal is written inside grammar productions.
GRAMMAR_SYMBOL: dict[TokenType, str] = {
    **SYMBOL_TEXT,
    **{tt: tt.value for tt in KEYWORDS.values()},
    T.IDENTIFIER: "id",
    T.NUMBER: "num",
    T.STRING: "str",
    T.EOF: "$",
}

DELIMITERS = {T.LEFT_PAREN, T.RIGHT_PAREN, T.LEFT_BRACE, T.RIGHT_BRACE, T.COMMA, T.SEMICOLON}


def display(tt: TokenType) -> str:
    """Human-readable name used in 'expected ...' lists."""
    if tt is T.IDENTIFIER:
        return "identifier"
    if tt is T.NUMBER:
        return "number"
    if tt is T.STRING:
        return "string"
    if tt is T.EOF:
        return "end of input"
    return f"'{GRAMMAR_SYMBOL[tt]}'"


def category(tt: TokenType) -> str:
    if tt in KEYWORDS.values():
        return "keyword"
    if tt in (T.IDENTIFIER, T.NUMBER, T.STRING, T.EOF):
        return {T.IDENTIFIER: "identifier", T.NUMBER: "number", T.STRING: "string", T.EOF: "eof"}[tt]
    if tt in DELIMITERS:
        return "delimiter"
    return "operator"


ORDER = {tt: i for i, tt in enumerate(TokenType)}


def sorted_display(types) -> list[str]:
    return [display(t) for t in sorted(types, key=lambda t: ORDER[t])]


@dataclass(frozen=True)
class Token:
    type: TokenType
    lexeme: str
    span: Span
    index: int
    value: object = None

    @property
    def line(self) -> int:
        return self.span.start.line

    @property
    def col(self) -> int:
        return self.span.start.col

    def describe(self) -> str:
        """How the token is quoted in messages."""
        return "end of input" if self.type is T.EOF else f"'{self.lexeme}'"

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "type": self.type.value if self.type not in KEYWORDS.values() else "KEYWORD",
            "token": _token_name(self.type),
            "category": category(self.type),
            "lexeme": self.lexeme,
            "line": self.line,
            "col": self.col,
            "span": self.span.to_dict(),
        }


def _token_name(tt: TokenType) -> str:
    if tt in KEYWORDS.values():
        return f"KW_{tt.value.upper()}"
    return tt.value
