# Implementation plan (v2): MiniC Compiler Explorer

This is the single source of truth for agents working on this repository. Read it together with
`PROGRESS.md` before changing anything.

## Goal

An educational, interactive compiler built around a hand-written LL(1) recursive descent parser.
- **Expression mode** reproduces the original "Interactive Arithmetic Expression Analyzer".
- **Program mode** compiles MiniC (types, conditions, loops, functions, scopes) through every phase:
  lexer → parser → semantic analysis → TAC → CFG → optimizer → VM.
- Every phase can be inspected in the web UI.

## Frozen contracts

Change these only together with their tests, the UI and an entry in `docs/decisions.md`:

- Language: `docs/language-spec.md`, `docs/grammar.md`
- IR: `docs/ir-spec.md`
- Compile result JSON and diagnostics: `docs/architecture.md`
- Error codes: `compiler/common/diagnostics.py` (`CATALOG`); regenerate `docs/error-catalog.md` with `python scripts/gen_error_catalog.py`
- Limits: `compiler/common/limits.py`

## Task status

| Task | Description | Status |
|---|---|---|
| T01 | Scaffold, tooling, git | done |
| T02 | Positions, spans, diagnostics, limits | done |
| T03 | Lexer (keywords, operators, strings, comments, positions) | done |
| T04 | Grammar as data, FIRST/FOLLOW, LL(1) check | done |
| T05 | Parser base: tracing, parse tree, errors, depth guard | done |
| T06 | Expression profile (original grammar, golden trace) | done |
| T07 | MiniC expression levels (logic, comparison, unary, calls) | done |
| T08 | ASCII renderers + CLI skeleton | done |
| T09–T10 | Statements: declarations, assignment, print, if/else, while, for | done |
| T11–T12 | Symbol table, scopes, type checker | done |
| T13–T14 | TAC for expressions (short-circuit) and statements | done |
| T15 | VM + execution trace + limits | done |
| T16–T18 | Pipeline, CLI, golden suite (Milestone A) | done |
| T19 | CFG + Mermaid export | done |
| T20 | FastAPI API + tests | done |
| T21–T29 | Web UI: shell, editor, pipeline bar, all phase views, debugger, Expression mode (Milestone B) | done |
| T30 | Functions and recursion | done |
| T31 | break/continue, do-while, compound assignment | done |
| T32 | Panic-mode + phrase-level recovery | done |
| T33 | Hardening: limits, fuzzing, hostile input | done |
| T34 | Playwright end-to-end tests (Milestone C) | done |
| T35 | Optimizer + differential tests | done |
| T36 | Arrays | not started (optional) |
| T37 | `read()` + stdin | not started (optional) |
| T38 | Second (Python-like) front end | not started (stretch) |
| T39 | Documentation | done |
| T40 | Final validation | done — see PROGRESS.md |

## Working rules for agents

1. **Analyze.** Read this file, `PROGRESS.md` and every file you will touch.
2. **Plan.** Write a short plan into `PROGRESS.md`.
3. **Implement.** Make the smallest change that does the job. The core (`compiler/`) stays dependency-free, and phases import only earlier phases.
4. **Test.** Run `python -m pytest -q`, `ruff check .`, and for UI changes `python -m pytest -m e2e`.
5. **Debug.** Never edit golden expectations (`examples/programs/*.out`, golden tables in tests) to make code pass, unless a spec error is recorded in `docs/decisions.md`. After 3 failed attempts, log the blocker.
6. **Document and commit.** Update `PROGRESS.md`, then commit `T## summary`.

**Editing on Windows:** never round-trip UTF-8 source files through PowerShell
`Get-Content`/`Set-Content` (PowerShell 5.1 corrupts `→`, `ε`, `—`). Use an editor tool or Python.

## Extension recipes

- **New operator:** add the token (`lexer/tokens.py`), the production (`syntax/grammar.py`), the parser function, the type rule (`semantic/types.py`), the VM op, tests, and an LL(1) re-check (`test_first_follow.py`).
- **Arrays (T36):**
  - grammar: `F → id Suffix`, `Suffix → ( Args ) | [ Expr ] | ε`, plus assignment to `id [ Expr ]`;
  - TAC: `t = a[i]` and `a[i] = t`;
  - VM: a bounds check (`E_RT_INDEX`).
