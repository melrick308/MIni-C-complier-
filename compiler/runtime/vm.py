"""A virtual machine that executes Three Address Code and records every step."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..common import limits
from ..common.diagnostics import ERROR, RUNTIME, Diagnostic
from ..ir.tac import Instr, Str, format_number, is_temp
from ..ir.tac_gen import IRProgram

MAX_INT = 10**300


@dataclass
class Frame:
    id: int
    func: str
    locals: dict = field(default_factory=dict)
    return_pc: int | None = None
    result_target: str | None = None


@dataclass
class ExecutionResult:
    status: str  # ok | runtime_error | limit
    output: list[str]
    steps: int
    trace: list[dict]
    trace_truncated: bool
    globals: dict
    max_depth: int
    error: Diagnostic | None = None
    value: object = None  # last temporary's value (expression mode)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "output": self.output,
            "steps": self.steps,
            "trace": self.trace,
            "trace_truncated": self.trace_truncated,
            "globals": self.globals,
            "max_depth": self.max_depth,
            "error": self.error.to_dict() if self.error else None,
        }


class VMError(Exception):
    def __init__(self, code: str, message: str, instr: Instr | None, status="runtime_error",
                 hint=None):
        super().__init__(message)
        self.status = status
        self.diagnostic = Diagnostic(ERROR, RUNTIME, code, message,
                                     instr.span if instr else None, hint=hint)


def apply_unop(operator: str, a):
    if operator == "minus":
        return -a
    if operator == "not":
        return not a
    if operator == "(float)":
        return float(a)
    raise ValueError(operator)


def trunc_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


class VM:
    def __init__(self, ir: IRProgram, *, division: str = "int", mode: str = "program",
                 initial: dict | None = None, max_steps: int = limits.MAX_EXEC_STEPS,
                 max_trace: int = limits.MAX_EXEC_TRACE,
                 max_seconds: float = limits.MAX_EXEC_SECONDS,
                 max_output: int = limits.MAX_OUTPUT_LINES,
                 max_depth: int = limits.MAX_CALL_DEPTH):
        self.code = ir.instrs
        self.functions = ir.functions
        self.labels = ir.label_index()
        self.division = division
        self.mode = mode
        self.globals: dict = dict(initial or {})
        self.max_steps, self.max_trace = max_steps, max_trace
        self.max_seconds, self.max_output, self.max_depth = max_seconds, max_output, max_depth
        self.output: list[str] = []
        self.trace: list[dict] = []
        self.truncated = False
        self.frames: list[Frame] = [Frame(0, "main")]
        self._frame_ids = 0
        self._writes: list = []
        self.last_value = None

    # --------------------------------------------------------------- operands
    def fmt(self, value) -> str:
        if isinstance(value, str):
            return value
        return format_number(value, mode=self.mode)

    def read(self, operand, instr: Instr):
        if isinstance(operand, Str):
            return operand.value
        if not isinstance(operand, str):
            return operand
        frame = self.frames[-1]
        if operand in frame.locals:
            return frame.locals[operand]
        if operand in self.globals:
            return self.globals[operand]
        raise VMError("E_RT_UNINITIALIZED", f"Variable '{operand}' has no value", instr)

    def store(self, frame: Frame, name: str, value) -> None:
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            raise VMError("E_RT_OVERFLOW", "Numeric result is too large", self._instr)
        if isinstance(value, int) and not isinstance(value, bool) and abs(value) > MAX_INT:
            raise VMError("E_RT_OVERFLOW", "Integer result is too large", self._instr)
        info = self.functions.get(frame.func)
        if is_temp(name):
            frame.locals[name] = value
            scope = "temp"
        elif info is not None and name in info.locals:
            frame.locals[name] = value
            scope = "local"
        else:
            self.globals[name] = value
            scope = "global"
        self._writes.append({"name": name, "value": self.fmt(value), "scope": scope})
        self.last_value = value

    # ------------------------------------------------------------- arithmetic
    def binop(self, op: str, a, b, instr: Instr):
        try:
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if b == 0:
                    raise VMError("E_RT_DIV_ZERO", "Division by zero", instr,
                                  hint="Check the divisor before dividing.")
                if self.division == "int" and _is_int(a) and _is_int(b):
                    return trunc_div(a, b)
                return a / b
            if op == "%":
                if b == 0:
                    raise VMError("E_RT_MOD_ZERO", "Modulo by zero", instr)
                return a - b * trunc_div(a, b)
            if op == "<":
                return a < b
            if op == "<=":
                return a <= b
            if op == ">":
                return a > b
            if op == ">=":
                return a >= b
            if op == "==":
                return a == b
            if op == "!=":
                return a != b
        except OverflowError as exc:
            raise VMError("E_RT_OVERFLOW", "Numeric result is too large", instr) from exc
        raise VMError("E_RT_INTERNAL", f"Unknown operator {op}", instr)

    # ------------------------------------------------------------------- run
    def run(self) -> ExecutionResult:
        status, error = "ok", None
        steps = 0
        max_depth = 0
        pc = 0
        params: list = []
        started = time.perf_counter()
        self._instr = None
        try:
            while True:
                while self.code[pc].op == "label":
                    pc += 1
                instr = self.code[pc]
                self._instr = instr
                if steps >= self.max_steps:
                    raise VMError("E_RT_STEP_LIMIT",
                                  f"Stopped after {self.max_steps:,} instructions — possible "
                                  "infinite loop", instr, status="limit",
                                  hint="Infinite loops cannot be detected in general (the halting "
                                       "problem), so execution is capped.")
                if steps % 2000 == 0 and time.perf_counter() - started > self.max_seconds:
                    raise VMError("E_RT_TIME_LIMIT",
                                  f"Stopped after {self.max_seconds:g} seconds", instr,
                                  status="limit")
                steps += 1
                frame = self.frames[-1]
                self._writes = []
                record = {"step": steps, "pc": instr.index, "func": frame.func,
                          "frame": frame.id, "depth": len(self.frames) - 1,
                          "line": instr.span.start.line if instr.span else None,
                          "text": instr.text()}
                op = instr.op
                next_pc = pc + 1
                if op == "assign":
                    self.store(frame, instr.result, self.read(instr.arg1, instr))
                elif op == "binop":
                    a, b = self.read(instr.arg1, instr), self.read(instr.arg2, instr)
                    self.store(frame, instr.result, self.binop(instr.operator, a, b, instr))
                elif op == "unop":
                    value = apply_unop(instr.operator, self.read(instr.arg1, instr))
                    self.store(frame, instr.result, value)
                elif op == "goto":
                    next_pc = self.labels[instr.label]
                elif op == "iffalse":
                    if not self.read(instr.arg1, instr):
                        next_pc = self.labels[instr.label]
                elif op == "iftrue":
                    if self.read(instr.arg1, instr):
                        next_pc = self.labels[instr.label]
                elif op == "param":
                    params.append(self.read(instr.arg1, instr))
                elif op == "call":
                    info = self.functions[instr.name]
                    count = instr.arg2
                    args = params[len(params) - count:] if count else []
                    del params[len(params) - count:]
                    if len(self.frames) > self.max_depth:
                        raise VMError("E_RT_CALL_DEPTH",
                                      f"More than {self.max_depth} nested calls — possible "
                                      "infinite recursion", instr, status="limit",
                                      hint="Make sure the recursion has a base case.")
                    self._frame_ids += 1
                    callee = Frame(self._frame_ids, info.name, {}, pc + 1, instr.result)
                    self.frames.append(callee)
                    max_depth = max(max_depth, len(self.frames) - 1)
                    record["event"] = "call"
                    record["call"] = {"func": info.name, "frame": callee.id}
                    for pname, value in zip(info.params, args, strict=True):
                        self.store(callee, pname, value)
                    next_pc = info.start + 1
                elif op in ("return", "endfunc"):
                    if op == "endfunc" and self.functions[frame.func].returns_value:
                        raise VMError("E_RT_NO_RETURN",
                                      f"Function '{frame.func}' ended without returning a value",
                                      instr)
                    value = self.read(instr.arg1, instr) if instr.arg1 is not None else None
                    self.frames.pop()
                    caller = self.frames[-1]
                    record["event"] = "return"
                    record["return"] = {"func": frame.func, "frame": frame.id,
                                        "value": None if value is None else self.fmt(value)}
                    if frame.result_target is not None:
                        self.store(caller, frame.result_target, value)
                    next_pc = frame.return_pc
                elif op == "print":
                    line = " ".join(self.fmt(self.read(a, instr)) for a in instr.args)
                    if len(self.output) >= self.max_output:
                        raise VMError("E_RT_OUTPUT_LIMIT",
                                      f"Stopped after printing {self.max_output} lines", instr,
                                      status="limit")
                    self.output.append(line)
                    record["output"] = line
                elif op == "halt":
                    record["writes"] = []
                    self._record(record)
                    break
                record["writes"] = self._writes
                self._record(record)
                pc = next_pc
        except VMError as exc:
            status, error = exc.status, exc.diagnostic
            if self._instr is not None:
                record = {"step": steps, "pc": self._instr.index, "func": self.frames[-1].func,
                          "frame": self.frames[-1].id, "depth": len(self.frames) - 1,
                          "line": self._instr.span.start.line if self._instr.span else None,
                          "text": self._instr.text(), "writes": [], "error": exc.diagnostic.message}
                self._record(record)
        return ExecutionResult(status, self.output, steps, self.trace, self.truncated,
                               {k: self.fmt(v) for k, v in self.globals.items()}, max_depth,
                               error, self.last_value)

    def _record(self, record: dict) -> None:
        if len(self.trace) < self.max_trace:
            self.trace.append(record)
        else:
            self.truncated = True


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
