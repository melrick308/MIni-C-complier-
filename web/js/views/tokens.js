import { el, empty, stat, viewHead } from "../dom.js";

const CATEGORIES = ["keyword", "identifier", "number", "string", "operator", "delimiter"];

export function tokenChip(token, extra = "") {
  return el("span", { class: `token tok-${token.category} ${extra}`, title: `${token.token} @ ${token.line}:${token.col}` },
    token.category === "eof" ? "$" : token.lexeme, el("small", {}, token.category === "eof" ? "EOF" : token.token.replace("KW_", "")));
}

export function render(container, ctx) {
  const phase = ctx.result?.phases.lexical;
  if (!phase || phase.status === "skipped") {
    container.append(empty("No tokens yet", "Compile to run the lexical analyzer."));
    return;
  }
  const tokens = phase.tokens;
  const stats = phase.stats;
  const filter = ctx.state.tokenFilter;
  container.append(
    viewHead("Lexical analysis", "The scanner groups characters into tokens and drops whitespace and comments."),
    el("div", { class: "stats" },
      stat(stats.tokens, "tokens"),
      ...CATEGORIES.filter((c) => stats.by_category[c]).map((c) => stat(stats.by_category[c], c + "s")),
      stat(stats.lines, "lines")),
  );
  if (phase.status === "error") {
    const diag = ctx.result.diagnostics.find((d) => d.phase === "lexical");
    container.append(el("div", { class: "banner error" }, el("strong", {}, "Lexical error"),
      `${diag.message} at line ${diag.line}, column ${diag.col}. Tokens up to the error are shown below.`));
  }
  container.append(el("div", { class: "card" }, el("h3", {}, "Token stream"),
    el("div", { class: "token-strip" }, ...tokens.slice(0, 400).map((t) => {
      const chip = tokenChip(t);
      chip.addEventListener("mouseenter", () => ctx.highlight(t.span));
      return chip;
    }), tokens.length > 400 ? el("span", { class: "muted" }, `… ${tokens.length - 400} more`) : null)));

  const filters = el("div", { class: "filters" },
    ...["all", ...CATEGORIES].map((c) => el("button", {
      class: "filter" + ((filter || "all") === c ? " active" : ""),
      onclick: () => ctx.set({ tokenFilter: c === "all" ? null : c }),
    }, c)));
  const rows = tokens.filter((t) => !filter || t.category === filter);
  container.append(filters, el("table", { class: "grid" },
    el("thead", {}, el("tr", {}, el("th", {}, "#"), el("th", {}, "Lexeme"), el("th", {}, "Token"),
      el("th", {}, "Category"), el("th", {}, "Line:Col"))),
    el("tbody", {}, ...rows.map((t) => el("tr", {
      class: "clickable",
      onmouseenter: () => ctx.highlight(t.span),
      onclick: () => ctx.highlight(t.span, { strong: true }),
    }, el("td", { class: "mono muted" }, t.index), el("td", { class: `mono tok-${t.category}` }, t.lexeme),
    el("td", { class: "mono" }, t.token), el("td", {}, t.category), el("td", { class: "mono" }, `${t.line}:${t.col}`))))));
}
