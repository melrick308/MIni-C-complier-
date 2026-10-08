"""Semantic analysis: name resolution with nested scopes, and static type checking.

Pass 1 collects function signatures (so functions can be called before they are defined).
Pass 2 walks the AST with a scope stack, annotating every expression with its type.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common.diagnostics import ERROR as SEV_ERROR
from ..common.diagnostics import SEMANTIC, WARNING, Diagnostic
from ..common.source import Span
from ..syntax import ast as A
from . import types as ty
from .symbols import Scope, Symbol, SymbolTable


@dataclass
class SemanticResult:
    scopes: list[Scope]
    symbols: list[Symbol]
    diagnostics: list[Diagnostic]

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == SEV_ERROR]


class SemanticAnalyzer:
    def __init__(self):
        self.table = SymbolTable()
        self.diags: list[Diagnostic] = []
        self.function: Symbol | None = None
        self.loop_depth = 0

    # ----------------------------------------------------------------- driver
    def analyze(self, program: A.Program) -> SemanticResult:
        self.table.push("global", "global", program.span)
        for item in program.items:
            if isinstance(item, A.FuncDecl):
                self._declare_function(item)
        for item in program.items:
            self.stmt(item)
        self._close_scope()
        return SemanticResult(self.table.scopes, self.table.symbols, self.diags)

    def error(self, code: str, message: str, span: Span | None, hint: str | None = None,
              related: tuple[Span, str] | None = None) -> None:
        self.diags.append(Diagnostic(
            SEV_ERROR, SEMANTIC, code, message, span, hint=hint,
            related_span=related[0] if related else None,
            related_message=related[1] if related else None))

    def _open_scope(self, kind: str, name: str, span: Span | None) -> None:
        self.table.push(kind, name, span)

    def _close_scope(self) -> None:
        scope = self.table.pop()
        for sym in scope.symbols.values():
            if sym.kind == "var" and not sym.used:
                self.diags.append(Diagnostic(
                    WARNING, SEMANTIC, "W_SEM_UNUSED",
                    f"Variable '{sym.name}' is declared but its value is never used", sym.span))

    def _owner(self) -> str | None:
        return self.function.name if self.function else None

    def _declare(self, name: str, kind: str, type_: str, span: Span | None) -> Symbol:
        existing = self.table.lookup_local(name)
        if existing is not None:
            self.error("E_SEM_REDECLARED",
                       f"'{name}' is already declared in this scope", span,
                       related=(existing.span, f"'{name}' was first declared here"))
        return self.table.declare(name, kind, type_, span, self._owner())

    def _declare_function(self, fn: A.FuncDecl) -> None:
        existing = self.table.lookup_local(fn.name)
        if existing is not None:
            self.error("E_SEM_REDECLARED", f"Function '{fn.name}' is already declared",
                       fn.name_span, related=(existing.span, "first declared here"))
            return
        sym = self.table.declare(fn.name, "func", fn.return_type, fn.name_span, None)
        sym.params = [(p.name, p.type_name) for p in fn.params]
        fn.symbol = sym

    # -------------------------------------------------------------- statements
    def stmt(self, node: A.Node) -> None:
        getattr(self, f"stmt_{node.KIND}")(node)

    def stmt_FuncDecl(self, fn: A.FuncDecl) -> None:
        if fn.symbol is None:  # duplicate function: still check the body
            fn.symbol = Symbol("s?", fn.name, "func", fn.return_type, 0, fn.name_span, fn.name)
        outer = self.function
        self.function = fn.symbol
        self._open_scope("function", fn.name, fn.span)
        for param in fn.params:
            param.symbol = self._declare(param.name, "param", param.type_name, param.span)
        for stmt in fn.body.stmts:
            self.stmt(stmt)
        if fn.return_type != ty.VOID and not always_returns(fn.body):
            self.error("E_SEM_MISSING_RETURN",
                       f"Function '{fn.name}' must return a value of type '{fn.return_type}' "
                       "on every path", fn.name_span,
                       hint="Add a return statement at the end of the function.")
        self._close_scope()
        self.function = outer

    def stmt_Block(self, block: A.Block) -> None:
        self._open_scope("block", "block", block.span)
        for stmt in block.stmts:
            self.stmt(stmt)
        self._close_scope()

    def stmt_VarDecl(self, decl: A.VarDecl) -> None:
        if decl.init is not None:
            value_type = self.value(decl.init)
            self._check_assign(decl.type_name, value_type, decl.init.span,
                               f"variable '{decl.name}'")
        decl.symbol = self._declare(decl.name, "var", decl.type_name, decl.name_span)

    def stmt_Assign(self, node: A.Assign) -> None:
        sym = self.table.resolve(node.name)
        value_type = self.value(node.value)
        if sym is None:
            self.error("E_SEM_UNDECLARED", f"Undeclared variable '{node.name}'", node.name_span,
                       hint=f"Declare it first, e.g. int {node.name} = 0;")
            return
        if sym.kind == "func":
            self.error("E_SEM_NOT_A_VARIABLE", f"Cannot assign to function '{node.name}'",
                       node.name_span)
            return
        node.symbol = sym
        self._check_assign(sym.type, value_type, node.value.span, f"variable '{node.name}'")

    def stmt_If(self, node: A.If) -> None:
        self._condition(node.cond, "if")
        self.stmt(node.then)
        if node.else_ is not None:
            self.stmt(node.else_)

    def stmt_While(self, node: A.While) -> None:
        self._condition(node.cond, "while")
        self.loop_depth += 1
        self.stmt(node.body)
        self.loop_depth -= 1

    def stmt_DoWhile(self, node: A.DoWhile) -> None:
        self.loop_depth += 1
        self.stmt(node.body)
        self.loop_depth -= 1
        self._condition(node.cond, "do-while")

    def stmt_For(self, node: A.For) -> None:
        self._open_scope("loop", "for", node.span)
        if node.init is not None:
            self.stmt(node.init)
        if node.cond is not None:
            self._condition(node.cond, "for")
        if node.update is not None:
            self.stmt(node.update)
        self.loop_depth += 1
        self.stmt(node.body)
        self.loop_depth -= 1
        self._close_scope()

    def stmt_Return(self, node: A.Return) -> None:
        if self.function is None:
            self.error("E_SEM_RETURN_OUTSIDE_FUNCTION", "'return' can only be used inside a function",
                       node.span)
            if node.value is not None:
                self.value(node.value)
            return
        expected = self.function.type
        if node.value is None:
            if expected != ty.VOID:
                self.error("E_SEM_RETURN_TYPE",
                           f"Function '{self.function.name}' must return a value of type "
                           f"'{expected}'", node.span)
            return
        value_type = self.value(node.value)
        if expected == ty.VOID:
            self.error("E_SEM_RETURN_TYPE",
                       f"Function '{self.function.name}' is void and cannot return a value",
                       node.value.span)
            return
        verdict = ty.assignable(expected, value_type)
        if verdict == "lossy":
            self.error("E_SEM_RETURN_TYPE",
                       f"Returning a 'float' from function '{self.function.name}' declared to "
                       f"return 'int' would lose precision", node.value.span)
        elif verdict == "mismatch":
            self.error("E_SEM_RETURN_TYPE",
                       f"Function '{self.function.name}' returns '{expected}' but this value is "
                       f"'{value_type}'", node.value.span)

    def stmt_Break(self, node: A.Node) -> None:
        if self.loop_depth == 0:
            self.error("E_SEM_BREAK_OUTSIDE_LOOP", "'break' can only be used inside a loop",
                       node.span)

    def stmt_Continue(self, node: A.Node) -> None:
        if self.loop_depth == 0:
            self.error("E_SEM_BREAK_OUTSIDE_LOOP", "'continue' can only be used inside a loop",
                       node.span)

    def stmt_Print(self, node: A.Print) -> None:
        for arg in node.args:
            if isinstance(arg, A.StringLit):
                arg.type = ty.STRING
            else:
                self.value(arg)

    def stmt_CallStmt(self, node: A.CallStmt) -> None:
        self.expr(node.call)

    # ------------------------------------------------------------- expressions
    def value(self, node: A.Node) -> str:
        """Type-check an expression whose value is used (void is not allowed)."""
        result = self.expr(node)
        if result == ty.VOID:
            self.error("E_SEM_VOID_VALUE",
                       f"Function '{node.name}' returns void and has no value to use",
                       node.span)
            return ty.ERROR
        return result

    def expr(self, node: A.Node) -> str:
        result = getattr(self, f"expr_{node.KIND}")(node)
        node.type = result
        return result

    def expr_Literal(self, node: A.Literal) -> str:
        return node.lit_type

    def expr_Var(self, node: A.Var) -> str:
        sym = self.table.resolve(node.name)
        if sym is None:
            self.error("E_SEM_UNDECLARED", f"Undeclared variable '{node.name}'", node.span,
                       hint=f"Declare it before use, e.g. int {node.name} = 0;")
            return ty.ERROR
        if sym.kind == "func":
            self.error("E_SEM_NOT_A_VARIABLE",
                       f"'{node.name}' is a function; call it with {node.name}(...)", node.span)
            return ty.ERROR
        sym.used = True
        node.symbol = sym
        return sym.type

    def expr_Unary(self, node: A.Unary) -> str:
        operand = self.value(node.operand)
        result = ty.unary_result(node.op, operand)
        if result is None:
            need = "a number" if node.op == "-" else "a bool"
            self.error("E_SEM_INVALID_OPERANDS",
                       f"Operator '{node.op}' needs {need}, not '{operand}'", node.span)
            return ty.ERROR
        return result

    def expr_Binary(self, node: A.Binary) -> str:
        left = self.value(node.left)
        right = self.value(node.right)
        result = ty.binary_result(node.op, left, right)
        if result is None:
            hint = None
            if node.op == "%":
                hint = "'%' works on int operands only."
            elif node.op in ty.LOGICAL_OPS:
                hint = f"'{node.op}' combines bool values, e.g. (a > 0) {node.op} (b > 0)."
            elif ty.BOOL in (left, right):
                hint = "Arithmetic and ordering operators work on numbers, not bool."
            self.error("E_SEM_INVALID_OPERANDS",
                       f"Operator '{node.op}' cannot be applied to '{left}' and '{right}'",
                       node.span, hint=hint)
            return ty.ERROR
        return result

    def expr_Call(self, node: A.Call) -> str:
        sym = self.table.resolve(node.name)
        arg_types = [self.value(arg) for arg in node.args]
        if sym is None:
            self.error("E_SEM_UNDECLARED", f"Undeclared function '{node.name}'", node.span)
            return ty.ERROR
        if sym.kind != "func":
            self.error("E_SEM_NOT_A_FUNCTION", f"'{node.name}' is a variable, not a function",
                       node.span)
            return ty.ERROR
        sym.used = True
        node.symbol = sym
        if len(arg_types) != len(sym.params):
            self.error("E_SEM_ARG_COUNT",
                       f"Function '{node.name}' expects {len(sym.params)} argument(s) but got "
                       f"{len(arg_types)}", node.span,
                       related=(sym.span, f"'{node.name}' is declared here"))
            return sym.type
        for arg, arg_type, (pname, ptype) in zip(node.args, arg_types, sym.params, strict=True):
            verdict = ty.assignable(ptype, arg_type)
            if verdict in ("lossy", "mismatch"):
                self.error("E_SEM_ARG_TYPE",
                           f"Argument for parameter '{pname}' of '{node.name}' must be "
                           f"'{ptype}', not '{arg_type}'", arg.span)
        return sym.type

    def expr_String(self, node: A.StringLit) -> str:
        self.error("E_SEM_TYPE_MISMATCH", "Strings can only be used as print(...) arguments",
                   node.span)
        return ty.ERROR

    # ----------------------------------------------------------------- helpers
    def _condition(self, cond: A.Node, construct: str) -> None:
        cond_type = self.value(cond)
        if cond_type not in (ty.BOOL, ty.ERROR):
            self.error("E_SEM_CONDITION_NOT_BOOL",
                       f"The {construct} condition must be 'bool', not '{cond_type}'", cond.span,
                       hint="Use a comparison, e.g. x != 0.")

    def _check_assign(self, target: str, value: str, span: Span | None, what: str) -> None:
        verdict = ty.assignable(target, value)
        if verdict == "lossy":
            self.error("E_SEM_LOSSY_ASSIGN",
                       f"Assigning a 'float' to {what} of type 'int' would lose precision", span,
                       hint="Declare the variable as float, or use an int value.")
        elif verdict == "mismatch":
            self.error("E_SEM_TYPE_MISMATCH",
                       f"Cannot assign a value of type '{value}' to {what} of type '{target}'",
                       span)


def always_returns(node: A.Node | None) -> bool:
    """Conservative check that every path through `node` ends in a return."""
    if node is None:
        return False
    if isinstance(node, A.Return):
        return True
    if isinstance(node, A.Block):
        return any(always_returns(s) for s in node.stmts)
    if isinstance(node, A.If):
        return node.else_ is not None and always_returns(node.then) and always_returns(node.else_)
    return False


def analyze(program: A.Program) -> SemanticResult:
    return SemanticAnalyzer().analyze(program)
