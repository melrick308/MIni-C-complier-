# Progress log

Each entry records the task, status, files, tests and notes. The newest entry is at the bottom.

## T01–T18 · Core compiler + CLI — DONE (2026-10-08)
- **Files:** `compiler/` (common, lexer, syntax, semantic, ir, opt, runtime, render, pipeline, cli),
  `examples/programs/*.mc|.out`, `examples/expressions.json`, `tests/`
- **Tests:** 1136 passed; coverage of `compiler/` 97%; ruff clean
- **Notes:**
  - The grammar is data (`syntax/grammar.py`). FIRST/FOLLOW and the LL(1) table are computed; the only conflict
    is the documented dangling else.
  - Expression mode reproduces the original E/E'/T/T'/F grammar exactly (golden 17-step trace).
  - Phrase-level recovery handles a missing `;`; panic mode handles everything else (maximum 20 errors).
  - JSON spans are compact `[line, col, end_line, end_col]`; trees are serialised flat.
  - The optimizer (T35) was implemented early; differential tests guard it.

## T19–T29, T34 · API, web UI, e2e — DONE (2026-10-09)
- **Files:** `server/` (app, schemas, examples), `web/` (index.html, css/app.css, js/*, vendor/),
  `tests/test_api.py`, `tests/e2e/test_ui.py`
- **Tests:** 1158 passed (unit/API/CLI), 8 e2e passed with Playwright; ruff clean
- **Notes:**
  - Problems found during visual verification and fixed:
    - compile requests sent while one was in flight were dropped (now queued);
    - `<=` rendered as a ligature;
    - TAC labels overlapped the instruction index;
    - CodeMirror's default theme overrode the token colours;
    - the narrow-screen layout overlapped.
  - `pytest-playwright` must NOT be installed: its `page`/`base_url` fixtures clash with ours.

## T39–T40 · Docs + final validation — DONE (2026-10-09)
- **Files:** `README.md`, `PLAN.md`, `docs/*.md`, `docs/screenshots/`, `scripts/gen_error_catalog.py`
- **Validation:**
  - every README command was run successfully;
  - the error catalog is generated from real compiler output;
  - the full suite and the e2e suite are green.
- **Next (optional):** T36 arrays, T37 `read()` with stdin, T38 second front end.
