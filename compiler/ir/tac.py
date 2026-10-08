"""Three Address Code instructions (see docs/ir-spec.md)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..common.source import Span

TEMP_RE = re.compile(r"^t\d+$")


@dataclass(frozen=True)
class Str:
    """A string constant operand (only used by print)."""

    value: str


Operand = str | int | float | bool | Str


def is_name(op: Operand) -> bool:
    return isinstance(op, str)


def is_temp(op: Operand) -> bool:
    return isinstance(op, str) and TEMP_RE.match(op) is not None


def format_number(value, *, mode: str = "program") -> str:
    """Program mode keeps '.0' on whole floats so the type stays visible; expression mode
    (the original analyzer) prints 5.0 as 5."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value != value or value in (float("inf"), float("-inf")):
        return str(value)
    if value.is_integer() and abs(value) < 1e16:
        return f"{int(value)}" if mode == "expression" else f"{value:.1f}"
    return f"{value:.10g}"


def fmt(op: Operand | None) -> str:
    if op is None:
        return ""
    if isinstance(op, Str):
        return json.dumps(op.value)
    if isinstance(op, (bool, int, float)):
        return format_number(op)
    return op


@dataclass(eq=False)
class Instr:
    op: str  # assign binop unop label goto iffalse iftrue param call return print func endfunc halt
    result: str | None = None
    arg1: Operand | None = None
    arg2: Operand | None = None
    operator: str | None = None
    label: str | None = None  # label name (label) or jump target (goto/iffalse/iftrue)
    name: str | None = None  # function name (call/func)
    args: list = field(default_factory=list)  # print operands / function parameters
    span: Span | None = None
    ast_id: str | None = None
    func: str = "main"
    index: int = -1

    def text(self) -> str:
        op = self.op
        if op == "assign":
            return f"{self.result} = {fmt(self.arg1)}"
        if op == "binop":
            return f"{self.result} = {fmt(self.arg1)} {self.operator} {fmt(self.arg2)}"
        if op == "unop":
            return f"{self.result} = {self.operator} {fmt(self.arg1)}"
        if op == "label":
            return f"{self.label}:"
        if op == "goto":
            return f"goto {self.label}"
        if op == "iffalse":
            return f"ifFalse {fmt(self.arg1)} goto {self.label}"
        if op == "iftrue":
            return f"if {fmt(self.arg1)} goto {self.label}"
        if op == "param":
            return f"param {fmt(self.arg1)}"
        if op == "call":
            call = f"call {self.name}, {self.arg2}"
            return f"{self.result} = {call}" if self.result else call
        if op == "return":
            return f"return {fmt(self.arg1)}" if self.arg1 is not None else "return"
        if op == "print":
            return "print " + ", ".join(fmt(a) for a in self.args)
        if op == "func":
            return f"func {self.name}({', '.join(self.args)}):"
        if op == "endfunc":
            return f"endfunc {self.name}"
        if op == "halt":
            return "halt"
        raise ValueError(op)

    def quadruple(self) -> dict:
        op = self.op
        quad = {"op": op, "arg1": "", "arg2": "", "result": ""}
        if op == "assign":
            quad.update(op="=", arg1=fmt(self.arg1), result=self.result)
        elif op in ("binop", "unop"):
            quad.update(op=self.operator, arg1=fmt(self.arg1), arg2=fmt(self.arg2),
                        result=self.result)
        elif op in ("label", "goto"):
            quad.update(result=self.label)
        elif op in ("iffalse", "iftrue"):
            quad.update(op="ifFalse" if op == "iffalse" else "if", arg1=fmt(self.arg1),
                        result=self.label)
        elif op == "param":
            quad.update(arg1=fmt(self.arg1))
        elif op == "call":
            quad.update(arg1=self.name, arg2=str(self.arg2), result=self.result or "")
        elif op == "return":
            quad.update(arg1=fmt(self.arg1))
        elif op == "print":
            quad.update(arg1=", ".join(fmt(a) for a in self.args))
        elif op in ("func", "endfunc"):
            quad.update(arg1=self.name, arg2=str(len(self.args)) if op == "func" else "")
        return quad

    def is_jump(self) -> bool:
        return self.op in ("goto", "iffalse", "iftrue")

    def defines(self) -> str | None:
        return self.result if self.op in ("assign", "binop", "unop", "call") else None

    def uses(self) -> list[str]:
        ops = [self.arg1, self.arg2] if self.op != "print" else list(self.args)
        if self.op == "call":
            ops = []
        return [o for o in ops if is_name(o)]

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "op": self.op,
            "text": self.text(),
            "func": self.func,
            "label": self.label,
            "result": self.result,
            "quad": self.quadruple(),
            "span": self.span.to_dict() if self.span else None,
            "line": self.span.start.line if self.span else None,
            "ast_id": self.ast_id,
        }
