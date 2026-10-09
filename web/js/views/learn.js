import { el, plural, viewHead } from "../dom.js";

const PHASES = {
  lexical: {
    title: "1 · Lexical analysis",
    what: "The scanner reads characters left to right and groups them into tokens — keywords, identifiers, numbers, operators. It uses maximal munch (the longest match wins, so <= is one token) and discards whitespace and comments. Every token keeps its line and column for error messages.",
    tip: "Why a separate lexer? The parser can then work with a small alphabet of tokens instead of characters, which keeps the grammar simple.",
    yours: (r, s) => `Your code produced ${plural(s.tokens, "token")} over ${plural(s.lines, "line")}: ` +
      Object.entries(s.by_category).map(([k, v]) => `${v} ${k}${v === 1 ? "" : "s"}`).join(", ") + ".",
  },
  syntax: {
    title: "2 · Syntax analysis (recursive descent)",
    what: "Each grammar non-terminal is one function (E(), EPrime(), IfStmt(), …). A function looks at one lookahead token and picks a production with the FIRST/FOLLOW sets — LL(1) parsing, no backtracking. Left recursion was removed (E → T E') and shared prefixes were left-factored (an identifier can start an assignment or a call).",
    tip: "Associativity: EPrime() receives the left operand as an inherited attribute and folds each new operand onto it, so a - b - c becomes ((a - b) - c) even though the grammar is right-recursive.",
    yours: (r, s) => `The parser took ${plural(s.trace_steps, "step")}, built a parse tree of ${plural(s.parse_tree_nodes, "node")} and an AST of ${plural(s.ast_nodes, "node")}` +
      (r.mode === "program" ? ` with ${plural(s.statements, "statement")} and ${plural(s.functions, "function")}.` : ".") +
      (s.errors ? ` It found ${plural(s.errors, "syntax error")} and recovered ${plural(s.recoveries, "time")}.` : ""),
  },
  semantic: {
    title: "3 · Semantic analysis",
    what: "The AST is checked for meaning: every name must be declared before use (scopes are a stack of hash tables — push on '{', pop on '}'), types must match (int, float, bool), conditions must be bool, calls must pass the right arguments, and non-void functions must return a value.",
    tip: "Functions are collected in a first pass, so they can be called before they are defined. Shadowed variables get unique IR names (x, x_2).",
    yours: (r, s) => (r.mode === "expression"
      ? `The expression uses ${plural(s.identifiers, "identifier")}; ${s.missing ? `${s.missing} still need values` : "all have values"}.`
      : `${plural(s.scopes, "scope")}, ${plural(s.variables, "variable")}, ${plural(s.parameters, "parameter")} and ${plural(s.functions, "function")}; ${plural(s.errors, "error")} and ${plural(s.warnings, "warning")}.`),
  },
  ir: {
    title: "4 · Intermediate code (TAC)",
    what: "Syntax-directed translation turns the AST into three address code: each instruction has at most one operator, intermediate results live in temporaries (t1, t2…), and if/while/for become labels and conditional jumps. && and || jump over their right side (short-circuit).",
    tip: "while (c) S  →  L1: ifFalse c goto L2; S; goto L1; L2:",
    yours: (r, s) => `${plural(s.instructions, "instruction")}, ${plural(s.temporaries, "temporary", "temporaries")}, ${plural(s.labels, "label")} and ${plural(s.jumps, "jump")}.`,
  },
  cfg: {
    title: "5 · Control flow graph",
    what: "The code is split into basic blocks — straight-line sequences with one entry and one exit — using the leaders algorithm (first instruction, jump targets, and instructions after jumps). Edges show where control can go next.",
    tip: "An edge back to an earlier block is a loop. Optimizers and register allocators work on this graph.",
    yours: (r, s) => `${plural(s.blocks, "basic block")} and ${plural(s.edges, "edge")} in ${plural(s.functions, "function")}; ${plural(s.loops, "loop")} detected.`,
  },
  optimize: {
    title: "6 · Optimization",
    what: "Machine-independent passes improve the TAC without changing behaviour: constant folding, constant propagation inside basic blocks, algebraic simplification, removal of dead temporaries, unreachable code and redundant jumps.",
    tip: "Correctness check: the test suite runs hundreds of random programs with and without the optimizer and requires identical output.",
    yours: (r, s) => `${s.before} → ${s.after} instructions (${s.percent}% smaller).`,
  },
  execution: {
    title: "7 · Execution",
    what: "A small virtual machine interprets the three address code: it keeps global variables, a call stack of frames for function calls, and prints output. Every executed instruction is recorded so you can step forwards and backwards.",
    tip: "Infinite loops cannot be detected in general (the halting problem), so execution stops after 100,000 instructions.",
    yours: (r, s) => `${s.steps.toLocaleString()} instructions executed, ${plural(s.output_lines, "line")} printed, maximum call depth ${s.max_call_depth}.`,
  },
};

export function render(container, ctx) {
  const result = ctx.result;
  const order = ctx.mode === "expression" ? ["lexical", "syntax", "semantic", "ir", "execution"] : Object.keys(PHASES);
  container.append(viewHead("How the compiler works", "Each phase explained — with what it did to your code."));
  container.append(el("div", { class: "learn-grid" }, ...order.map((id) => {
    const info = PHASES[id];
    const phase = result?.phases[id];
    let yours = "Compile to see what this phase did with your code.";
    if (phase?.status === "skipped") yours = phase.reason || "Skipped.";
    else if (phase?.stats) yours = info.yours(result, phase.stats);
    const status = phase?.status;
    return el("div", { class: "card learn" + (ctx.state.learnFocus === id ? " active" : "") },
      el("h3", {}, el("span", { class: `act ${status === "ok" ? "accept" : status === "error" ? "error" : ""}` }, status || "–"), info.title),
      el("p", {}, info.what),
      el("p", {}, el("strong", {}, "Your code: "), yours),
      el("div", { class: "tip" }, "💡 ", info.tip));
  })));
}
