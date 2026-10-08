"""MiniC type rules."""

from __future__ import annotations

INT = "int"
FLOAT = "float"
BOOL = "bool"
VOID = "void"
STRING = "string"
ERROR = "error"  # produced after an error, silently accepted to avoid cascades

NUMERIC = {INT, FLOAT}
ARITHMETIC_OPS = {"+", "-", "*", "/"}
RELATIONAL_OPS = {"<", "<=", ">", ">="}
EQUALITY_OPS = {"==", "!="}
LOGICAL_OPS = {"&&", "||"}

ZERO_VALUE = {INT: 0, FLOAT: 0.0, BOOL: False}


def binary_result(op: str, left: str, right: str) -> str | None:
    """Result type of `left op right`, or None if the operands are invalid."""
    if ERROR in (left, right):
        return ERROR
    if op in ARITHMETIC_OPS:
        if left in NUMERIC and right in NUMERIC:
            return FLOAT if FLOAT in (left, right) else INT
        return None
    if op == "%":
        return INT if left == INT and right == INT else None
    if op in RELATIONAL_OPS:
        return BOOL if left in NUMERIC and right in NUMERIC else None
    if op in EQUALITY_OPS:
        if (left in NUMERIC and right in NUMERIC) or (left == BOOL and right == BOOL):
            return BOOL
        return None
    if op in LOGICAL_OPS:
        return BOOL if left == BOOL and right == BOOL else None
    return None


def unary_result(op: str, operand: str) -> str | None:
    if operand == ERROR:
        return ERROR
    if op == "-":
        return operand if operand in NUMERIC else None
    if op == "!":
        return BOOL if operand == BOOL else None
    return None


def assignable(target: str, value: str) -> str:
    """'ok', 'widen' (int → float), 'lossy' (float → int) or 'mismatch'."""
    if ERROR in (target, value) or target == value:
        return "ok"
    if target == FLOAT and value == INT:
        return "widen"
    if target == INT and value == FLOAT:
        return "lossy"
    return "mismatch"
