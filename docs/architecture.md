# Architecture

```
┌──────────────────────────── Browser (web/) ────────────────────────────┐
│ CodeMirror editor · pipeline bar · phase views · step debugger          │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ POST /api/compile   (JSON, gzip)
┌──────────────────────────────▼─────────────────────────────────────────┐
│ server/ (FastAPI): request validation, limits, static hosting          │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ compile_source(source, mode, optimize, run, variables)
┌──────────────────────────────▼─────────────────────────────────────────┐
│ compiler/ (pure Python, no dependencies)                                │
│  lexer → syntax (parser + trace + parse tree + AST) → semantic          │
│  → ir (TAC, CFG) → opt → runtime (VM)                                   │
│  pipeline.py gates and times each phase; cli.py is a second front end   │
└────────────────────────────────────────────────────────────────────────┘
```

## Phase boundaries

| Module | Consumes | Produces |
|---|---|---|
| `lexer/lexer.py` | source text | `Token` list (ending in EOF), or the first lexical error |
| `syntax/parser.py` | tokens | AST, parse tree, trace, syntax errors (with recovery) |
| `semantic/analyzer.py` | AST | scopes, symbols, types written onto the AST, semantic diagnostics |
| `ir/tac_gen.py` | typed AST + symbols | `IRProgram` (instructions + function table) |
| `ir/cfg.py` | IR | basic blocks, edges and Mermaid text per function |
| `opt/optimizer.py` | IR | optimized IR, change counts, per-instruction marks |
| `runtime/vm.py` | IR | output, execution trace, final globals, runtime error |

Each module imports only from earlier phases and from `common/`. The parser never checks types,
the semantic pass never emits code, and the VM never reads the AST.

## The compile result

`compile_source` never raises for bad input. Every problem becomes a diagnostic:

```json
{
  "mode": "program",
  "success": true,
  "failed_phase": null,
  "phases": {
    "lexical":   {"status": "ok", "ms": 0.4, "tokens": [...], "stats": {...}},
    "syntax":    {"status": "ok", "ms": 1.2, "ast": {...}, "parse_tree": {...}, "trace": [...], "stats": {...}},
    "semantic":  {"status": "ok", "scopes": [...], "symbols": [...], "stats": {...}},
    "ir":        {"status": "ok", "tac": [...], "stats": {...}},
    "cfg":       {"status": "ok", "functions": [{"name": "main", "blocks": [...], "edges": [...], "mermaid": "..."}]},
    "optimize":  {"status": "skipped", "reason": "..."},
    "execution": {"status": "ok", "output": [...], "trace": [...], "globals": {...}, "stats": {...}}
  },
  "diagnostics": [{"severity": "error", "phase": "syntax", "code": "E_SYN_MISSING_SEMICOLON",
                   "message": "...", "span": [1, 10, 1, 10], "line": 1, "col": 10,
                   "found": "'int'", "expected": ["';'"], "hint": "...", "related": null}],
  "symbol_names": {"x_2": "x"},
  "timings": {"lexical": 0.4, ...}
}
```

- Spans are compact `[line, col, end_line, end_col]` arrays with 1-based columns.
- Trees are serialised **flat** (`{"root": id, "nodes": [{id, parent, children: [ids], …}]}`), so deep programs never produce deeply nested JSON.
- A phase after a failed phase is `skipped`, with a reason.
- Compile errors are HTTP 200 results. Only malformed requests return 422.

## Front end

The front end is plain ES modules with no build step:

| File | Role |
|---|---|
| `main.js` | state, modes, compile requests, tab routing |
| `editor.js` | CodeMirror: MiniC highlighting, error squiggles, cross-highlighting, execution line, line-hit gutter |
| `components.js` | step player, SVG tree layout, collapsible outline tree |
| `views/*.js` | one module per tab |

All user text is inserted through text nodes, never `innerHTML`. The only `innerHTML` is the
SVG produced by Mermaid in strict security mode from escaped TAC text.
