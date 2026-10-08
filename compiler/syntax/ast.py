"""Abstract syntax tree. Shared contract between the parser and every later phase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from ..common.source import Span


@dataclass(eq=False)
class Node:
    span: Span | None = field(default=None, kw_only=True)
    id: str = field(default="", kw_only=True, repr=False)
    type: str | None = field(default=None, kw_only=True)

    KIND: ClassVar[str] = "Node"
    CHILDREN: ClassVar[tuple[str, ...]] = ()

    def children(self) -> list[Node]:
        out: list[Node] = []
        for name in self.CHILDREN:
            value = getattr(self, name)
            if isinstance(value, list):
                out.extend(v for v in value if v is not None)
            elif value is not None:
                out.append(value)
        return out

    def attrs(self) -> dict:
        return {}

    def label(self) -> str:
        return self.KIND


# --------------------------------------------------------------------- expressions
@dataclass(eq=False)
class Literal(Node):
    value: int | float | bool
    lexeme: str
    KIND: ClassVar[str] = "Literal"

    @property
    def lit_type(self) -> str:
        if isinstance(self.value, bool):
            return "bool"
        return "float" if isinstance(self.value, float) else "int"

    def attrs(self):
        return {"value": self.lexeme, "literal_type": self.lit_type}

    def label(self):
        return self.lexeme


@dataclass(eq=False)
class StringLit(Node):
    value: str
    lexeme: str
    KIND: ClassVar[str] = "String"

    def attrs(self):
        return {"value": self.value}

    def label(self):
        return self.lexeme


@dataclass(eq=False)
class Var(Node):
    name: str
    symbol: object = field(default=None, kw_only=True, repr=False)
    KIND: ClassVar[str] = "Var"

    def attrs(self):
        return {"name": self.name}

    def label(self):
        return self.name


@dataclass(eq=False)
class Unary(Node):
    op: str
    operand: Node
    KIND: ClassVar[str] = "Unary"
    CHILDREN: ClassVar[tuple[str, ...]] = ("operand",)

    def attrs(self):
        return {"op": self.op}

    def label(self):
        return self.op


@dataclass(eq=False)
class Binary(Node):
    op: str
    left: Node
    right: Node
    KIND: ClassVar[str] = "Binary"
    CHILDREN: ClassVar[tuple[str, ...]] = ("left", "right")

    def attrs(self):
        return {"op": self.op}

    def label(self):
        return self.op


@dataclass(eq=False)
class Call(Node):
    name: str
    args: list[Node]
    symbol: object = field(default=None, kw_only=True, repr=False)
    KIND: ClassVar[str] = "Call"
    CHILDREN: ClassVar[tuple[str, ...]] = ("args",)

    def attrs(self):
        return {"name": self.name, "argc": len(self.args)}

    def label(self):
        return f"{self.name}()"


# ---------------------------------------------------------------------- statements
@dataclass(eq=False)
class Param(Node):
    name: str
    type_name: str
    symbol: object = field(default=None, kw_only=True, repr=False)
    KIND: ClassVar[str] = "Param"

    def attrs(self):
        return {"name": self.name, "declared_type": self.type_name}

    def label(self):
        return f"{self.type_name} {self.name}"


@dataclass(eq=False)
class Block(Node):
    stmts: list[Node]
    KIND: ClassVar[str] = "Block"
    CHILDREN: ClassVar[tuple[str, ...]] = ("stmts",)

    def label(self):
        return "{ }"


@dataclass(eq=False)
class FuncDecl(Node):
    name: str
    return_type: str
    params: list[Param]
    body: Block
    name_span: Span | None = None
    symbol: object = field(default=None, kw_only=True, repr=False)
    KIND: ClassVar[str] = "FuncDecl"
    CHILDREN: ClassVar[tuple[str, ...]] = ("params", "body")

    def attrs(self):
        return {"name": self.name, "return_type": self.return_type}

    def label(self):
        return f"{self.return_type} {self.name}({', '.join(p.name for p in self.params)})"


@dataclass(eq=False)
class VarDecl(Node):
    name: str
    type_name: str
    init: Node | None
    name_span: Span | None = None
    symbol: object = field(default=None, kw_only=True, repr=False)
    KIND: ClassVar[str] = "VarDecl"
    CHILDREN: ClassVar[tuple[str, ...]] = ("init",)

    def attrs(self):
        return {"name": self.name, "declared_type": self.type_name}

    def label(self):
        return f"{self.type_name} {self.name}"


@dataclass(eq=False)
class Assign(Node):
    name: str
    value: Node
    op: str = "="  # original operator, e.g. '+=' or '++' (value is already desugared)
    name_span: Span | None = None
    symbol: object = field(default=None, kw_only=True, repr=False)
    KIND: ClassVar[str] = "Assign"
    CHILDREN: ClassVar[tuple[str, ...]] = ("value",)

    def attrs(self):
        return {"name": self.name, "op": self.op}

    def label(self):
        return f"{self.name} {self.op}"


@dataclass(eq=False)
class If(Node):
    cond: Node
    then: Node
    else_: Node | None
    KIND: ClassVar[str] = "If"
    CHILDREN: ClassVar[tuple[str, ...]] = ("cond", "then", "else_")

    def label(self):
        return "if-else" if self.else_ is not None else "if"


@dataclass(eq=False)
class While(Node):
    cond: Node
    body: Node
    KIND: ClassVar[str] = "While"
    CHILDREN: ClassVar[tuple[str, ...]] = ("cond", "body")

    def label(self):
        return "while"


@dataclass(eq=False)
class DoWhile(Node):
    body: Node
    cond: Node
    KIND: ClassVar[str] = "DoWhile"
    CHILDREN: ClassVar[tuple[str, ...]] = ("body", "cond")

    def label(self):
        return "do-while"


@dataclass(eq=False)
class For(Node):
    init: Node | None
    cond: Node | None
    update: Node | None
    body: Node
    KIND: ClassVar[str] = "For"
    CHILDREN: ClassVar[tuple[str, ...]] = ("init", "cond", "update", "body")

    def label(self):
        return "for"


@dataclass(eq=False)
class Return(Node):
    value: Node | None
    KIND: ClassVar[str] = "Return"
    CHILDREN: ClassVar[tuple[str, ...]] = ("value",)

    def label(self):
        return "return"


@dataclass(eq=False)
class Break(Node):
    KIND: ClassVar[str] = "Break"

    def label(self):
        return "break"


@dataclass(eq=False)
class Continue(Node):
    KIND: ClassVar[str] = "Continue"

    def label(self):
        return "continue"


@dataclass(eq=False)
class Print(Node):
    args: list[Node]
    KIND: ClassVar[str] = "Print"
    CHILDREN: ClassVar[tuple[str, ...]] = ("args",)

    def label(self):
        return "print"


@dataclass(eq=False)
class CallStmt(Node):
    call: Call
    KIND: ClassVar[str] = "CallStmt"
    CHILDREN: ClassVar[tuple[str, ...]] = ("call",)

    def label(self):
        return "call"


@dataclass(eq=False)
class Program(Node):
    items: list[Node]
    KIND: ClassVar[str] = "Program"
    CHILDREN: ClassVar[tuple[str, ...]] = ("items",)


# ------------------------------------------------------------------------- helpers
def walk_postorder(root: Node):
    """Iterative post-order traversal (no recursion limits for deep trees)."""
    stack: list[tuple[Node, bool]] = [(root, False)]
    while stack:
        node, visited = stack.pop()
        if visited:
            yield node
            continue
        stack.append((node, True))
        for child in reversed(node.children()):
            stack.append((child, False))


def number_nodes(root: Node) -> int:
    count = 0
    for node in walk_postorder(root):
        count += 1
        node.id = f"a{count}"
    return count


def ast_to_dict(root: Node | None) -> dict | None:
    """Flat serialisation: {'root': id, 'nodes': [...]} — avoids deep JSON nesting."""
    if root is None:
        return None
    nodes = []
    stack: list[tuple[Node, str | None]] = [(root, None)]
    while stack:
        node, parent = stack.pop()
        nodes.append({
            "id": node.id,
            "kind": node.KIND,
            "label": node.label(),
            "type": node.type,
            "span": node.span.to_dict() if node.span else None,
            "parent": parent,
            "children": [c.id for c in node.children()],
            **node.attrs(),
        })
        for child in reversed(node.children()):
            stack.append((child, node.id))
    return {"root": root.id, "nodes": nodes}


def to_infix(node: Node) -> str:
    """Fully parenthesised rendering of an expression."""
    if isinstance(node, Binary):
        return f"({to_infix(node.left)} {node.op} {to_infix(node.right)})"
    if isinstance(node, Unary):
        return f"({node.op}{to_infix(node.operand)})"
    if isinstance(node, Call):
        return f"{node.name}({', '.join(to_infix(a) for a in node.args)})"
    if isinstance(node, Var):
        return node.name
    if isinstance(node, (Literal, StringLit)):
        return node.lexeme
    return node.label()


def expr_depth(node: Node) -> int:
    return getattr(node, "_depth", 0)
