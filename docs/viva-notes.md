# Viva notes

## Concepts demonstrated

- **Lexical analysis:** tokens and lexemes, maximal munch, keyword table, positions for error messages.
- **Context-free grammars:** derivations, parse trees vs ASTs, ambiguity, removing left recursion, left factoring.
- **Top-down predictive parsing:** recursive descent, FIRST/FOLLOW sets, the LL(1) table, ε-productions, and the dangling else.
- **Precedence and associativity:** precedence through grammar levels; left associativity through inherited attributes (an L-attributed SDD).
- **Error handling:** precise diagnostics, phrase-level recovery and panic-mode recovery with synchronising tokens.
- **Semantic analysis:** symbol tables as a stack of hash maps, nested scopes, shadowing, static type checking, type widening.
- **Intermediate code:** syntax-directed translation to three address code and quadruples, labels and jumps, short-circuit evaluation, function calls with params.
- **Control flow graphs:** basic blocks, the leaders algorithm, back edges as loops.
- **Optimization:** constant folding and propagation, algebraic identities, dead and unreachable code.
- **Run-time environment:** activation records (frames), the call stack, recursion; limits and the halting problem.

## Likely questions

| Question | Answer |
|---|---|
| Why not a universal compiler for every language? | Every language has its own grammar, and recursive descent is written for one specific grammar. Real multi-language compilers (GCC, LLVM) share an intermediate representation, not a parser. MiniC covers every kind of construct, and its AST/TAC is that shared layer. |
| Why can't you use `E → E + T`? | `E()` would call itself before consuming any token, which is infinite recursion. We rewrite it as `E → T E'`. |
| How is precedence enforced? | One grammar level per precedence level. `*` is parsed deeper (in `T`), so it binds tighter than `+`. |
| The grammar is right-recursive. Why is `a - b - c` left-associative? | `EPrime()` receives the left operand as an inherited attribute and folds each new operand onto it. Show `10 - 4 - 3 = 3`. |
| Is it LL(1)? Does it backtrack? | It is LL(1) with no backtracking. The table is computed from the grammar and a test checks it. The single conflict, the dangling else, is resolved by binding `else` to the nearest `if`. |
| When does `T'` choose ε? | When the lookahead is in FOLLOW(T') = { + - ) $ } (Expression mode). |
| Assignment and call both start with an identifier. How does the parser decide? | Left factoring: `IdStmt → id IdTail`; the next token (`=`, `(`, `+=` …) chooses the branch. |
| Parse tree vs AST? | The parse tree contains every grammar symbol, including ε. The AST keeps only meaning (operators, operands, statements) and is what later phases use. |
| Lexical vs syntax vs semantic vs runtime error? | `@` is a lexical error, a missing `;` is a syntax error, an undeclared variable is a semantic error, and dividing by zero is a runtime error. Each one is shown by the samples. |
| How does error recovery work? | A missing `;` is reported and assumed (phrase level). Anything else: skip to a synchronising token such as `;`, `}` or a statement keyword, then continue (panic mode). Only one error is reported per token. |
| How are scopes implemented? | As a stack of dictionaries: push on `{`, pop on `}`, and resolve a name from the innermost scope outwards. Shadowed variables get unique IR names. |
| How is a `while` loop translated? | `L1: t = cond; ifFalse t goto L2; body; goto L1; L2:`. Show the TAC and the CFG back edge. |
| How does `&&` avoid evaluating its right side? | With a jump: `t = a; ifFalse t goto L; t = b; L:`. The *Short-circuit* sample divides by zero only on the skipped side. |
| What is a basic block? | A maximal straight-line sequence with a single entry and a single exit. Leaders are the first instruction, every jump target, and every instruction that follows a jump. |
| How does recursion work at run time? | `call` pushes a frame (params, locals, temps, return address); `return` pops it and stores the result in the caller. Show the debugger. |
| Why the step limit? | Whether an arbitrary program halts is undecidable (the halting problem), so execution is bounded. |
| How do you know the optimizer is correct? | Differential testing: hundreds of random programs run with and without optimization must produce identical output. |
| Why `eval` is never used | It would be a security risk, and it would bypass the compiler we are demonstrating. All evaluation happens on the generated TAC. |
| Complexity? | Lexing and parsing are O(n), since every token is consumed once with no backtracking. |
| Recursive descent vs LR parsers? | LR (yacc/bison) is bottom-up and table-driven. It handles left recursion and a larger class of grammars, but its tables are generated and hard to read. Recursive descent is hand-written and readable, and is limited to LL grammars. |

## Known limitations and how to defend them

| Limitation | Defense |
|---|---|
| Not a real-world language | The scope is deliberate: every phase of a real compiler is present and visible. |
| VM instead of machine code | The VM proves the IR is correct. Instruction selection from TAC to assembly is a direct next step. |
| Ints don't overflow like C | A documented choice (D11). 32-bit wrapping would be a one-line VM change. |
| No arrays or strings as values | Kept out of scope. The grammar and IR are designed to extend (`F → id [ Expr ]`). |
| Error recovery can still cascade in rare cases | Cascade suppression plus a 20-error cap; sync sets come from FOLLOW sets. |

## Numbers to remember

- 7 phases and 23 sample programs.
- More than 1,150 automated tests, with 97% coverage of the compiler package.
- The grammar has about 50 non-terminals, and the only LL(1) conflict is the dangling else.
