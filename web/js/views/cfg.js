/* global mermaid */
import { el, empty, stat, viewHead } from "../dom.js";

const cache = new Map();
let renderCount = 0;

function theme() {
  return document.documentElement.dataset.theme === "light" ? "default" : "dark";
}

let initializedTheme = null;
function ensureMermaid() {
  if (typeof mermaid === "undefined") return false;
  const t = theme();
  if (initializedTheme !== t) {
    mermaid.initialize({ startOnLoad: false, theme: t, securityLevel: "strict",
      flowchart: { htmlLabels: true, useMaxWidth: false, curve: "basis" },
      themeVariables: { fontFamily: "Consolas, Cascadia Mono, monospace", fontSize: "13px" } });
    initializedTheme = t;
  }
  return true;
}

export function render(container, ctx) {
  const cfg = ctx.result?.phases.cfg;
  if (!cfg || cfg.status !== "ok") {
    container.append(empty("No control flow graph", ctx.mode === "expression"
      ? "A single expression has no branches or loops — switch to Program mode." : "The CFG is built from the three address code."));
    return;
  }
  const functions = cfg.functions;
  const name = functions.some((f) => f.name === ctx.state.cfgFunc) ? ctx.state.cfgFunc : functions[0].name;
  const fn = functions.find((f) => f.name === name);
  const select = el("select", { onchange: (e) => ctx.set({ cfgFunc: e.target.value, cfgBlock: null }) },
    ...functions.map((f) => el("option", { value: f.name, selected: f.name === name }, f.name === "main" ? "main (top-level code)" : `function ${f.name}`)));
  container.append(viewHead("Control flow graph", "Basic blocks (straight-line code) connected by jumps. Dashed red edges are loop back-edges.", select));
  container.append(el("div", { class: "stats" }, stat(fn.blocks.length, "basic blocks"), stat(fn.edges.length, "edges"),
    stat(fn.loops, fn.loops === 1 ? "loop" : "loops"), stat(cfg.stats.blocks, "blocks in program")));
  const host = el("div", { class: "cfg-host" }, el("span", { class: "muted" }, "Drawing graph…"));
  container.append(host);
  const blockInfo = el("div");
  container.append(blockInfo);

  const selectBlock = (id) => {
    const block = fn.blocks.find((b) => b.id === id);
    if (!block) return;
    ctx.state.cfgBlock = id;
    host.querySelectorAll(".node").forEach((n) => n.classList.toggle("selected", n.dataset.block === id));
    ctx.highlightLines(block.lines);
    blockInfo.replaceChildren(el("div", { class: "card", style: { marginTop: "12px" } },
      el("h3", {}, `${block.id} — instructions ${block.start}…${block.end}`),
      el("div", { class: "small muted" }, `Successors: ${block.succ.join(", ") || "none"} · Predecessors: ${block.pred.join(", ") || "none"} · Source lines: ${block.lines.join(", ") || "–"}`),
      el("pre", { class: "mono", style: { margin: "8px 0 0" } }, block.text.join("\n"))));
  };

  if (!ensureMermaid()) {
    host.replaceChildren(el("pre", { class: "mono small" }, fn.mermaid));
    return;
  }
  const key = `${theme()}::${fn.mermaid}`;
  const finish = (svgText) => {
    host.innerHTML = svgText; // produced by Mermaid from escaped TAC text (securityLevel: strict)
    host.querySelectorAll("g.node").forEach((node) => {
      const match = /flowchart-([A-Za-z0-9]+)-/.exec(node.id);
      if (!match) return;
      node.dataset.block = match[1];
      node.addEventListener("click", () => selectBlock(match[1]));
    });
    if (ctx.state.cfgBlock) selectBlock(ctx.state.cfgBlock);
  };
  if (cache.has(key)) {
    finish(cache.get(key));
    return;
  }
  renderCount += 1;
  mermaid.render(`cfg-graph-${renderCount}`, fn.mermaid)
    .then(({ svg }) => { cache.set(key, svg); if (host.isConnected) finish(svg); })
    .catch((error) => host.replaceChildren(el("div", { class: "banner error" }, "Could not draw graph: " + error.message),
      el("pre", { class: "mono small" }, fn.mermaid)));
}
