"""Symbols, scopes and the scoped symbol table (a stack of hash maps)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..common.source import Span

_RESERVED_IR = re.compile(r"^[tL]\d+$")


def safe_ir_name(name: str) -> str:
    """User names that look like temporaries/labels (t1, L2) get a suffix in the IR."""
    return f"{name}_" if _RESERVED_IR.match(name) else name


@dataclass(eq=False)
class Symbol:
    id: str
    name: str
    kind: str  # var | param | func
    type: str
    scope_id: int
    span: Span | None
    ir_name: str
    owner: str | None = None  # function that owns this local; None for globals
    used: bool = False
    params: list[tuple[str, str]] = field(default_factory=list)  # (name, type) for functions

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "type": self.type,
            "scope": self.scope_id,
            "ir_name": self.ir_name,
            "owner": self.owner,
            "used": self.used,
            "span": self.span.to_dict() if self.span else None,
            "line": self.span.start.line if self.span else None,
        }
        if self.kind == "func":
            data["params"] = [{"name": n, "type": t} for n, t in self.params]
            data["signature"] = f"{self.type} {self.name}({', '.join(t for _, t in self.params)})"
        return data


@dataclass(eq=False)
class Scope:
    id: int
    kind: str  # global | function | block | loop
    parent: int | None
    name: str
    span: Span | None
    symbols: dict[str, Symbol] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "parent": self.parent,
            "span": self.span.to_dict() if self.span else None,
            "symbols": [s.id for s in self.symbols.values()],
        }


class SymbolTable:
    def __init__(self):
        self.scopes: list[Scope] = []
        self.stack: list[Scope] = []
        self.symbols: list[Symbol] = []
        self._ir_counts: dict[str, int] = {}

    def push(self, kind: str, name: str, span: Span | None) -> Scope:
        parent = self.stack[-1].id if self.stack else None
        scope = Scope(len(self.scopes), kind, parent, name, span)
        self.scopes.append(scope)
        self.stack.append(scope)
        return scope

    def pop(self) -> Scope:
        return self.stack.pop()

    @property
    def current(self) -> Scope:
        return self.stack[-1]

    def lookup_local(self, name: str) -> Symbol | None:
        return self.current.symbols.get(name)

    def resolve(self, name: str) -> Symbol | None:
        for scope in reversed(self.stack):
            if name in scope.symbols:
                return scope.symbols[name]
        return None

    def declare(self, name: str, kind: str, type_: str, span: Span | None,
                owner: str | None) -> Symbol:
        base = safe_ir_name(name)
        count = self._ir_counts.get(base, 0) + 1
        self._ir_counts[base] = count
        ir_name = base if count == 1 or kind == "func" else f"{base}_{count}"
        symbol = Symbol(f"s{len(self.symbols) + 1}", name, kind, type_, self.current.id, span,
                        ir_name, owner)
        self.current.symbols[name] = symbol
        self.symbols.append(symbol)
        return symbol
