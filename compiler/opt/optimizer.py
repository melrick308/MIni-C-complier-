"""Machine-independent optimisation passes over TAC.

Passes (repeated until nothing changes):
  1. constant folding + constant propagation inside each basic block
  2. algebraic simplification (x + 0, x * 1, x - 0, x / 1)
  3. constant conditional jumps → goto / removed
  4. dead temporary elimination
  5. unreachable code elimination and jump-to-next-label removal
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..ir.tac import Instr, Str, is_name, is_temp
from ..ir.tac_gen import IRProgram
from ..runtime.vm import apply_unop, trunc_div


@dataclass
class OptimizationResult:
    ir: IRProgram
    removed: int
    changes: dict[str, int] = field(default_factory=dict)
    # original instruction index -> what happened ("removed" | "rewritten")
    marks: dict[int, str] = field(default_factory=dict)


def _const(op) -> bool:
    return isinstance(op, (bool, int, float)) and not isinstance(op, Str)


def _fold(operator: str, a, b):
    """Evaluate a constant binary operation with VM semantics; None if unsafe."""
    try:
        if operator == "+":
            return a + b
        if operator == "-":
            return a - b
        if operator == "*":
            return a * b
        if operator == "/":
            if b == 0:
                return None
            if isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool):
                return trunc_div(a, b)
            return a / b
        if operator == "%":
            if b == 0:
                return None
            return a - b * trunc_div(a, b)
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b,
                "!=": a != b}.get(operator)
    except (OverflowError, TypeError):
        return None


class Optimizer:
    def __init__(self, ir: IRProgram):
        self.ir = ir
        self.code: list[Instr] = [copy.copy(i) for i in ir.instrs]
        for original, instr in zip(ir.instrs, self.code, strict=True):
            instr.args = list(original.args)
            instr._origin = original.index
        self.changes: dict[str, int] = {}
        self.marks: dict[int, str] = {}

    def count(self, name: str, origin: int | None = None, mark: str = "rewritten") -> None:
        self.changes[name] = self.changes.get(name, 0) + 1
        if origin is not None and self.marks.get(origin) != "removed":
            self.marks[origin] = mark

    def run(self) -> OptimizationResult:
        for _ in range(6):
            before = (len(self.code), sum(self.changes.values()))
            self.fold_and_propagate()
            self.dead_temps()
            self.unreachable()
            if (len(self.code), sum(self.changes.values())) == before:
                break
        for i, instr in enumerate(self.code):
            instr.index = i
        functions = {}
        for name, info in self.ir.functions.items():
            new = copy.copy(info)
            new.start = next(i.index for i in self.code if i.op == "func" and i.name == name)
            new.end = next(i.index for i in self.code if i.op == "endfunc" and i.name == name)
            functions[name] = new
        optimized = IRProgram(self.code, functions, self.ir.temps, self.ir.labels)
        return OptimizationResult(optimized, len(self.ir.instrs) - len(self.code), self.changes,
                                  self.marks)

    # ------------------------------------------------------------------ passes
    def fold_and_propagate(self) -> None:
        env: dict[str, object] = {}
        for instr in self.code:
            op = instr.op
            if op in ("label", "func"):
                env = {}  # a new basic block may be entered from elsewhere
                continue
            # propagate known constants into operands
            for attr in ("arg1", "arg2"):
                value = getattr(instr, attr)
                if op not in ("call",) and is_name(value) and value in env:
                    setattr(instr, attr, env[value])
                    self.count("constant propagation", instr._origin)
            if op == "print":
                for k, value in enumerate(instr.args):
                    if is_name(value) and value in env:
                        instr.args[k] = env[value]
                        self.count("constant propagation", instr._origin)
            if op == "binop":
                if _const(instr.arg1) and _const(instr.arg2):
                    value = _fold(instr.operator, instr.arg1, instr.arg2)
                    if value is not None:
                        self._to_assign(instr, value)
                        self.count("constant folding", instr._origin)
                else:
                    self._algebraic(instr)
            elif op == "unop" and _const(instr.arg1):
                self._to_assign(instr, apply_unop(instr.operator, instr.arg1))
                self.count("constant folding", instr._origin)
            elif op in ("iffalse", "iftrue") and _const(instr.arg1):
                taken = (not instr.arg1) if op == "iffalse" else bool(instr.arg1)
                if taken:
                    instr.op, instr.arg1 = "goto", None
                else:
                    instr.op = "nop"
                self.count("constant branch", instr._origin)
            defined = instr.defines()
            if defined is not None:
                if instr.op == "assign" and _const(instr.arg1):
                    env[defined] = instr.arg1
                else:
                    env.pop(defined, None)
            if op == "call":
                # a call may change any global variable
                env = {k: v for k, v in env.items() if is_temp(k)}
        self._drop("nop")

    def _to_assign(self, instr: Instr, value) -> None:
        instr.op, instr.arg1, instr.arg2, instr.operator = "assign", value, None, None

    def _algebraic(self, instr: Instr) -> None:
        a, b, op = instr.arg1, instr.arg2, instr.operator
        keep = None
        if op in ("+", "-") and _const(b) and not isinstance(b, bool) and b == 0 \
                and isinstance(b, int):
            keep = a
        elif op == "+" and _const(a) and isinstance(a, int) and not isinstance(a, bool) and a == 0:
            keep = b
        elif op in ("*", "/") and isinstance(b, int) and not isinstance(b, bool) and b == 1:
            keep = a
        elif op == "*" and isinstance(a, int) and not isinstance(a, bool) and a == 1:
            keep = b
        if keep is not None:
            self._to_assign(instr, keep)
            self.count("algebraic simplification", instr._origin)

    def dead_temps(self) -> None:
        used: set[str] = set()
        for instr in self.code:
            used.update(instr.uses())
            if instr.op in ("iffalse", "iftrue", "return", "param") and is_name(instr.arg1):
                used.add(instr.arg1)
        kept = []
        for instr in self.code:
            target = instr.result
            if (instr.op in ("assign", "binop", "unop") and is_temp(target)
                    and target not in used):
                self.count("dead code elimination", instr._origin, "removed")
                continue
            kept.append(instr)
        self.code = kept

    def unreachable(self) -> None:
        kept: list[Instr] = []
        dead = False
        for instr in self.code:
            if instr.op in ("label", "func", "endfunc"):
                dead = False
            if dead:
                self.count("unreachable code", instr._origin, "removed")
                continue
            kept.append(instr)
            if instr.op in ("goto", "return", "halt"):
                dead = True
        # goto L immediately followed by L:
        cleaned: list[Instr] = []
        for i, instr in enumerate(kept):
            nxt = kept[i + 1] if i + 1 < len(kept) else None
            if instr.op == "goto" and nxt is not None and nxt.op == "label" \
                    and nxt.label == instr.label:
                self.count("redundant jump", instr._origin, "removed")
                continue
            cleaned.append(instr)
        # labels nobody jumps to
        targets = {i.label for i in cleaned if i.is_jump()}
        final = []
        for instr in cleaned:
            if instr.op == "label" and instr.label not in targets:
                self.count("unused label", instr._origin, "removed")
                continue
            final.append(instr)
        self.code = final

    def _drop(self, op: str) -> None:
        kept = []
        for instr in self.code:
            if instr.op == op:
                self.marks[instr._origin] = "removed"
                continue
            kept.append(instr)
        self.code = kept


def optimize(ir: IRProgram) -> OptimizationResult:
    return Optimizer(ir).run()
