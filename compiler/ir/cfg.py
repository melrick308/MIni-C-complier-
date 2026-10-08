"""Basic blocks and control flow graphs (leaders algorithm), plus Mermaid export."""

from __future__ import annotations

from dataclasses import dataclass, field

from .tac import Instr
from .tac_gen import IRProgram


@dataclass
class Edge:
    source: str
    target: str  # block id or "EXIT"
    kind: str  # fall | jump | true | false | exit
    back: bool = False

    def to_dict(self) -> dict:
        return {"from": self.source, "to": self.target, "kind": self.kind, "back": self.back}


@dataclass
class BasicBlock:
    id: str
    start: int
    end: int
    instrs: list[Instr]
    succ: list[str] = field(default_factory=list)
    pred: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "start": self.start, "end": self.end,
            "instrs": [i.index for i in self.instrs],
            "text": [i.text() for i in self.instrs],
            "succ": self.succ, "pred": self.pred,
            "lines": sorted({i.span.start.line for i in self.instrs if i.span}),
        }


@dataclass
class FunctionCFG:
    name: str
    blocks: list[BasicBlock]
    edges: list[Edge]

    @property
    def loops(self) -> int:
        return sum(1 for e in self.edges if e.back)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "blocks": [b.to_dict() for b in self.blocks],
            "edges": [e.to_dict() for e in self.edges],
            "loops": self.loops,
            "mermaid": to_mermaid(self),
        }


def segments(ir: IRProgram) -> list[tuple[str, int, int]]:
    """(name, first, last) instruction ranges: main code, then each function."""
    if not ir.instrs:
        return []
    halt = next((i.index for i in ir.instrs if i.op == "halt"), len(ir.instrs) - 1)
    result = [("main", 0, halt)]
    for info in ir.functions.values():
        result.append((info.name, info.start, info.end))
    return result


def build_cfg(ir: IRProgram) -> list[FunctionCFG]:
    return [_build(ir, name, first, last) for name, first, last in segments(ir)]


def _build(ir: IRProgram, name: str, first: int, last: int) -> FunctionCFG:
    code = ir.instrs
    labels = ir.label_index()
    leaders = {first}
    for i in range(first, last + 1):
        instr = code[i]
        if instr.op == "label":
            leaders.add(i)
        if instr.is_jump() or instr.op in ("return", "halt"):
            if i + 1 <= last:
                leaders.add(i + 1)
    ordered = sorted(leaders)
    blocks: list[BasicBlock] = []
    block_of: dict[int, str] = {}
    for n, start in enumerate(ordered):
        end = (ordered[n + 1] - 1) if n + 1 < len(ordered) else last
        block = BasicBlock(f"B{n + 1}", start, end, code[start:end + 1])
        blocks.append(block)
        for i in range(start, end + 1):
            block_of[i] = block.id
    by_id = {b.id: b for b in blocks}
    edges: list[Edge] = []

    def link(src: BasicBlock, target_index: int | None, kind: str) -> None:
        if target_index is None or target_index > last:
            target = "EXIT"
            back = False
        else:
            target = block_of[target_index]
            back = by_id[target].start <= src.start
        edges.append(Edge(src.id, target, kind, back))
        if target not in src.succ:
            src.succ.append(target)
        if target != "EXIT" and src.id not in by_id[target].pred:
            by_id[target].pred.append(src.id)

    for block in blocks:
        tail = code[block.end]
        nxt = block.end + 1 if block.end + 1 <= last else None
        if tail.op == "goto":
            link(block, labels[tail.label], "jump")
        elif tail.op == "iffalse":
            link(block, nxt, "true")
            link(block, labels[tail.label], "false")
        elif tail.op == "iftrue":
            link(block, labels[tail.label], "true")
            link(block, nxt, "false")
        elif tail.op in ("return", "halt", "endfunc"):
            link(block, None, "exit")
        else:
            link(block, nxt, "fall")
    return FunctionCFG(name, blocks, edges)


def _escape(text: str) -> str:
    return (text.replace("&", "#amp;").replace('"', "#quot;").replace("<", "#lt;")
            .replace(">", "#gt;"))


def to_mermaid(cfg: FunctionCFG) -> str:
    lines = ["flowchart TD", f'  ENTRY(["entry: {_escape(cfg.name)}"])']
    for block in cfg.blocks:
        body = "<br/>".join(_escape(i.text()) for i in block.instrs) or "(empty)"
        lines.append(f'  {block.id}["<b>{block.id}</b><br/>{body}"]')
    lines.append('  EXIT(["exit"])')
    link_styles = []
    count = 0
    if cfg.blocks:
        lines.append(f"  ENTRY --> {cfg.blocks[0].id}")
        count += 1
    for edge in cfg.edges:
        label = "" if edge.kind in ("fall", "jump", "exit") else f"|{edge.kind}|"
        arrow = "-.->" if edge.back else "-->"
        lines.append(f"  {edge.source} {arrow}{label} {edge.target}")
        if edge.back:
            link_styles.append(f"  linkStyle {count} stroke:#e11d48,stroke-width:2px")
        count += 1
    lines.extend(link_styles)
    return "\n".join(lines)
