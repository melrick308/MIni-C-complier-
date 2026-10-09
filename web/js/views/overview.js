// Expression mode: the original "Interactive Arithmetic Expression Analyzer" screen.
import { el, empty, viewHead } from "../dom.js";
import { tacListing, writtenValues } from "./tac.js";
import { tokenChip } from "./tokens.js";

export function caretBox(source, diag) {
  const [line, col, endLine, endCol] = diag.span;
  const text = source.split("\n")[line - 1] ?? "";
  const width = Math.max(1, endLine === line ? endCol - col : 1);
  return el("div", { class: "caret-box" }, text, "\n", " ".repeat(Math.max(0, col - 1)),
    el("span", { class: "c" }, "^" + "~".repeat(width - 1)));
}

export function errorCard(source, diag) {
  const kind = { lexical: "Lexical Error", syntax: "Syntax Error", runtime: "Runtime Error" }[diag.phase] || "Error";
  return el("div", { class: "banner error" },
    el("strong", {}, `✗ ${kind}: ${diag.message}`),
    el("div", { class: "small" }, `Position: column ${diag.col}${diag.line > 1 ? `, line ${diag.line}` : ""}`),
    diag.span ? caretBox(source, diag) : null,
    diag.found ? el("div", { class: "small" }, "Found: ", el("code", {}, diag.found)) : null,
    diag.expected ? el("div", { class: "small" }, "Expected: ",
      ...diag.expected.map((e) => el("span", { class: "chip", style: { marginRight: "4px" } }, e))) : null,
    diag.related ? el("div", { class: "small muted" }, `${diag.related.message} (column ${diag.related.span[1]})`) : null,
    diag.hint ? el("div", { class: "small", style: { marginTop: "4px" } }, "💡 ", diag.hint) : null);
}

export function render(container, ctx) {
  const result = ctx.result;
  if (!result) {
    container.append(empty("Type an expression", "It is analyzed as you type."));
    return;
  }
  const source = ctx.source();
  container.append(viewHead("Expression analysis", "Lexer → recursive descent parser → AST → evaluation and three address code."));
  const tokens = result.phases.lexical?.tokens || [];
  const firstError = result.diagnostics.find((d) => d.severity === "error" && d.phase !== "runtime");
  if (firstError) {
    container.append(errorCard(source, firstError));
  } else if (result.failed_phase === "input") {
    container.append(el("div", { class: "banner error" }, el("strong", {}, result.diagnostics[0].message)));
  } else {
    container.append(el("div", { class: "banner ok" }, el("strong", {}, "✓ Valid Expression"),
      "Fully parenthesised: ", el("code", { class: "mono" }, result.phases.syntax.ast_infix)));
  }
  if (tokens.length) {
    const errorIndex = firstError?.phase === "lexical" ? tokens.length - 1 : -1;
    container.append(el("div", { class: "card" }, el("h3", {}, "Tokens"),
      el("div", { class: "token-strip" }, ...tokens.map((t, i) => {
        const chip = tokenChip(t, i === errorIndex ? "error" : "");
        chip.addEventListener("mouseenter", () => ctx.highlight(t.span));
        return chip;
      }))));
  }
  if (firstError || result.failed_phase) return;

  const ev = result.evaluation;
  const evalCard = el("div", { class: "card" }, el("h3", {}, "Evaluation"));
  if (ev.status === "ok") {
    evalCard.append(el("div", { class: "result-big" }, `Result = ${ev.value}`));
  } else if (ev.status === "skipped") {
    evalCard.append(el("div", {}, ev.message),
      el("button", { class: "btn small", style: { marginTop: "8px" }, onclick: () => ctx.addVariables(ev.missing) },
        `Add ${ev.missing.join(", ")} to the Variables panel`));
  } else {
    const rt = result.diagnostics.find((d) => d.phase === "runtime");
    evalCard.append(el("div", { class: "banner error" }, el("strong", {}, `Runtime error: ${ev.message}`),
      "The expression is syntactically valid, but evaluating it fails.", rt?.span ? caretBox(source, rt) : null));
  }
  container.append(evalCard);
  const values = writtenValues(ctx);
  container.append(el("div", { class: "card" }, el("h3", {}, "Three address code"),
    tacListing(result.phases.ir.tac, ctx, {
      annotate: (ins) => (values.has(ins.index) ? `→ ${values.get(ins.index)}` : ""),
    })));
}
