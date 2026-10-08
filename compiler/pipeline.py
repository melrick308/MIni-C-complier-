"""Runs the compiler phases in order, gating each on the previous one, and returns one
JSON-serialisable result containing every intermediate artefact."""

from __future__ import annotations

import time
from collections import Counter

from .common import limits
from .common.diagnostics import ERROR, INPUT, Diagnostic, sort_diagnostics
from .common.source import SourceFile
from .ir.cfg import build_cfg
from .ir.tac_gen import generate_expression, generate_program
from .lexer.lexer import Lexer
from .opt.optimizer import optimize as run_optimizer
from .runtime.vm import VM
from .semantic.analyzer import analyze
from .semantic.symbols import safe_ir_name
from .syntax import ast as A
from .syntax.grammar import EXPRESSION, MINIC
from .syntax.parse_tree import parse_tree_to_dict
from .syntax.parser import parse

PROGRAM = "program"
PHASES = ["lexical", "syntax", "semantic", "ir", "cfg", "optimize", "execution"]
STATEMENT_KINDS = {"VarDecl", "Assign", "If", "While", "DoWhile", "For", "Return", "Break",
                   "Continue", "Print", "CallStmt", "Block", "FuncDecl"}


class _Clock:
    def __init__(self):
        self.start = time.perf_counter()

    def ms(self) -> float:
        return round((time.perf_counter() - self.start) * 1000, 3)


def compile_source(source: str, mode: str = PROGRAM, *, optimize: bool = False, run: bool = True,
                   variables: dict | None = None) -> dict:
    """Compile (and optionally run) MiniC source, or analyze one arithmetic expression."""
    expression_mode = mode == EXPRESSION
    variables = dict(variables or {})
    phases: dict[str, dict] = {}
    diags: list[Diagnostic] = []
    result: dict = {"mode": EXPRESSION if expression_mode else PROGRAM, "phases": phases}
    ast_root: A.Node | None = None

    def finish(failed: str | None) -> dict:
        for name in PHASES:
            if name not in phases:
                phases[name] = {"status": "skipped",
                                "reason": f"Skipped because the {failed} phase failed"
                                if failed else "Not applicable"}
        if "syntax" in phases and phases["syntax"].get("status") != "skipped":
            phases["syntax"]["ast"] = A.ast_to_dict(ast_root)
            if expression_mode and ast_root is not None:
                phases["syntax"]["ast_infix"] = A.to_infix(ast_root)
        ordered = sort_diagnostics(diags)
        result["diagnostics"] = [d.to_dict() for d in ordered]
        result["failed_phase"] = failed
        result["success"] = failed is None and not any(d.severity == ERROR for d in ordered)
        result["timings"] = {k: v.get("ms") for k, v in phases.items() if "ms" in v}
        return result

    # ------------------------------------------------------------------ input
    max_chars = limits.MAX_EXPRESSION_CHARS if expression_mode else limits.MAX_SOURCE_CHARS
    line_count = source.count("\n") + 1
    if len(source) > max_chars or (not expression_mode and line_count > limits.MAX_SOURCE_LINES):
        diags.append(Diagnostic(
            ERROR, INPUT, "E_INPUT_TOO_LONG",
            f"Input is too long (limit: {max_chars:,} characters"
            + ("" if expression_mode else f", {limits.MAX_SOURCE_LINES} lines") + ")"))
        return finish("input")
    source_file = SourceFile(source)
    result["source"] = {"chars": len(source), "lines": source_file.line_count}

    # ---------------------------------------------------------------- lexical
    clock = _Clock()
    tokens, lex_error = Lexer(source_file).tokenize()
    categories = Counter(t.to_dict()["category"] for t in tokens if t.type.value != "EOF")
    phases["lexical"] = {
        "status": "error" if lex_error else "ok",
        "ms": clock.ms(),
        "tokens": [t.to_dict() for t in tokens],
        "stats": {"tokens": len(tokens) - 1, "by_category": dict(categories),
                  "lines": source_file.line_count, "chars": len(source)},
    }
    if lex_error:
        diags.append(lex_error)
        return finish("lexical")

    # ----------------------------------------------------------------- syntax
    clock = _Clock()
    parsed = parse(tokens, EXPRESSION if expression_mode else MINIC)
    ast_root = parsed.ast
    tree = parse_tree_to_dict(parsed.parse_tree)
    ast_nodes = list(A.walk_postorder(ast_root)) if ast_root is not None else []
    phases["syntax"] = {
        "status": "error" if parsed.errors else "ok",
        "ms": clock.ms(),
        "parse_tree": tree,
        "trace": [s.to_dict() for s in parsed.trace],
        "trace_truncated": parsed.trace_truncated,
        "stats": {
            "trace_steps": len(parsed.trace),
            "parse_tree_nodes": tree["count"] if tree else 0,
            "ast_nodes": len(ast_nodes),
            "ast_depth": _depth(ast_root),
            "statements": sum(1 for n in ast_nodes if n.KIND in STATEMENT_KINDS),
            "functions": sum(1 for n in ast_nodes if n.KIND == "FuncDecl"),
            "errors": len(parsed.errors),
            "recoveries": sum(1 for s in parsed.trace if s.action == "recover"),
        },
    }
    if parsed.errors:
        diags.extend(parsed.errors)
        return finish("syntax")

    # --------------------------------------------------------------- semantic
    clock = _Clock()
    if expression_mode:
        names = list(dict.fromkeys(n.name for n in ast_nodes if isinstance(n, A.Var)))
        missing = [n for n in names if n not in variables]
        phases["semantic"] = {
            "status": "ok", "ms": clock.ms(), "identifiers": names, "missing": missing,
            "symbols": [{"name": n, "value": variables.get(n), "defined": n in variables}
                        for n in names],
            "stats": {"identifiers": len(names), "missing": len(missing)},
        }
        symbol_names = {safe_ir_name(n): n for n in names}
    else:
        sem = analyze(ast_root)
        diags.extend(sem.diagnostics)
        kinds = Counter(s.kind for s in sem.symbols)
        phases["semantic"] = {
            "status": "error" if sem.errors else "ok",
            "ms": clock.ms(),
            "scopes": [s.to_dict() for s in sem.scopes],
            "symbols": [s.to_dict() for s in sem.symbols],
            "stats": {"scopes": len(sem.scopes), "symbols": len(sem.symbols),
                      "variables": kinds.get("var", 0), "parameters": kinds.get("param", 0),
                      "functions": kinds.get("func", 0), "errors": len(sem.errors),
                      "warnings": len(sem.diagnostics) - len(sem.errors)},
        }
        symbol_names = {s.ir_name: s.name for s in sem.symbols}
        if sem.errors:
            return finish("semantic")
    result["symbol_names"] = symbol_names

    # --------------------------------------------------------------------- IR
    clock = _Clock()
    ir = generate_expression(ast_root) if expression_mode else generate_program(ast_root,
                                                                                sem.symbols)
    shown = [i for i in ir.instrs if not (expression_mode and i.op == "halt")]
    phases["ir"] = {
        "status": "ok",
        "ms": clock.ms(),
        "tac": [i.to_dict() for i in shown],
        "functions": {name: {"params": f.params, "start": f.start, "end": f.end}
                      for name, f in ir.functions.items()},
        "stats": _ir_stats(shown, ir.temps),
    }

    # -------------------------------------------------------------------- CFG
    run_ir = ir
    if expression_mode:
        phases["cfg"] = {"status": "skipped", "reason": "A single expression has no control flow"}
        phases["optimize"] = {"status": "skipped", "reason": "Not used in Expression mode"}
    else:
        clock = _Clock()
        cfgs = build_cfg(ir)
        phases["cfg"] = {
            "status": "ok", "ms": clock.ms(),
            "functions": [c.to_dict() for c in cfgs],
            "stats": {"functions": len(cfgs), "blocks": sum(len(c.blocks) for c in cfgs),
                      "edges": sum(len(c.edges) for c in cfgs),
                      "loops": sum(c.loops for c in cfgs)},
        }
        if optimize:
            clock = _Clock()
            opt = run_optimizer(ir)
            run_ir = opt.ir
            phases["optimize"] = {
                "status": "ok", "ms": clock.ms(),
                "tac": [i.to_dict() for i in opt.ir.instrs],
                "marks": {str(k): v for k, v in opt.marks.items()},
                "changes": opt.changes,
                "stats": {"before": len(ir.instrs), "after": len(opt.ir.instrs),
                          "removed": opt.removed,
                          "percent": round(100 * opt.removed / max(1, len(ir.instrs)), 1)},
            }
        else:
            phases["optimize"] = {"status": "skipped",
                                  "reason": "Optimization is off (turn on 'Optimize')"}

    # -------------------------------------------------------------- execution
    if expression_mode:
        missing = phases["semantic"]["missing"]
        if missing:
            phases["execution"] = {"status": "skipped",
                                   "reason": "Values are missing for: " + ", ".join(missing)}
            result["evaluation"] = {
                "status": "skipped", "value": None, "missing": missing,
                "message": "Cannot evaluate: no value for " + ", ".join(missing)}
            return finish(None)
        initial = {safe_ir_name(k): v for k, v in variables.items()}
        vm = VM(run_ir, division="true", mode="expression", initial=initial)
    elif not run:
        phases["execution"] = {"status": "skipped", "reason": "Run is turned off"}
        return finish(None)
    else:
        vm = VM(run_ir)
    clock = _Clock()
    executed = vm.run()
    data = executed.to_dict()
    data["status"] = "ok" if executed.status == "ok" else "error"
    data["kind"] = executed.status
    data["ms"] = clock.ms()
    data["optimized"] = run_ir is not ir
    data["stats"] = {"steps": executed.steps, "output_lines": len(executed.output),
                     "max_call_depth": executed.max_depth}
    phases["execution"] = data
    if executed.error is not None:
        diags.append(executed.error)
    if expression_mode:
        if executed.status == "ok":
            result["evaluation"] = {"status": "ok", "value": vm.fmt(executed.value),
                                    "missing": [], "message": None}
        else:
            result["evaluation"] = {"status": "error", "value": None, "missing": [],
                                    "message": executed.error.message}
    return finish(None)


def _depth(root: A.Node | None) -> int:
    if root is None:
        return 0
    best = 0
    stack = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        best = max(best, depth)
        stack.extend((c, depth + 1) for c in node.children())
    return best


def _ir_stats(instrs, temps: int) -> dict:
    ops = Counter(i.op for i in instrs)
    return {
        "instructions": sum(c for op, c in ops.items() if op != "label"),
        "labels": ops.get("label", 0),
        "temporaries": temps,
        "jumps": ops.get("goto", 0) + ops.get("iffalse", 0) + ops.get("iftrue", 0),
        "calls": ops.get("call", 0),
        "by_op": dict(ops),
    }
