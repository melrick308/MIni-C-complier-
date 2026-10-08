"""Structured diagnostics shared by every compiler phase, plus the error-code catalog."""

from __future__ import annotations

from dataclasses import dataclass

from .source import Span

ERROR = "error"
WARNING = "warning"

LEXICAL = "lexical"
SYNTAX = "syntax"
SEMANTIC = "semantic"
RUNTIME = "runtime"
INPUT = "input"

# code -> short description (rendered into docs/error-catalog.md)
CATALOG = {
    # lexical
    "E_LEX_INVALID_CHAR": "A character that is not part of the language",
    "E_LEX_MALFORMED_NUMBER": "A number such as '3.' that has no digits after the decimal point",
    "E_LEX_UNTERMINATED_STRING": "A string literal without its closing quote",
    "E_LEX_UNTERMINATED_COMMENT": "A /* comment without its closing */",
    # input
    "E_INPUT_TOO_LONG": "Source exceeds the maximum allowed size",
    # syntax
    "E_SYN_EMPTY": "Empty expression",
    "E_SYN_UNEXPECTED_TOKEN": "A token that cannot appear at this point",
    "E_SYN_UNEXPECTED_EOF": "Input ended while more was expected",
    "E_SYN_EXPECTED": "A specific token was required but another was found",
    "E_SYN_MISSING_SEMICOLON": "A statement is not terminated with ';'",
    "E_SYN_MISSING_RPAREN": "A '(' without its matching ')'",
    "E_SYN_UNMATCHED_RPAREN": "A ')' without a matching '('",
    "E_SYN_MISSING_RBRACE": "A '{' without its matching '}'",
    "E_SYN_EMPTY_PARENS": "Parentheses with nothing inside",
    "E_SYN_MISSING_OPERATOR": "Two operands without an operator between them",
    "E_SYN_UNARY_NOT_SUPPORTED": "Unary minus/plus in the arithmetic grammar",
    "E_SYN_CHAINED_COMPARISON": "Comparisons such as a < b < c (non-associative)",
    "E_SYN_ELSE_WITHOUT_IF": "'else' that does not follow an if statement",
    "E_SYN_NESTED_FUNCTION": "Function declared inside a block",
    "E_SYN_EXPECTED_STATEMENT": "A statement was expected",
    "E_SYN_TOO_DEEP": "Nesting deeper than the allowed limit",
    "E_SYN_TOO_COMPLEX": "Expression with too many nested operators",
    "E_SYN_TOO_MANY_ERRORS": "Parsing stopped after too many errors",
    # semantic
    "E_SEM_UNDECLARED": "Use of a name that was never declared",
    "E_SEM_REDECLARED": "A name declared twice in the same scope",
    "E_SEM_TYPE_MISMATCH": "Value type does not match the declared type",
    "E_SEM_LOSSY_ASSIGN": "Assigning a float to an int would lose precision",
    "E_SEM_CONDITION_NOT_BOOL": "Condition of if/while/for is not bool",
    "E_SEM_INVALID_OPERANDS": "Operator applied to operands of the wrong type",
    "E_SEM_NOT_A_FUNCTION": "Calling something that is not a function",
    "E_SEM_NOT_A_VARIABLE": "Using a function name as a variable",
    "E_SEM_ARG_COUNT": "Wrong number of arguments in a call",
    "E_SEM_ARG_TYPE": "Argument type does not match the parameter type",
    "E_SEM_RETURN_TYPE": "Returned value does not match the function's return type",
    "E_SEM_MISSING_RETURN": "Non-void function can finish without returning a value",
    "E_SEM_RETURN_OUTSIDE_FUNCTION": "'return' used outside a function",
    "E_SEM_BREAK_OUTSIDE_LOOP": "'break' or 'continue' used outside a loop",
    "E_SEM_VOID_VALUE": "A void function used where a value is needed",
    "W_SEM_UNUSED": "Variable declared but its value is never read",
    # runtime
    "E_RT_DIV_ZERO": "Division by zero",
    "E_RT_MOD_ZERO": "Modulo by zero",
    "E_RT_OVERFLOW": "Numeric result is too large to represent",
    "E_RT_STEP_LIMIT": "Program executed too many instructions (possible infinite loop)",
    "E_RT_TIME_LIMIT": "Program ran for too long",
    "E_RT_OUTPUT_LIMIT": "Program printed too many lines",
    "E_RT_CALL_DEPTH": "Too many nested calls (possible infinite recursion)",
    "E_RT_NO_RETURN": "Non-void function ended without returning a value",
    "E_RT_UNINITIALIZED": "A variable was read before it had a value",
    "E_RT_INTERNAL": "Internal virtual machine error",
}


@dataclass
class Diagnostic:
    severity: str
    phase: str
    code: str
    message: str
    span: Span | None = None
    found: str | None = None
    expected: list[str] | None = None
    hint: str | None = None
    related_span: Span | None = None
    related_message: str | None = None

    def to_dict(self) -> dict:
        data = {
            "severity": self.severity,
            "phase": self.phase,
            "code": self.code,
            "message": self.message,
            "span": self.span.to_dict() if self.span else None,
            "line": self.span.start.line if self.span else None,
            "col": self.span.start.col if self.span else None,
            "found": self.found,
            "expected": self.expected,
            "hint": self.hint,
            "related": None,
        }
        if self.related_span is not None:
            data["related"] = {"span": self.related_span.to_dict(), "message": self.related_message}
        return data


class CompileError(Exception):
    """Raised by a phase that cannot continue; carries one diagnostic."""

    def __init__(self, diagnostic: Diagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def sort_diagnostics(diags: list[Diagnostic]) -> list[Diagnostic]:
    def key(d: Diagnostic):
        if d.span is None:
            return (1, 0, 0)
        return (0, d.span.start.line, d.span.start.col)

    return sorted(diags, key=key)
