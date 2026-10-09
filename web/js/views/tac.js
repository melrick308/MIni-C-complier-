import { el, empty, stat, viewHead } from "../dom.js";

export function insClass(ins) {
  if (ins.op === "label") return "label";
  if (ins.op === "func" || ins.op === "endfunc") return "func";
  if (["goto", "iffalse", "iftrue", "call", "return"].includes(ins.op)) return "jump";
  return "";
}

/** A clickable TAC listing. opts: current, selected, marks{index: removed|rewritten}, annotate(ins), onPick(ins) */
export function tacListing(instrs, ctx, opts = {}) {
  return el("div", { class: "tac" }, ...instrs.map((ins) => {
    const classes = ["ins", insClass(ins)];
    if (opts.current === ins.index) classes.push("current");
    if (opts.selected === ins.index) classes.push("selected");
    if (opts.marks && opts.marks[ins.index]) classes.push(opts.marks[ins.index]);
    const row = el("div", {
      class: classes.join(" "),
      title: ins.line ? `from source line ${ins.line}` : "",
      dataset: { index: ins.index },
      onmouseenter: () => ins.span && ctx.highlight(ins.span),
      onclick: () => opts.onPick && opts.onPick(ins),
    }, el("span", { class: "idx" }, ins.index), el("span", { class: "code" }, ins.text),
    el("span", { class: "ann" }, opts.annotate ? opts.annotate(ins) || "" : ""));
    return row;
  }));
}

export function quadTable(instrs, ctx) {
  return el("table", { class: "grid" },
    el("thead", {}, el("tr", {}, ...["#", "op", "arg1", "arg2", "result"].map((h) => el("th", {}, h)))),
    el("tbody", {}, ...instrs.map((ins) => el("tr", {
      class: "clickable", onmouseenter: () => ins.span && ctx.highlight(ins.span),
    }, el("td", { class: "mono muted" }, ins.index), el("td", { class: "mono" }, ins.quad.op),
    el("td", { class: "mono" }, ins.quad.arg1), el("td", { class: "mono" }, ins.quad.arg2),
    el("td", { class: "mono" }, ins.quad.result)))));
}

/** Values written by each instruction during execution (for annotations). */
export function writtenValues(ctx) {
  const map = new Map();
  for (const step of ctx.result?.phases.execution?.trace || []) {
    if (step.writes && step.writes.length && !map.has(step.pc)) map.set(step.pc, step.writes[step.writes.length - 1].value);
  }
  return map;
}

export function render(container, ctx) {
  const ir = ctx.result?.phases.ir;
  if (!ir || ir.status !== "ok") {
    container.append(empty("No intermediate code", "Three address code is generated after semantic analysis succeeds."));
    return;
  }
  const stats = ir.stats;
  const view = ctx.state.tacView || "tac";
  const toggle = el("span", { class: "filters", style: { margin: 0 } },
    ...[["tac", "Three address code"], ["quad", "Quadruples"]].map(([v, label]) =>
      el("button", { class: "filter" + (view === v ? " active" : ""), onclick: () => ctx.set({ tacView: v }) }, label)));
  container.append(viewHead("Intermediate code", "Each instruction has at most one operator; control flow becomes labels and jumps.", toggle));
  container.append(el("div", { class: "stats" }, stat(stats.instructions, "instructions"), stat(stats.temporaries, "temporaries"),
    stat(stats.labels, "labels"), stat(stats.jumps, "jumps"), stat(stats.calls, "calls")));
  const values = writtenValues(ctx);
  const annotate = (ins) => (values.has(ins.index) && ins.result ? `→ ${values.get(ins.index)}` : "");
  if (view === "quad") {
    container.append(quadTable(ir.tac, ctx));
  } else {
    container.append(tacListing(ir.tac, ctx, {
      selected: ctx.state.selectedTac, annotate: ctx.mode === "expression" ? annotate : null,
      onPick: (ins) => { ctx.set({ selectedTac: ins.index }); if (ins.span) ctx.highlight(ins.span, { strong: true }); },
    }));
  }
  container.append(el("p", { class: "muted small" },
    "Hover an instruction to see the source it came from. ",
    ctx.mode === "expression" ? "Values on the right come from evaluating the code." : "Labels (L1:) mark jump targets; temporaries (t1) hold intermediate results."));
}
