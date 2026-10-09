// Bottom panels: program output and the problems list.
import { el } from "./dom.js";

export function renderOutput(container, result, mode) {
  container.replaceChildren();
  if (!result) {
    container.append(el("div", { class: "meta" }, "Press Compile & Run (Ctrl+Enter)."));
    return;
  }
  const ex = result.phases.execution;
  if (mode === "expression") {
    const ev = result.evaluation;
    if (ev?.status === "ok") container.append(el("div", { class: "line" }, `Result = ${ev.value}`));
    else if (ev) container.append(el("div", { class: "meta" }, ev.message));
    else container.append(el("div", { class: "meta" }, "Invalid expression — see Problems."));
    return;
  }
  if (!ex || ex.status === "skipped") {
    container.append(el("div", { class: "meta" }, ex?.reason || "Not run."));
    return;
  }
  container.append(el("div", { class: "meta" },
    `Ran ${ex.steps.toLocaleString()} instructions in ${ex.ms} ms${ex.optimized ? " (optimized)" : ""}`));
  for (const line of ex.output) container.append(el("div", { class: "line" }, line));
  if (!ex.output.length) container.append(el("div", { class: "meta" }, "(no output)"));
  const err = result.diagnostics.find((d) => d.phase === "runtime");
  if (err) container.append(el("div", { class: "line rt-error" }, `✗ ${err.message} (line ${err.line})`));
}

export function renderProblems(container, result, onPick) {
  container.replaceChildren();
  const diags = result?.diagnostics || [];
  if (!diags.length) {
    container.append(el("div", { class: "meta muted" }, result ? "No problems detected." : ""));
    return;
  }
  for (const d of diags) {
    container.append(el("div", { class: `problem ${d.severity}`, onclick: () => onPick(d) },
      el("span", { class: "ico" }),
      el("div", {},
        el("div", { class: "msg" }, d.message),
        el("div", { class: "meta" }, `${d.phase} · ${d.code}`),
        d.expected ? el("div", { class: "exp" }, `expected: ${d.expected.join(", ")}`) : null,
        d.hint ? el("div", { class: "hint" }, d.hint) : null),
      el("span", { class: "where" }, d.line ? `${d.line}:${d.col}` : "")));
  }
}
