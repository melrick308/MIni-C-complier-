import { el } from "./dom.js";

export const PHASES = [
  { id: "lexical", label: "Lexer", tab: "tokens" },
  { id: "syntax", label: "Parser", tab: "ast" },
  { id: "semantic", label: "Semantic", tab: "symbols" },
  { id: "ir", label: "TAC", tab: "tac" },
  { id: "cfg", label: "CFG", tab: "cfg", programOnly: true },
  { id: "optimize", label: "Optimize", tab: "optimized", programOnly: true },
  { id: "execution", label: "Run", tab: "run", expressionLabel: "Evaluate", expressionTab: "overview" },
];

export function renderPipeline(container, { result, mode, dirty, onPick, activeTab }) {
  container.replaceChildren();
  const phases = PHASES.filter((p) => mode === "program" || !p.programOnly);
  phases.forEach((p, i) => {
    const data = result?.phases[p.id];
    let status = data ? data.status : "idle";
    if (status === "ok" && p.id === "semantic" && result.diagnostics.some((d) => d.severity === "warning")) status = "warn";
    const tab = mode === "expression" && p.expressionTab ? p.expressionTab : p.tab;
    const label = mode === "expression" && p.expressionLabel ? p.expressionLabel : p.label;
    const title = data?.reason || (data?.status === "error" ? "This phase reported errors" : data ? "Completed" : "Not run yet");
    container.append(el("button", {
      class: `phase ${status}${activeTab === tab ? " current" : ""}`,
      title, onclick: () => onPick(tab, p.id),
    }, el("span", { class: "dot" }), label, data?.ms !== undefined ? el("span", { class: "ms" }, `${data.ms} ms`) : null));
    if (i < phases.length - 1) container.append(el("span", { class: "arrow" }, "›"));
  });
  let summary = "";
  if (dirty) summary = "● edited — press Compile & Run";
  else if (result) {
    if (result.success) {
      const total = Object.values(result.timings || {}).reduce((a, b) => a + (b || 0), 0);
      summary = `✓ all phases passed · ${total.toFixed(1)} ms`;
    } else if (result.failed_phase) summary = `✗ stopped at the ${result.failed_phase} phase`;
    else summary = "✗ runtime error";
  }
  container.append(el("span", { class: "summary" }, summary));
}
