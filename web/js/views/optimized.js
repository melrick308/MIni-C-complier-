import { el, empty, stat, viewHead } from "../dom.js";
import { tacListing } from "./tac.js";

const EXPLAIN = {
  "constant folding": "operations on constants computed at compile time (2 * 3 → 6)",
  "constant propagation": "a variable known to hold a constant is replaced by that constant",
  "algebraic simplification": "identities such as x * 1 → x and x + 0 → x",
  "constant branch": "conditional jumps whose condition is known become goto or disappear",
  "dead code elimination": "temporaries that are computed but never used are removed",
  "unreachable code": "instructions that can never execute are removed",
  "redundant jump": "a goto to the very next label is removed",
  "unused label": "labels that no jump targets are removed",
};

export function render(container, ctx) {
  if (ctx.mode === "expression") {
    container.append(empty("Optimizer", "Available in Program mode."));
    return;
  }
  const opt = ctx.result?.phases.optimize;
  const ir = ctx.result?.phases.ir;
  if (!opt || opt.status !== "ok") {
    container.append(viewHead("Code optimization", "Machine-independent optimizations on the three address code."),
      empty("The optimizer is off", ir?.status === "ok" ? "Turn it on to see constant folding, propagation and dead code elimination." : "Compile a valid program first."));
    if (ir?.status === "ok") {
      container.append(el("div", { style: { textAlign: "center" } },
        el("button", { class: "btn primary", onclick: () => ctx.enableOptimize() }, "Turn on Optimize and recompile")));
    }
    return;
  }
  const s = opt.stats;
  container.append(viewHead("Code optimization", "The optimized code is what the virtual machine runs while Optimize is on."));
  container.append(el("div", { class: "stats" }, stat(s.before, "instructions before"), stat(s.after, "after"),
    stat(s.removed, "removed"), stat(`${s.percent}%`, "smaller")));
  const changes = Object.entries(opt.changes);
  container.append(el("div", { class: "card" }, el("h3", {}, "What changed"),
    changes.length ? el("ul", { class: "small", style: { margin: 0, paddingLeft: "18px" } },
      ...changes.map(([name, n]) => el("li", {}, el("strong", {}, `${name} ×${n}`), " — ", EXPLAIN[name] || ""))) :
      el("div", { class: "muted small" }, "Nothing to optimize in this program.")));
  container.append(el("div", { class: "two-col" },
    el("div", {}, el("h3", { class: "small muted" }, "ORIGINAL (struck through = removed, green = rewritten)"),
      tacListing(ir.tac, ctx, { marks: opt.marks })),
    el("div", {}, el("h3", { class: "small muted" }, "OPTIMIZED"), tacListing(opt.tac, ctx, {}))));
}
