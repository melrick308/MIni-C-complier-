"""Concrete parse tree: one node per grammar symbol the parser expanded or matched."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.source import Span


@dataclass(eq=False)
class ParseNode:
    id: str
    symbol: str
    kind: str  # nonterminal | terminal | epsilon | error
    lexeme: str | None = None
    token_index: int | None = None
    step: int | None = None
    span: Span | None = None
    production: str | None = None
    children: list[ParseNode] = field(default_factory=list)


def compute_spans(root: ParseNode) -> None:
    """Fill non-terminal spans from their descendants (iterative post-order)."""
    stack: list[tuple[ParseNode, bool]] = [(root, False)]
    while stack:
        node, visited = stack.pop()
        if not visited:
            stack.append((node, True))
            stack.extend((c, False) for c in node.children)
            continue
        if node.kind == "nonterminal":
            span = None
            for child in node.children:
                if child.span is not None:
                    span = child.span if span is None else span.merge(child.span)
            node.span = span


def parse_tree_to_dict(root: ParseNode | None) -> dict | None:
    if root is None:
        return None
    nodes = []
    stack: list[tuple[ParseNode, str | None]] = [(root, None)]
    count = 0
    while stack:
        node, parent = stack.pop()
        count += 1
        entry = {"id": node.id, "symbol": node.symbol, "kind": node.kind, "parent": parent,
                 "children": [c.id for c in node.children]}
        if node.lexeme is not None:
            entry["lexeme"] = node.lexeme
        if node.token_index is not None:
            entry["token"] = node.token_index
        if node.step is not None:
            entry["step"] = node.step
        if node.span is not None:
            entry["span"] = node.span.to_dict()
        nodes.append(entry)
        for child in reversed(node.children):
            stack.append((child, node.id))
    return {"root": root.id, "nodes": nodes, "count": count}


def to_sexpr(node: ParseNode) -> str:
    """Compact structural form used in tests, e.g. E(T(F(a) T'(ε)) E'(ε))."""
    if node.kind == "terminal":
        return node.lexeme or node.symbol
    if node.kind == "epsilon":
        return "ε"
    return f"{node.symbol}({' '.join(to_sexpr(c) for c in node.children)})"
