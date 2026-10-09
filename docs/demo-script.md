# Demo script (12–15 minutes)

**Setup before the evaluation:**
1. Run `uvicorn server.app:app`.
2. Open <http://localhost:8000>, zoom the browser to 125%, and choose the dark theme.
3. Keep a terminal open for the CLI backup and `pytest`.

The demo works without internet.

| # | Time | Do | Say / point at |
|---|---|---|---|
| 1 | 1 min | Show the pipeline bar, then open **Learn** | "Every chip is a compiler phase, with its own timing. Learn explains each phase for the code on screen." |
| 2 | 2 min | Switch to **Expression** mode and type `a + b * c` | Overview → Parse Tree → press ⏮ then ▶ Play: the tree grows step by step. Point out "'+' ∈ FOLLOW(T') → T' → ε": the parser knows when to stop without backtracking. AST: `*` sits below `+`. TAC: `t1 = b * c` comes first. |
| 3 | 1 min | Sample "Left associativity": `10 - 4 - 3` | The result is 3, not 9. Explain the inherited attribute in one sentence. |
| 4 | 1 min | Errors: `a + * b`, `(a + b`, `a + b)`, `a + @ + b`, `2(3)`, `-5` | Caret, column, found, expected list, hint. Point out the difference between a lexical and a syntax error. |
| 5 | 2 min | **Program** mode → sample *FizzBuzz* | Tokens (counts) → AST (click an `if`; the source highlights) → TAC (`ifFalse … goto`) → CFG (loop back-edge). |
| 6 | 2 min | Sample *Scopes and shadowing*, then *Semantic errors* | Symbols: the scope tree, with the inner `x` renamed `x_2` in the IR. Semantic errors: lossy assignment, condition not bool, undeclared name; later phases turn grey. |
| 7 | 3 min | Sample *Factorial (recursive)* → **Run ▸ Debug** | Step with ▶. The editor line follows execution and the call stack grows to `fact(1)` and unwinds. Drag the slider backwards (time travel). |
| 8 | 1 min | Sample *Syntax errors (recovery)* | Three errors are reported at once. Parse Steps → filter "recover": phrase-level and panic-mode recovery. |
| 9 | 30 s | Sample *Infinite loop* | The step limit stops it, which is the halting problem in practice. |
| 10 | 1 min | Sample *Optimizer showcase* → tick **Optimize** | The Optimized tab shows folding and propagation, removed lines are struck through, and the output is the same. |
| 11 | 30 s | **Grammar** tab | FIRST/FOLLOW sets and the LL(1) table; the only conflict is the dangling else, and how it is resolved. |
| 12 | 30 s | Terminal: `python -m pytest -q` | Over 1,150 tests, including the LL(1) proof and the optimizer differential tests. |

## Backup plan

If the browser fails, use the CLI:

```powershell
python -m compiler expr "a + b * c" --all
python -m compiler run examples\programs\04_factorial_recursive.mc --tac --cfg
python -m compiler run examples\programs\20_error_syntax.mc
```

Screenshots of every screen are in `docs/screenshots/`.

## Manual UI checklist

- [ ] Every sample in both modes loads and gives the expected result.
- [ ] The error caret lines up under the right character.
- [ ] The Parse Tree stepper grows the tree; the token highlight follows the lookahead.
- [ ] "Hide ε" works.
- [ ] Hovering a TAC line highlights its source.
- [ ] Clicking a CFG block highlights its source lines.
- [ ] The debugger moves forwards and backwards; the call stack and variables update.
- [ ] "Add missing variables" in Expression mode works.
- [ ] The theme toggle works and the layout holds on a narrow window.
- [ ] Stopping the server shows a friendly "Server not reachable" message.
