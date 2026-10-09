// Execution view: a time-travel debugger over the recorded VM trace.
import { stepper } from "../components.js";
import { el, empty, stat, viewHead } from "../dom.js";
import { tacListing } from "./tac.js";

export function replay(trace, upto) {
  const globals = new Map();
  const frames = [{ func: "main", id: 0, vars: new Map() }];
  const output = [];
  const hits = {};
  for (let i = 0; i < upto; i++) {
    const s = trace[i];
    if (s.event === "call") frames.push({ func: s.call.func, id: s.call.frame, vars: new Map() });
    if (s.event === "return" && frames.length > 1) frames.pop();
    for (const w of s.writes || []) {
      if (w.scope === "global") globals.set(w.name, w.value);
      else frames[frames.length - 1].vars.set(w.name, w.value);
    }
    if (s.output !== undefined) output.push(s.output);
    if (s.line) hits[s.line] = (hits[s.line] || 0) + 1;
  }
  return { globals, frames, output, hits };
}

function varsGrid(vars, names, changed, showTemps) {
  const entries = [...vars.entries()].filter(([n]) => showTemps || !/^t\d+$/.test(n));
  if (!entries.length) return el("div", { class: "vars" }, el("span", { class: "muted" }, "(empty)"));
  return el("div", { class: "vars" }, ...entries.flatMap(([n, v]) => {
    const isTemp = /^t\d+$/.test(n);
    const shown = names[n] && names[n] !== n ? `${names[n]} (${n})` : n;
    return [el("span", { class: "n" + (isTemp ? " temp" : "") }, shown),
      el("span", { class: "v" + (changed.has(n) ? " changed" : "") }, v)];
  }));
}

export function render(container, ctx) {
  const ex = ctx.result?.phases.execution;
  if (!ex || ex.status === "skipped") {
    container.append(empty("Nothing ran", ex?.reason || "Compile a valid program to run it on the virtual machine."));
    return;
  }
  const trace = ex.trace;
  const names = ctx.result.symbol_names || {};
  const step = Math.min(ctx.state.execStep ?? trace.length, trace.length);
  const err = ctx.result.diagnostics.find((d) => d.phase === "runtime");
  container.append(viewHead("Execution", "The generated three address code runs on a small virtual machine. Step through it."));
  if (ex.status === "ok") {
    container.append(el("div", { class: "banner ok" }, el("strong", {}, "Program finished normally"),
      `${ex.steps.toLocaleString()} instructions executed${ex.optimized ? " (optimized code)" : ""}.`));
  } else if (err) {
    container.append(el("div", { class: `banner ${ex.kind === "limit" ? "warn" : "error"}` },
      el("strong", {}, `${ex.kind === "limit" ? "Stopped" : "Runtime error"} at line ${err.line}: ${err.message}`),
      err.hint || ""));
  }
  container.append(el("div", { class: "stats" }, stat(ex.steps.toLocaleString(), "instructions run"),
    stat(ex.output.length, "output lines"), stat(ex.max_depth, "max call depth"), stat(`${ex.ms} ms`, "run time")));
  if (ex.trace_truncated) {
    container.append(el("div", { class: "banner warn" }, el("strong", {}, "Trace truncated"),
      `Only the first ${trace.length.toLocaleString()} steps were recorded for stepping.`));
  }
  if (!trace.length) return;
  const current = trace[step - 1];
  container.append(stepper({
    key: "exec", count: trace.length, value: step,
    onChange: (v) => ctx.setExecStep(v),
    describe: () => el("span", {}, el("strong", {}, current.func === "main" ? "main" : `${current.func}()`),
      ` · line ${current.line ?? "–"} · `, el("code", {}, current.text),
      current.event === "call" ? el("span", { class: "chip" }, `call → ${current.call.func}`) : null,
      current.event === "return" ? el("span", { class: "chip" }, `return ${current.return.value ?? ""}`) : null,
      current.output !== undefined ? el("span", { class: "chip" }, `prints "${current.output}"`) : null,
      current.error ? el("span", { class: "chip", style: { color: "var(--err)" } }, current.error) : null),
  }));

  const state = replay(trace, step);
  ctx.editor?.setHits(state.hits);
  ctx.editor?.setExecLine(current.line, Boolean(current.error));
  const changed = new Set((current.writes || []).map((w) => w.name));
  const showTemps = ctx.state.showTemps;
  const instrs = ex.optimized ? ctx.result.phases.optimize.tac : ctx.result.phases.ir.tac;
  const listing = tacListing(instrs, ctx, { current: current.pc, onPick: (ins) => {
    const target = trace.findIndex((s, i) => i >= step && s.pc === ins.index);
    const first = target >= 0 ? target : trace.findIndex((s) => s.pc === ins.index);
    if (first >= 0) ctx.setExecStep(first + 1);
  } });
  const frames = el("div", { class: "frames" },
    el("label", { class: "toggle small" }, el("input", { type: "checkbox", checked: showTemps,
      onchange: (e) => ctx.set({ showTemps: e.target.checked }) }), "Show temporaries"),
    el("div", { class: "frame" }, el("div", { class: "frame-head" }, "Global variables"),
      varsGrid(state.globals, names, changed, true)),
    el("h3", { class: "small muted", style: { margin: "4px 0 0" } }, `CALL STACK (${state.frames.length})`),
    ...state.frames.slice().reverse().map((f, i) => el("div", { class: "frame" + (i === 0 ? " top" : "") },
      el("div", { class: "frame-head" }, f.func === "main" ? "main (top level)" : `${f.func}()`, el("span", { class: "muted small" }, `frame #${f.id}`)),
      varsGrid(f.vars, names, i === 0 ? changed : new Set(), showTemps))),
    el("h3", { class: "small muted", style: { margin: "4px 0 0" } }, "OUTPUT SO FAR"),
    el("div", { class: "out-box" }, state.output.join("\n") || el("span", { class: "muted" }, "(nothing printed yet)")));
  container.append(el("div", { class: "debugger" }, el("div", {}, el("h3", { class: "small muted", style: { margin: "0 0 6px" } }, "THREE ADDRESS CODE (click to jump)"), listing), frames));
  requestAnimationFrame(() => listing.querySelector(".ins.current")?.scrollIntoView({ block: "nearest" }));
}
