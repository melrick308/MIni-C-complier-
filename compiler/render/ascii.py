"""Plain-text renderings of compiler artefacts for the CLI."""

from __future__ import annotations


def tree(flat: dict | None, label) -> str:
    """Render a flat {'root', 'nodes'} tree with box-drawing characters."""
    if not flat:
        return "(none)"
    nodes = {n["id"]: n for n in flat["nodes"]}
    lines: list[str] = []
    stack = [(flat["root"], "", True, True)]
    while stack:
        node_id, prefix, last, is_root = stack.pop()
        node = nodes[node_id]
        if is_root:
            lines.append(label(node))
            child_prefix = ""
        else:
            lines.append(prefix + ("└── " if last else "├── ") + label(node))
            child_prefix = prefix + ("    " if last else "│   ")
        children = node["children"]
        for i in reversed(range(len(children))):
            stack.append((children[i], child_prefix, i == len(children) - 1, False))
    return "\n".join(lines)


def parse_tree_label(node: dict) -> str:
    if node["kind"] == "terminal":
        return node.get("lexeme", node["symbol"])
    if node["kind"] == "error":
        return f"⚠ error [{node.get('lexeme') or ''}]"
    return node["symbol"]


def ast_label(node: dict) -> str:
    text = f"{node['kind']} {node['label']}" if node["label"] != node["kind"] else node["kind"]
    return f"{text} : {node['type']}" if node.get("type") else text


def caret(source: str, diag: dict) -> str:
    if not diag.get("span"):
        return ""
    line, col, end_line, end_col = diag["span"]
    lines = source.splitlines() or [""]
    text = lines[line - 1] if line - 1 < len(lines) else ""
    width = max(1, (end_col - col) if end_line == line else len(text) - col + 1)
    gutter = f"{line:>4} | "
    return f"{gutter}{text}\n{' ' * len(gutter)}{' ' * (col - 1)}^{'~' * (width - 1)}"


def trace_table(steps: list[dict]) -> str:
    rows = [("Step", "Function", "Lookahead", "Action", "Production / message")]
    for s in steps:
        detail = s.get("production") if s["action"] == "enter" else s["message"]
        rows.append((str(s["step"]), "  " * s["depth"] + s["function"], s["lexeme"], s["action"],
                     detail or ""))
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    out = []
    for r in rows:
        out.append("  ".join(r[i].ljust(widths[i]) for i in range(4)) + "  " + r[4])
    return "\n".join(out)


def token_table(tokens: list[dict]) -> str:
    rows = [("Lexeme", "Token", "Line:Col")]
    rows += [(t["lexeme"], t["token"], f"{t['line']}:{t['col']}") for t in tokens]
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    return "\n".join("  ".join(r[i].ljust(widths[i]) for i in range(3)) for r in rows)


def tac_listing(instrs: list[dict]) -> str:
    out = []
    for i in instrs:
        text = i["text"]
        out.append(f"{i['index']:>4}  {text}" if i["op"] == "label" else f"{i['index']:>4}      {text}")
    return "\n".join(out)


def diagnostics(source: str, diags: list[dict]) -> str:
    out = []
    for d in diags:
        where = f"{d['line']}:{d['col']}" if d.get("line") else "-"
        out.append(f"{d['severity'].upper()} [{d['phase']}] {d['code']} at {where}: {d['message']}")
        if d.get("span"):
            out.append(caret(source, d))
        if d.get("expected"):
            out.append("     expected: " + ", ".join(d["expected"]))
        if d.get("hint"):
            out.append("     hint: " + d["hint"])
    return "\n".join(out)
