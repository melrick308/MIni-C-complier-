// Parse tree and AST views (graph for small trees, outline for large ones).
import { outlineTree, stepper, svgTree } from "../components.js";
import { el, empty, stat, viewHead } from "../dom.js";

const GRAPH_LIMIT = 260;
const STATEMENTS = new Set(["Program", "FuncDecl", "Block", "VarDecl", "Assign", "If", "While", "DoWhile",
  "For", "Return", "Break", "Continue", "Print", "CallStmt", "Param"]);

function modeToggle(ctx, key, count) {
  const current = ctx.state[key] || (count <= GRAPH_LIMIT ? "graph" : "outline");
  const button = (mode, label) => el("button", {
    class: "filter" + (current === mode ? " active" : ""),
    onclick: () => ctx.set({ [key]: mode }),
  }, label);
  return [current, el("span", { class: "filters", style: { margin: 0 } }, button("graph", "Graph"), button("outline", "Outline"))];
}

/* -------------------------------------------------------------- parse tree */
export function renderParseTree(container, ctx) {
  const syntax = ctx.result?.phases.syntax;
  if (!syntax || syntax.status === "skipped" || !syntax.parse_tree) {
    container.append(empty("No parse tree", "The parser runs after a successful lexical analysis."));
    return;
  }
  const tree = syntax.parse_tree;
  const trace = syntax.trace;
  const [mode, toggle] = modeToggle(ctx, "parseTreeMode", tree.count);
  const hideEps = ctx.state.hideEpsilon;
  const step = ctx.state.parseStep ?? trace.length;
  const building = ctx.state.parseStep !== null && ctx.state.parseStep !== undefined;
  const epsToggle = el("label", { class: "toggle" },
    el("input", { type: "checkbox", checked: hideEps, onchange: (e) => ctx.set({ hideEpsilon: e.target.checked }) }), "Hide ε");
  container.append(viewHead("Parse tree", "Concrete syntax: every grammar symbol the recursive descent parser expanded.", epsToggle, toggle));
  container.append(el("div", { class: "stats" },
    stat(tree.count, "nodes"), stat(trace.length, "parser steps"),
    stat(syntax.stats.errors, "syntax errors")));
  container.append(stepper({
    key: "parse",
    count: trace.length,
    value: step,
    onChange: (v) => ctx.setParseStep(v),
    describe: (v) => describeStep(trace[v - 1]),
  }));
  const selected = ctx.state.selectedParse;
  const byId = new Map(tree.nodes.map((n) => [n.id, n]));
  const skip = (n) => hideEps && (n.kind === "epsilon"
    || (n.children.length === 1 && byId.get(n.children[0])?.kind === "epsilon"));
  const stateOf = (n) => {
    if (!building || n.step === undefined) return "";
    if (n.step > step) return "ghost";
    return n.step === step ? "new" : "";
  };
  const onClick = (n) => {
    ctx.set({ selectedParse: n.id });
    if (n.span) ctx.highlight(n.span, { strong: true });
  };
  if (mode === "graph") {
    container.append(el("div", { class: "svg-tree-wrap" }, svgTree(tree, {
      describe: (n) => ({
        text: n.kind === "terminal" ? n.lexeme : n.kind === "error" ? "⚠ error" : n.symbol,
        sub: n.kind === "error" ? (n.lexeme || "") : null,
        cls: n.kind,
        title: n.kind === "error" ? `recovered: ${n.lexeme || ""}` : n.symbol,
      }),
      state: stateOf, skip, onClick, selected,
    })));
  } else {
    container.append(outlineTree(tree, {
      skip: (n) => skip(n) || stateOf(n) === "ghost",
      selected, onClick, openDepth: 40,
      render: (n) => {
        if (n.kind === "terminal") return el("span", { class: "term" }, n.lexeme);
        if (n.kind === "epsilon") return el("span", { class: "eps" }, "ε");
        if (n.kind === "error") return el("span", { class: "err" }, `⚠ error ${n.lexeme ? "[" + n.lexeme + "]" : ""}`);
        return el("span", { class: "kind" }, n.symbol);
      },
    }));
  }
  if (selected) {
    const node = tree.nodes.find((n) => n.id === selected);
    const traceStep = node && node.step ? trace[node.step - 1] : null;
    if (traceStep) {
      container.append(el("div", { class: "card", style: { marginTop: "12px" } },
        el("h3", {}, `${node.symbol} (step ${node.step})`),
        el("div", { class: "mono" }, traceStep.production || traceStep.message),
        el("div", { class: "muted small" }, traceStep.message)));
    }
  }
}

export function describeStep(step) {
  if (!step) return "";
  return el("span", {}, el("strong", {}, `${step.function}() `), el("span", { class: `act ${step.action}` }, step.action), " ",
    step.production ? el("code", {}, step.production) : null, " ", el("span", { class: "muted" }, step.message));
}

/* ---------------------------------------------------------------------- AST */
export function astDescribe(n) {
  let cls = "stmt";
  if (n.kind === "Binary" || n.kind === "Unary") cls = "op";
  else if (["Var", "Literal", "String"].includes(n.kind)) cls = "leaf";
  else if (n.kind === "Call") cls = "op";
  let text = n.label;
  if (n.kind === "Program") text = "Program";
  return { text, sub: n.type && n.type !== "error" ? n.type : (STATEMENTS.has(n.kind) && n.kind !== text ? n.kind : null), cls, title: `${n.kind}${n.type ? " : " + n.type : ""}` };
}

export function renderAst(container, ctx) {
  const syntax = ctx.result?.phases.syntax;
  const ast = syntax?.ast;
  if (!ast) {
    container.append(empty("No abstract syntax tree", syntax && syntax.status === "error"
      ? "Fix the syntax errors to build the AST." : "Compile to build the AST."));
    return;
  }
  const [mode, toggle] = modeToggle(ctx, "astMode", ast.nodes.length);
  const selected = ctx.state.selectedAst;
  const typed = ctx.result.phases.semantic?.status === "ok";
  container.append(viewHead("Abstract syntax tree",
    typed ? "Operators and operands only — annotated with types by the semantic analyzer." : "Operators and operands only.", toggle));
  container.append(el("div", { class: "stats" }, stat(ast.nodes.length, "AST nodes"),
    stat(syntax.parse_tree?.count ?? "–", "parse tree nodes"), stat(syntax.stats.ast_depth, "depth")));
  if (syntax.ast_infix) {
    container.append(el("div", { class: "banner info" }, el("strong", {}, "Fully parenthesised"),
      el("code", { class: "mono", style: { fontSize: "16px" } }, syntax.ast_infix)));
  }
  const onClick = (n) => {
    ctx.set({ selectedAst: n.id });
    if (n.span) ctx.highlight(n.span, { strong: true });
  };
  if (mode === "graph") {
    container.append(el("div", { class: "svg-tree-wrap" }, svgTree(ast, { describe: astDescribe, onClick, selected })));
  } else {
    container.append(outlineTree(ast, {
      selected, onClick, openDepth: 12,
      render: (n) => el("span", {}, el("span", { class: "kind" }, n.kind), " ",
        n.kind !== n.label ? el("span", { class: "lbl" }, n.label) : null, " ",
        n.type ? el("span", { class: "ty" }, `: ${n.type}`) : null),
    }));
  }
  if (selected) {
    const node = ast.nodes.find((n) => n.id === selected);
    if (node) container.append(astDetails(node, ctx));
  }
}

function astDetails(node, ctx) {
  const tac = (ctx.result.phases.ir?.tac || []).filter((i) => i.ast_id === node.id);
  const attrs = Object.entries(node).filter(([k]) => !["id", "kind", "label", "span", "parent", "children", "type"].includes(k));
  return el("div", { class: "card", style: { marginTop: "12px" } },
    el("h3", {}, `${node.kind} ${node.label !== node.kind ? "· " + node.label : ""}`),
    el("div", { class: "small" },
      node.type ? el("div", {}, "Type: ", el("code", {}, node.type)) : null,
      node.span ? el("div", {}, `Source: line ${node.span[0]}, col ${node.span[1]} → line ${node.span[2]}, col ${node.span[3]}`) : null,
      ...attrs.map(([k, v]) => el("div", {}, `${k}: `, el("code", {}, String(v))))),
    tac.length ? el("div", { style: { marginTop: "8px" } }, el("div", { class: "muted small" }, "Three address code generated for this node:"),
      el("div", { class: "tac" }, ...tac.map((i) => el("div", { class: "ins" }, el("span", { class: "idx" }, i.index), el("span", { class: "code" }, i.text), el("span"))))) : null);
}
