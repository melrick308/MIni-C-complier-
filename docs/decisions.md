# Design decisions

| # | Decision | Why |
|---|---|---|
| D1 | Build one C-like teaching language (MiniC) instead of a "universal" compiler | Recursive descent needs one fixed grammar. Real compilers share an IR between languages, not a parser. MiniC covers every kind of construct: types, conditions, loops, functions, scopes. |
| D2 | Keep the original arithmetic analyzer as Expression mode, with its exact grammar | The original problem statement stays fully demonstrable. Both profiles share the same parser functions. |
| D3 | `F → ( E ) \| id \| num` instead of `id` for both | The lexer emits separate IDENTIFIER and NUMBER tokens. The language is the same. |
| D4 | 1-based columns everywhere, EOF at `len + 1` | The original examples were inconsistent (one used 0-based columns). |
| D5 | Left associativity through an inherited attribute in `X'` functions | The grammar is right-recursive; copying the parse tree's shape would make `a - b - c` right-associative. |
| D6 | Grammar stored as data; FIRST/FOLLOW computed | One source of truth, and a test proves the grammar is LL(1). |
| D7 | Strict FOLLOW check in Expression mode, lenient in Program mode | Expression mode gives exact "expected" lists. Program mode reports a missing `;` at the right place. |
| D8 | Phrase-level recovery for `;`, panic mode for everything else, at most 20 errors | Several real errors per compile with very few cascades. |
| D9 | Conditions must be `bool` | Clearer type rules than C, and it catches mistakes. |
| D10 | `int / int` truncates toward zero in Program mode; true division in Expression mode | C semantics for the language; the original statement expects `7 / 2 = 3.5`. |
| D11 | Arbitrary-precision ints (capped at 10^300) | Python ints. Results are deterministic and easy to explain. |
| D12 | Functions hoisted, top-level only; script-style entry point | Simple two-pass semantic analysis; no `main` boilerplate. |
| D13 | Execute TAC on a VM instead of interpreting the AST | Proves the generated IR is correct and allows instruction-level stepping. |
| D14 | Explicit `(float)` conversion instructions | Type conversion becomes visible in the IR, and the VM needs no type information. |
| D15 | Step, time, call-depth and output limits | Infinite loops are undecidable in general (the halting problem). |
| D16 | No database; stateless API | Nothing needs persisting. The client sends the source and variables with each request. |
| D17 | Flat JSON trees, compact spans, gzip | Large programs stay small and never hit JSON nesting limits. |
| D18 | Vanilla JS with vendored CodeMirror 5 and Mermaid | No build tooling, and the demo works offline. |
| D19 | Optimizer implemented early, guarded by differential tests | The optimizer must never change behaviour; random programs are run both ways. |
| D20 | User names that look like `t1` or `L1` get a `_` suffix in the IR | Prevents collisions with generated temporaries and labels. |
| D21 | Maximal munch means `a ++ b` lexes as `a`, `++`, `b` | Same as C. In Expression mode it is reported as an unexpected `'++'`. |
