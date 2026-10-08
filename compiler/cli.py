"""Command-line interface.

    python -m compiler run examples/programs/factorial_loop.mc --tac
    python -m compiler expr "a + b * (c - 2)" --var a=3 --var b=4 --var c=7 --all
    python -m compiler repl
"""

from __future__ import annotations

import argparse
import json
import sys

from .pipeline import compile_source
from .render import ascii as R
from .syntax.grammar import EXPRESSION


def _parse_vars(items: list[str]) -> dict:
    variables = {}
    for item in items or []:
        name, _, value = item.partition("=")
        number = float(value)
        variables[name.strip()] = int(number) if number.is_integer() and "." not in value else number
    return variables


def _report(result: dict, source: str, args) -> int:
    phases = result["phases"]
    show_all = args.all

    def section(title: str, body: str) -> None:
        print(f"\n== {title} " + "=" * max(0, 60 - len(title)))
        print(body)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1
    if (show_all or args.tokens) and phases["lexical"].get("tokens"):
        section("Tokens", R.token_table(phases["lexical"]["tokens"]))
    syntax = phases["syntax"]
    if (show_all or args.trace) and syntax.get("trace"):
        section("Parsing steps", R.trace_table(syntax["trace"]))
    if (show_all or args.tree) and syntax.get("parse_tree"):
        section("Parse tree", R.tree(syntax["parse_tree"], R.parse_tree_label))
    if (show_all or args.ast) and syntax.get("ast"):
        section("Abstract syntax tree", R.tree(syntax["ast"], R.ast_label))
    sem = phases["semantic"]
    if (show_all or args.symbols) and sem.get("symbols"):
        if result["mode"] == EXPRESSION:
            body = "\n".join(f"{s['name']:<12} {s['value'] if s['defined'] else '(no value)'}"
                             for s in sem["symbols"])
        else:
            body = "\n".join(f"{s['name']:<12} {s['kind']:<6} {s['type']:<6} scope {s['scope']}"
                             f"  line {s['line']}" for s in sem["symbols"])
        section("Symbol table", body)
    if (show_all or args.tac) and phases["ir"].get("tac"):
        section("Three address code", R.tac_listing(phases["ir"]["tac"]))
    if (show_all or args.cfg) and phases["cfg"].get("functions"):
        body = []
        for fn in phases["cfg"]["functions"]:
            body.append(f"[{fn['name']}] {len(fn['blocks'])} blocks, {fn['loops']} loop(s)")
            for b in fn["blocks"]:
                body.append(f"  {b['id']}: " + " | ".join(b["text"]) + f"  -> {', '.join(b['succ'])}")
        section("Control flow graph", "\n".join(body))
    if phases["optimize"].get("status") == "ok":
        stats = phases["optimize"]["stats"]
        section("Optimized TAC", R.tac_listing(phases["optimize"]["tac"])
                + f"\n  ({stats['before']} → {stats['after']} instructions)")
    execution = phases["execution"]
    if args.exec_trace and execution.get("trace"):
        body = "\n".join(f"{s['step']:>5}  line {s['line'] or '-':<4} {s['text']}"
                         + ("   " + ", ".join(f"{w['name']}={w['value']}" for w in s["writes"])
                            if s.get("writes") else "")
                         for s in execution["trace"])
        section("Execution trace", body)
    if result["diagnostics"]:
        section("Diagnostics", R.diagnostics(source, result["diagnostics"]))
    if result["mode"] == EXPRESSION:
        evaluation = result.get("evaluation")
        if result["failed_phase"]:
            print(f"\n✗ Invalid expression ({result['failed_phase']} error)")
        else:
            print(f"\n✓ Valid expression: {phases['syntax'].get('ast_infix', '')}")
            if evaluation:
                print("Result = " + (evaluation["value"] if evaluation["status"] == "ok"
                                     else evaluation["message"]))
    elif execution.get("output") is not None:
        section("Program output", "\n".join(execution["output"]) or "(no output)")
    if result["failed_phase"]:
        return 1
    return 2 if execution.get("status") == "error" else 0


def _add_view_flags(p: argparse.ArgumentParser) -> None:
    for flag in ("tokens", "trace", "tree", "ast", "symbols", "tac", "cfg", "all", "json"):
        p.add_argument(f"--{flag}", action="store_true")
    p.add_argument("--exec-trace", action="store_true", dest="exec_trace")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="python -m compiler",
                                     description="MiniC Compiler Explorer (CLI)")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="compile and run a MiniC program")
    run.add_argument("file")
    run.add_argument("--optimize", action="store_true")
    _add_view_flags(run)
    expr = sub.add_parser("expr", help="analyze one arithmetic expression")
    expr.add_argument("expression")
    expr.add_argument("--var", action="append", default=[], metavar="NAME=VALUE")
    _add_view_flags(expr)
    sub.add_parser("repl", help="interactive expression analyzer")
    args = parser.parse_args(argv)

    if args.command == "run":
        with open(args.file, encoding="utf-8") as fh:
            source = fh.read()
        result = compile_source(source, optimize=args.optimize)
        return _report(result, source, args)
    if args.command == "expr":
        result = compile_source(args.expression, EXPRESSION, variables=_parse_vars(args.var))
        return _report(result, args.expression, args)
    return repl()


def repl() -> int:
    print("Expression analyzer. Commands: :vars a=3 b=4   :clear   :quit")
    variables: dict = {}
    flags = argparse.Namespace(tokens=True, trace=False, tree=False, ast=True, symbols=False,
                               tac=True, cfg=False, all=False, json=False, exec_trace=False)
    while True:
        try:
            line = input("expr> ").strip()
        except EOFError:
            return 0
        if not line:
            continue
        if line in (":quit", ":q"):
            return 0
        if line.startswith(":vars"):
            variables.update(_parse_vars(line.split()[1:]))
            print("variables:", variables)
            continue
        if line == ":clear":
            variables.clear()
            continue
        _report(compile_source(line, EXPRESSION, variables=variables), line, flags)
