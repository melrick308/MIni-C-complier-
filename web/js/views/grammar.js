import { el, empty, viewHead } from "../dom.js";

export function render(container, ctx) {
  const profile = ctx.mode === "expression" ? "expression" : "minic";
  const info = ctx.grammar(profile);
  if (!info) {
    container.append(empty("Loading grammar…"));
    return;
  }
  const trace = ctx.result?.phases.syntax?.trace;
  const activeStep = ctx.state.parseStep && trace ? trace[ctx.state.parseStep - 1] : null;
  const activeProd = activeStep?.production;
  container.append(viewHead(profile === "expression" ? "Expression grammar" : "MiniC grammar",
    "Every non-terminal is implemented by one parser function. FIRST/FOLLOW sets are computed from this grammar."));
  container.append(el("div", { class: `banner ${info.is_ll1 ? "ok" : "warn"}` },
    el("strong", {}, info.is_ll1 ? "The grammar is LL(1) — the parser never backtracks" : "Grammar has unresolved conflicts"),
    info.conflicts.length ? info.conflicts.map((c) => el("div", { class: "small" },
      `Conflict in table cell [${c.nonterminal}, ${c.terminal}] — resolved: ${c.resolution}`))
      : "No two productions of a non-terminal can start with the same token."));
  if (activeProd) {
    container.append(el("div", { class: "banner info" }, el("strong", {}, `Current parsing step ${activeStep.step}`), el("code", {}, activeProd)));
  }
  container.append(el("table", { class: "grid" },
    el("thead", {}, el("tr", {}, ...["Non-terminal", "Parser function", "Productions", "FIRST", "FOLLOW"].map((h) => el("th", {}, h)))),
    el("tbody", {}, ...info.nonterminals.map((row) => el("tr", {},
      el("td", { class: "mono kind", style: { fontWeight: 600 } }, row.nonterminal),
      el("td", { class: "mono muted" }, row.function),
      el("td", {}, ...row.productions.map((p) => el("div", { class: "grammar-prod" + (p === activeProd ? " active" : "") }, p))),
      el("td", { class: "mono small" }, `{ ${row.first.join(", ")} }`),
      el("td", { class: "mono small" }, `{ ${row.follow.join(", ")} }`))))));
  const table = info.table;
  container.append(el("details", { class: "card", style: { marginTop: "14px" } },
    el("summary", {}, `LL(1) parse table (${table.length} entries)`),
    el("table", { class: "grid" },
      el("thead", {}, el("tr", {}, el("th", {}, "M[A, a]"), el("th", {}, "Lookahead"), el("th", {}, "Production"))),
      el("tbody", {}, ...table.map((t) => el("tr", {}, el("td", { class: "mono" }, t.nonterminal),
        el("td", { class: "mono" }, t.terminal), el("td", { class: "mono" }, t.productions.join("  |  "))))))));
}
