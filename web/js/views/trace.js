import { stepper } from "../components.js";
import { el, empty, stat, viewHead } from "../dom.js";
import { describeStep } from "./trees.js";

const PAGE = 200;
const ACTIONS = ["enter", "match", "epsilon", "error", "recover"];

export function render(container, ctx) {
  const syntax = ctx.result?.phases.syntax;
  if (!syntax || !syntax.trace) {
    container.append(empty("No parsing steps", "Compile to see how the recursive descent parser works."));
    return;
  }
  const trace = syntax.trace;
  const step = ctx.state.parseStep ?? trace.length;
  const filter = ctx.state.traceFilter;
  const counts = Object.fromEntries(ACTIONS.map((a) => [a, trace.filter((s) => s.action === a).length]));
  container.append(
    viewHead("Parsing steps", "Each row is one decision of a parser function, driven by the lookahead token."),
    el("div", { class: "stats" }, stat(trace.length, "steps"), stat(counts.enter, "expansions"),
      stat(counts.match, "matches"), stat(counts.epsilon, "ε-productions"),
      counts.error ? stat(counts.error, "errors") : null, counts.recover ? stat(counts.recover, "recoveries") : null),
  );
  if (syntax.trace_truncated) {
    container.append(el("div", { class: "banner warn" }, el("strong", {}, "Trace truncated"),
      "Only the first steps are recorded for very large programs."));
  }
  container.append(stepper({
    key: "parse", count: trace.length, value: step,
    onChange: (v) => ctx.setParseStep(v),
    describe: (v) => describeStep(trace[v - 1]),
  }));
  container.append(el("div", { class: "filters" },
    ...["all", ...ACTIONS].map((a) => el("button", {
      class: "filter" + ((filter || "all") === a ? " active" : ""),
      onclick: () => ctx.set({ traceFilter: a === "all" ? null : a, tracePage: null }),
    }, a === "all" ? "all" : `${a} (${counts[a]})`))));

  const rows = filter ? trace.filter((s) => s.action === filter) : trace;
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  let page = ctx.state.tracePage;
  if (page === null || page === undefined) {
    const index = filter ? 0 : Math.max(0, step - 1);
    page = Math.floor(index / PAGE);
  }
  page = Math.min(page, pages - 1);
  const slice = rows.slice(page * PAGE, page * PAGE + PAGE);
  const table = el("table", { class: "grid trace" },
    el("thead", {}, el("tr", {}, el("th", {}, "Step"), el("th", {}, "Function"), el("th", {}, "Lookahead"),
      el("th", {}, "Action"), el("th", {}, "Production / reason"))),
    el("tbody", {}, ...slice.map((s) => el("tr", {
      class: "clickable" + (s.step === step && ctx.state.parseStep ? " current" : ""),
      onclick: () => ctx.setParseStep(s.step),
    },
    el("td", { class: "mono muted" }, s.step),
    el("td", { class: "fn" }, ...Array.from({ length: Math.min(s.depth, 30) }, () => el("span", { class: "indent" })), `${s.function}()`),
    el("td", { class: "mono" }, s.lexeme),
    el("td", {}, el("span", { class: `act ${s.action}` }, s.action)),
    el("td", {}, s.production ? el("code", { class: "mono" }, s.production) : null,
      s.production && s.action !== "enter" ? " " : null,
      s.action !== "enter" || !s.production ? el("span", { class: "muted" }, s.message) : null)))));
  container.append(table);
  if (pages > 1) {
    container.append(el("div", { class: "pager" },
      el("button", { class: "btn small", disabled: page === 0, onclick: () => ctx.set({ tracePage: page - 1 }) }, "‹ Prev"),
      `Page ${page + 1} of ${pages}`,
      el("button", { class: "btn small", disabled: page >= pages - 1, onclick: () => ctx.set({ tracePage: page + 1 }) }, "Next ›")));
  }
}
