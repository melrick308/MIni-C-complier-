"""Syntax-directed translation from the (type-checked) AST to Three Address Code."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..semantic import types as ty
from ..semantic.symbols import Symbol, safe_ir_name
from ..syntax import ast as A
from .tac import Instr, Operand, Str


@dataclass
class FunctionInfo:
    name: str
    params: list[str]
    locals: set[str]
    returns_value: bool
    start: int = -1
    end: int = -1


@dataclass
class IRProgram:
    instrs: list[Instr]
    functions: dict[str, FunctionInfo] = field(default_factory=dict)
    temps: int = 0
    labels: int = 0

    def label_index(self) -> dict[str, int]:
        return {i.label: i.index for i in self.instrs if i.op == "label"}


class TACGenerator:
    def __init__(self):
        self.code: list[Instr] = []
        self.temp_count = 0
        self.label_count = 0
        self.func = "main"
        self.loops: list[tuple[str, str]] = []  # (continue label, break label)
        self.return_types: dict[str, str] = {}

    # ---------------------------------------------------------------- helpers
    def new_temp(self) -> str:
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self) -> str:
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, op: str, node: A.Node | None = None, **kwargs) -> Instr:
        instr = Instr(op, span=node.span if node is not None else None,
                      ast_id=node.id if node is not None else None, func=self.func, **kwargs)
        instr.index = len(self.code)
        self.code.append(instr)
        return instr

    def label(self, name: str, node: A.Node | None = None) -> None:
        self.emit("label", node, label=name)

    # ---------------------------------------------------------------- program
    def program(self, program: A.Program, symbols: list[Symbol]) -> IRProgram:
        functions: dict[str, FunctionInfo] = {}
        for item in program.items:
            if isinstance(item, A.FuncDecl):
                self.return_types[item.name] = item.return_type
                locals_ = {s.ir_name for s in symbols
                           if s.owner == item.name and s.kind in ("var", "param")}
                functions[item.name] = FunctionInfo(
                    item.name, [p.symbol.ir_name for p in item.params], locals_,
                    item.return_type != ty.VOID)
        for item in program.items:
            if not isinstance(item, A.FuncDecl):
                self.stmt(item)
        self.emit("halt", None)
        for item in program.items:
            if isinstance(item, A.FuncDecl):
                info = functions[item.name]
                info.start = len(self.code)
                self.function(item, info)
                info.end = len(self.code) - 1
        return IRProgram(self.code, functions, self.temp_count, self.label_count)

    def expression(self, expr: A.Node) -> IRProgram:
        """Expression mode: the result always ends up in the last temporary."""
        result = self.expr(expr)
        if not isinstance(expr, (A.Binary, A.Unary)):
            temp = self.new_temp()
            self.emit("assign", expr, result=temp, arg1=result)
        self.emit("halt", None)
        return IRProgram(self.code, {}, self.temp_count, self.label_count)

    def function(self, fn: A.FuncDecl, info: FunctionInfo) -> None:
        self.func = fn.name
        self.emit("func", fn, name=fn.name, args=list(info.params))
        for stmt in fn.body.stmts:
            self.stmt(stmt)
        last = self.code[-1]
        if fn.return_type == ty.VOID and last.op != "return":
            self.emit("return", fn.body)
        self.emit("endfunc", fn, name=fn.name)
        self.func = "main"

    # ------------------------------------------------------------- statements
    def stmt(self, node: A.Node) -> None:
        getattr(self, f"stmt_{node.KIND}")(node)

    def stmt_Block(self, node: A.Block) -> None:
        for stmt in node.stmts:
            self.stmt(stmt)

    def stmt_VarDecl(self, node: A.VarDecl) -> None:
        target = node.symbol.ir_name
        if node.init is None:
            self.emit("assign", node, result=target, arg1=ty.ZERO_VALUE[node.type_name])
            return
        value = self.coerce(self.expr(node.init), node.init, node.type_name)
        self.assign_into(target, value, node)

    def stmt_Assign(self, node: A.Assign) -> None:
        value = self.coerce(self.expr(node.value), node.value, node.symbol.type)
        self.assign_into(node.symbol.ir_name, value, node)

    def assign_into(self, target: str, value: Operand, node: A.Node) -> None:
        last = self.code[-1] if self.code else None
        # Write straight into the target instead of copying a fresh temporary.
        if (isinstance(value, str) and last is not None and last.result == value
                and last.op in ("binop", "unop", "call") and value == f"t{self.temp_count}"):
            last.result = target
            return
        self.emit("assign", node, result=target, arg1=value)

    def stmt_If(self, node: A.If) -> None:
        cond = self.expr(node.cond)
        if node.else_ is None:
            end = self.new_label()
            self.emit("iffalse", node.cond, arg1=cond, label=end)
            self.stmt(node.then)
            self.label(end, node)
            return
        else_label, end = self.new_label(), self.new_label()
        self.emit("iffalse", node.cond, arg1=cond, label=else_label)
        self.stmt(node.then)
        self.emit("goto", node, label=end)
        self.label(else_label, node.else_)
        self.stmt(node.else_)
        self.label(end, node)

    def stmt_While(self, node: A.While) -> None:
        start, end = self.new_label(), self.new_label()
        self.label(start, node)
        cond = self.expr(node.cond)
        self.emit("iffalse", node.cond, arg1=cond, label=end)
        self.loops.append((start, end))
        self.stmt(node.body)
        self.loops.pop()
        self.emit("goto", node, label=start)
        self.label(end, node)

    def stmt_DoWhile(self, node: A.DoWhile) -> None:
        start, cont, end = self.new_label(), self.new_label(), self.new_label()
        self.label(start, node)
        self.loops.append((cont, end))
        self.stmt(node.body)
        self.loops.pop()
        self.label(cont, node.cond)
        cond = self.expr(node.cond)
        self.emit("iftrue", node.cond, arg1=cond, label=start)
        self.label(end, node)

    def stmt_For(self, node: A.For) -> None:
        if node.init is not None:
            self.stmt(node.init)
        start, cont, end = self.new_label(), self.new_label(), self.new_label()
        self.label(start, node)
        if node.cond is not None:
            cond = self.expr(node.cond)
            self.emit("iffalse", node.cond, arg1=cond, label=end)
        self.loops.append((cont, end))
        self.stmt(node.body)
        self.loops.pop()
        self.label(cont, node.update or node)
        if node.update is not None:
            self.stmt(node.update)
        self.emit("goto", node, label=start)
        self.label(end, node)

    def stmt_Return(self, node: A.Return) -> None:
        if node.value is None:
            self.emit("return", node)
            return
        value = self.coerce(self.expr(node.value), node.value, self.return_types.get(self.func))
        self.emit("return", node, arg1=value)

    def stmt_Break(self, node: A.Node) -> None:
        self.emit("goto", node, label=self.loops[-1][1])

    def stmt_Continue(self, node: A.Node) -> None:
        self.emit("goto", node, label=self.loops[-1][0])

    def stmt_Print(self, node: A.Print) -> None:
        operands = [Str(a.value) if isinstance(a, A.StringLit) else self.expr(a) for a in node.args]
        self.emit("print", node, args=operands)

    def stmt_CallStmt(self, node: A.CallStmt) -> None:
        self.call(node.call, want_result=False)

    # ------------------------------------------------------------ expressions
    def expr(self, node: A.Node) -> Operand:
        if isinstance(node, A.Literal):
            return node.value
        if isinstance(node, A.Var):
            return node.symbol.ir_name if node.symbol is not None else safe_ir_name(node.name)
        if isinstance(node, A.Unary):
            operand = self.expr(node.operand)
            temp = self.new_temp()
            self.emit("unop", node, result=temp, operator="minus" if node.op == "-" else "not",
                      arg1=operand)
            return temp
        if isinstance(node, A.Binary):
            if node.op in ("&&", "||"):
                return self.short_circuit(node)
            left = self.expr(node.left)
            right = self.expr(node.right)
            temp = self.new_temp()
            self.emit("binop", node, result=temp, arg1=left, arg2=right, operator=node.op)
            return temp
        if isinstance(node, A.Call):
            return self.call(node, want_result=True)
        raise TypeError(f"cannot translate {node.KIND}")

    def short_circuit(self, node: A.Binary) -> str:
        """a && b:  t = a; ifFalse t goto L; t = b; L:     (|| uses 'if t goto L')."""
        result = self.new_temp()
        end = self.new_label()
        self.assign_into(result, self.expr(node.left), node.left)
        self.emit("iffalse" if node.op == "&&" else "iftrue", node, arg1=result, label=end)
        self.assign_into(result, self.expr(node.right), node.right)
        self.label(end, node)
        return result

    def call(self, node: A.Call, want_result: bool) -> Operand | None:
        params = node.symbol.params if node.symbol is not None else []
        values = []
        for arg, (_, ptype) in zip(node.args, params, strict=False):
            values.append(self.coerce(self.expr(arg), arg, ptype))
        for value in values:
            self.emit("param", node, arg1=value)
        result = self.new_temp() if want_result else None
        self.emit("call", node, result=result, name=node.name, arg2=len(values))
        return result

    def coerce(self, value: Operand, node: A.Node, target: str) -> Operand:
        """Insert an explicit int → float conversion where the types require it."""
        if target == ty.FLOAT and node.type == ty.INT:
            if isinstance(value, int) and not isinstance(value, bool):
                return float(value)
            temp = self.new_temp()
            self.emit("unop", node, result=temp, operator="(float)", arg1=value)
            return temp
        return value


def generate_program(program: A.Program, symbols: list[Symbol]) -> IRProgram:
    return TACGenerator().program(program, symbols)


def generate_expression(expr: A.Node) -> IRProgram:
    return TACGenerator().expression(expr)
