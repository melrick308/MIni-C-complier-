# Progress log

Each entry: task, status, files, tests, notes. Newest at the bottom.

## T01–T18 · Core compiler + CLI — DONE (2026-10-08)
- Files: `compiler/` (common, lexer, syntax, semantic, ir, opt, runtime, render, pipeline, cli),
  `examples/programs/*.mc|.out`, `examples/expressions.json`, `tests/`
- Tests: 1136 passed; coverage of `compiler/` 97%; ruff clean
- Notes:
  - Grammar is data (`syntax/grammar.py`); FIRST/FOLLOW + LL(1) table computed; only conflict
    is the documented dangling else.
  - Expression mode reproduces the original E/E'/T/T'/F grammar exactly (golden 17-step trace).
  - Phrase-level recovery for missing `;`, panic mode for everything else (max 20 errors).
  - JSON spans are compact `[line, col, end_line, end_col]`; trees are serialised flat.
  - Optimizer (T35) implemented early; differential tests guard it.
- Next: T20 API
