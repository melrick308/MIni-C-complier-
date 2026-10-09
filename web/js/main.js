import { api } from "./api.js";
import { renderOutput, renderProblems } from "./bottom.js";
import { stopPlayer } from "./components.js";
import { el, storage, toast } from "./dom.js";
import { Editor } from "./editor.js";
import { renderPipeline } from "./pipeline.js";
import * as cfgView from "./views/cfg.js";
import * as grammarView from "./views/grammar.js";
import * as learnView from "./views/learn.js";
import * as optimizedView from "./views/optimized.js";
import * as overviewView from "./views/overview.js";
import * as runView from "./views/run.js";
import * as symbolsView from "./views/symbols.js";
import * as tacView from "./views/tac.js";
import * as tokensView from "./views/tokens.js";
import * as traceView from "./views/trace.js";
import { renderAst, renderParseTree } from "./views/trees.js";

const TABS = {
  program: [
    { id: "tokens", label: "Tokens", render: tokensView.render },
    { id: "parsetree", label: "Parse Tree", render: renderParseTree },
    { id: "ast", label: "AST", render: renderAst },
    { id: "steps", label: "Parse Steps", render: traceView.render },
    { id: "symbols", label: "Symbols", render: symbolsView.render },
    { id: "tac", label: "TAC", render: tacView.render },
    { id: "cfg", label: "CFG", render: cfgView.render },
    { id: "optimized", label: "Optimized", render: optimizedView.render },
    { id: "run", label: "Run ▸ Debug", render: runView.render },
    { id: "grammar", label: "Grammar", render: grammarView.render },
    { id: "learn", label: "Learn", render: learnView.render },
  ],
  expression: [
    { id: "overview", label: "Overview", render: overviewView.render },
    { id: "parsetree", label: "Parse Tree", render: renderParseTree },
    { id: "ast", label: "AST", render: renderAst },
    { id: "steps", label: "Parse Steps", render: traceView.render },
    { id: "tokens", label: "Tokens", render: tokensView.render },
    { id: "symbols", label: "Symbols", render: symbolsView.render },
    { id: "tac", label: "TAC", render: tacView.render },
    { id: "grammar", label: "Grammar", render: grammarView.render },
    { id: "learn", label: "Learn", render: learnView.render },
  ],
};
const PHASE_TAB = { lexical: "tokens", syntax: "ast", semantic: "symbols", ir: "tac", cfg: "cfg", optimize: "optimized", execution: "run" };

const $ = (id) => document.getElementById(id);
const state = {
  mode: storage.get("mode", "program"),
  tab: storage.get("tabs", { program: "ast", expression: "overview" }),
  results: { program: null, expression: null },
  dirty: false,
  busy: false,
  variables: storage.get("variables", [{ name: "a", value: "3" }, { name: "b", value: "4" }, { name: "c", value: "7" }]),
  hideEpsilon: true,
  showTemps: false,
  examples: null,
  grammars: {},
};
let view = {};  // per-result view state (steps, selections, filters)
let editor = null;
let exprTimer = null;

/* ------------------------------------------------------------------ context */
const ctx = {
  get result() { return state.results[state.mode]; },
  get mode() { return state.mode; },
  get state() { return Object.assign(view, { hideEpsilon: state.hideEpsilon, showTemps: state.showTemps }); },
  get editor() { return state.mode === "program" ? editor : null; },
  source() { return state.mode === "program" ? editor.value : $("expr").value; },
  set(patch) {
    if ("hideEpsilon" in patch) state.hideEpsilon = patch.hideEpsilon;
    if ("showTemps" in patch) state.showTemps = patch.showTemps;
    Object.assign(view, patch);
    renderView();
  },
  setParseStep(step) {
    view.parseStep = step;
    view.tracePage = null;
    const trace = ctx.result?.phases.syntax.trace || [];
    const tokens = ctx.result?.phases.lexical.tokens || [];
    const entry = trace[step - 1];
    if (entry && tokens[entry.la]) ctx.highlight(tokens[entry.la].span, { strong: true });
    renderView();
  },
  setExecStep(step) {
    view.execStep = step;
    renderView();
  },
  highlight(span, opts = {}) {
    if (state.mode === "program") editor.highlight(span, opts);
    else renderExprMirror(span);
  },
  highlightLines(lines) {
    if (state.mode === "program") editor.highlightLines(lines);
  },
  grammar(profile) {
    if (state.grammars[profile]) return state.grammars[profile];
    if (!state.grammars[`${profile}:loading`]) {
      state.grammars[`${profile}:loading`] = true;
      api.grammar(profile).then((g) => { state.grammars[profile] = g; renderView(); })
        .catch((e) => toast(e.message));
    }
    return null;
  },
  enableOptimize() {
    $("optimize").checked = true;
    storage.set("optimize", true);
    compile();
  },
  addVariables(names) {
    for (const name of names) if (!state.variables.some((v) => v.name === name)) state.variables.push({ name, value: "" });
    renderVariables();
    $("variables").querySelector("input[data-field=value]:placeholder-shown")?.focus();
  },
};

/* ------------------------------------------------------------------ render */
function renderTabs() {
  const bar = $("view-tabs");
  bar.replaceChildren();
  const diags = ctx.result?.diagnostics || [];
  for (const tab of TABS[state.mode]) {
    const button = el("button", { class: "tab" + (tab.id === currentTab() ? " active" : ""), role: "tab",
      onclick: () => selectTab(tab.id) }, tab.label);
    if (tab.id === "symbols" && state.mode === "program") {
      const n = diags.filter((d) => d.phase === "semantic" && d.severity === "error").length;
      if (n) button.append(el("span", { class: "badge err" }, n));
    }
    if (tab.id === "run" && ctx.result?.phases.execution?.status === "error") button.append(el("span", { class: "badge err" }, "!"));
    bar.append(button);
  }
}

function currentTab() {
  const tab = state.tab[state.mode];
  return TABS[state.mode].some((t) => t.id === tab) ? tab : TABS[state.mode][0].id;
}

function selectTab(id) {
  stopPlayer();
  state.tab[state.mode] = id;
  storage.set("tabs", state.tab);
  if (editor && id !== "run") { editor.setExecLine(null); editor.setHits(null); }
  if (editor) editor.clearHighlight();
  $("view").scrollTop = 0;
  renderView();
}

function renderView() {
  const container = $("view");
  const top = container.scrollTop;
  container.replaceChildren();
  const tab = TABS[state.mode].find((t) => t.id === currentTab());
  try {
    tab.render(container, ctx);
  } catch (error) {
    console.error(error);
    container.append(el("div", { class: "banner error" }, el("strong", {}, "This view failed to render"), String(error)));
  }
  container.scrollTop = top;
  renderTabs();
  renderPipeline($("pipeline"), {
    result: ctx.result, mode: state.mode, dirty: state.dirty && state.mode === "program", activeTab: currentTab(),
    onPick: (tabId, phase) => { view.learnFocus = phase; selectTab(tabId); },
  });
}

function renderBottom() {
  renderOutput($("bottom-output"), ctx.result, state.mode);
  renderProblems($("bottom-problems"), ctx.result, (d) => {
    if (state.mode === "program" && d.line) {
      editor.goto(d.line, d.col);
      if (d.span) editor.highlight(d.span, { strong: true });
    }
    const tab = PHASE_TAB[d.phase === "runtime" ? "execution" : d.phase];
    if (tab && TABS[state.mode].some((t) => t.id === tab)) selectTab(tab);
  });
  const errors = (ctx.result?.diagnostics || []).filter((d) => d.severity === "error").length;
  const warnings = (ctx.result?.diagnostics || []).length - errors;
  const badge = $("problem-count");
  badge.textContent = errors || warnings ? String(errors + warnings) : "";
  badge.className = "badge" + (errors ? " err" : "");
}

function showBottom(which) {
  document.querySelectorAll("[data-bottom]").forEach((b) => b.classList.toggle("active", b.dataset.bottom === which));
  $("bottom-output").hidden = which !== "output";
  $("bottom-problems").hidden = which !== "problems";
}

/* ----------------------------------------------------------------- compile */
let pending = false;

async function compile() {
  if (state.busy) {
    pending = true; // run again with the latest input once the current request finishes
    return;
  }
  const mode = state.mode;
  const source = ctx.source();
  const payload = { mode, source, options: { optimize: $("optimize").checked, run: true } };
  if (mode === "expression") {
    payload.variables = collectVariables();
    if (payload.variables === null) return;
  }
  state.busy = true;
  $("compile").disabled = true;
  try {
    const result = await api.compile(payload);
    stopPlayer();
    state.results[mode] = result;
    view = {};
    if (mode === "program") {
      state.dirty = false;
      storage.set("source", source);
      editor.setDiagnostics(result.diagnostics);
      editor.setExecLine(null);
      editor.setHits(null);
      editor.clearHighlight();
      const hasErrors = result.diagnostics.some((d) => d.severity === "error" && d.phase !== "runtime");
      showBottom(hasErrors ? "problems" : "output");
      if (hasErrors && ["run", "optimized", "cfg", "tac"].includes(currentTab())) {
        state.tab.program = PHASE_TAB[result.failed_phase] || "tokens";
      }
    } else {
      storage.set("expression", source);
      renderExprMirror(null);
    }
    renderBottom();
    renderView();
  } catch (error) {
    toast(error.message);
    $("bottom-output").replaceChildren(el("div", { class: "line rt-error" }, error.message));
    showBottom("output");
  } finally {
    state.busy = false;
    $("compile").disabled = false;
    if (pending) {
      pending = false;
      compile();
    }
  }
}

/* --------------------------------------------------------- expression mode */
function collectVariables() {
  const vars = {};
  let ok = true;
  $("variables").querySelectorAll(".var-row").forEach((row) => {
    const name = row.querySelector("[data-field=name]");
    const value = row.querySelector("[data-field=value]");
    const n = name.value.trim();
    const v = value.value.trim();
    name.classList.toggle("bad", n !== "" && !/^[A-Za-z_]\w*$/.test(n));
    value.classList.toggle("bad", v !== "" && !Number.isFinite(Number(v)));
    if (!n || !v) return;
    if (name.classList.contains("bad") || value.classList.contains("bad")) { ok = false; return; }
    vars[n] = Number(v);
  });
  return ok ? vars : null;
}

function renderVariables() {
  const host = $("variables");
  host.replaceChildren();
  state.variables.forEach((v, i) => {
    const update = () => {
      state.variables[i] = { name: nameInput.value, value: valueInput.value };
      storage.set("variables", state.variables);
      scheduleExpression();
    };
    const nameInput = el("input", { value: v.name, placeholder: "name", "data-field": "name", "aria-label": "Variable name" });
    const valueInput = el("input", { value: v.value, placeholder: "value", "data-field": "value", "aria-label": "Value", inputmode: "decimal" });
    nameInput.addEventListener("input", update);
    valueInput.addEventListener("input", update);
    host.append(el("div", { class: "var-row" }, nameInput, valueInput,
      el("button", { class: "btn ghost small", title: "Remove", onclick: () => {
        state.variables.splice(i, 1);
        storage.set("variables", state.variables);
        renderVariables();
        scheduleExpression();
      } }, "✕")));
  });
}

function scheduleExpression() {
  clearTimeout(exprTimer);
  exprTimer = setTimeout(compile, 250);
}

function renderExprMirror(span) {
  const host = $("expr-status");
  const text = $("expr").value;
  const result = state.results.expression;
  host.replaceChildren();
  if (!result) return;
  const error = result.diagnostics.find((d) => d.severity === "error" && d.phase !== "runtime");
  const status = error ? el("span", { class: "act error" }, `✗ ${error.phase} error`)
    : el("span", { class: "act accept" }, "✓ valid");
  let mirror = text;
  if (span && span[0] === 1) {
    const a = span[1] - 1;
    const b = Math.max(span[3] - 1, a + 1);
    mirror = el("span", {}, text.slice(0, a), el("mark", { class: "mark-hl-strong" }, text.slice(a, b) || " "), text.slice(b));
  }
  host.append(status, " ", el("span", { class: "mono" }, mirror));
  if (error) host.append(overviewView.caretBox(text, error));
}

/* --------------------------------------------------------------- examples */
function fillExamples() {
  const select = $("examples");
  select.replaceChildren(el("option", { value: "" }, "Load a sample…"));
  if (!state.examples) return;
  if (state.mode === "program") {
    const groups = {};
    for (const ex of state.examples.programs) (groups[ex.category] ||= []).push(ex);
    for (const [category, items] of Object.entries(groups)) {
      select.append(el("optgroup", { label: category[0].toUpperCase() + category.slice(1) },
        ...items.map((ex) => el("option", { value: ex.id, title: ex.description }, ex.title))));
    }
  } else {
    const groups = {};
    for (const ex of state.examples.expressions) (groups[ex.category] ||= []).push(ex);
    for (const [category, items] of Object.entries(groups)) {
      select.append(el("optgroup", { label: category === "valid" ? "Valid" : `${category} errors` },
        ...items.map((ex) => el("option", { value: ex.id }, `${ex.title}:  ${ex.expression}`))));
    }
  }
}

function loadExample(id) {
  if (!id || !state.examples) return;
  if (state.mode === "program") {
    const ex = state.examples.programs.find((e) => e.id === id);
    editor.value = ex.source;
    compile();
  } else {
    const ex = state.examples.expressions.find((e) => e.id === id);
    $("expr").value = ex.expression;
    if (Object.keys(ex.variables).length) {
      state.variables = Object.entries(ex.variables).map(([name, value]) => ({ name, value: String(value) }));
      storage.set("variables", state.variables);
      renderVariables();
    }
    compile();
  }
  $("examples").value = "";
}

/* ------------------------------------------------------------------- modes */
function setMode(mode) {
  stopPlayer();
  state.mode = mode;
  storage.set("mode", mode);
  document.querySelectorAll(".seg").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  $("program-input").hidden = mode !== "program";
  $("expression-input").hidden = mode !== "expression";
  $("optimize-wrap").hidden = mode !== "program";
  $("compile-label").textContent = mode === "program" ? "Compile & Run" : "Analyze";
  fillExamples();
  view = {};
  if (mode === "program") {
    editor.refresh();
    if (!state.results.program) compile();
  } else if (!state.results.expression) {
    compile();
  }
  renderBottom();
  renderView();
  renderExprMirror(null);
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  storage.set("theme", theme);
}

/* -------------------------------------------------------------------- init */
const DEFAULT_PROGRAM = `// Recursive factorial — press Compile & Run (Ctrl+Enter)
int fact(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * fact(n - 1);
}

for (int i = 1; i <= 5; i++) {
    print(i, "! =", fact(i));
}
`;

async function init() {
  setTheme(storage.get("theme", window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark"));
  editor = new Editor($("editor-host"));
  editor.value = storage.get("source", DEFAULT_PROGRAM);
  editor.onChange(() => {
    if (!state.dirty) { state.dirty = true; renderPipeline($("pipeline"), { result: ctx.result, mode: state.mode, dirty: true, activeTab: currentTab(), onPick: (t) => selectTab(t) }); }
  });
  editor.onCursor((line, col) => { $("cursor-pos").textContent = `Ln ${line}, Col ${col}`; });
  $("expr").value = storage.get("expression", "a + b * (c - 2)");
  $("optimize").checked = storage.get("optimize", false);
  renderVariables();

  $("compile").addEventListener("click", compile);
  $("optimize").addEventListener("change", () => { storage.set("optimize", $("optimize").checked); compile(); });
  $("theme").addEventListener("click", () => {
    setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    renderView();
  });
  document.querySelectorAll(".seg").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  document.querySelectorAll("[data-bottom]").forEach((b) => b.addEventListener("click", () => showBottom(b.dataset.bottom)));
  $("examples").addEventListener("change", (e) => loadExample(e.target.value));
  $("expr").addEventListener("input", scheduleExpression);
  $("expr").addEventListener("keydown", (e) => { if (e.key === "Enter") { clearTimeout(exprTimer); compile(); } });
  $("expr-clear").addEventListener("click", () => { $("expr").value = ""; $("expr").focus(); compile(); });
  $("var-add").addEventListener("click", () => { state.variables.push({ name: "", value: "" }); renderVariables(); });
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); compile(); }
  });

  setMode(state.mode);
  try {
    state.examples = await api.examples();
    fillExamples();
  } catch (error) {
    toast(error.message);
  }
}

init();
