import { el, empty, stat, viewHead } from "../dom.js";

export function render(container, ctx) {
  const sem = ctx.result?.phases.semantic;
  if (!sem || sem.status === "skipped") {
    container.append(empty("No symbol table", "Semantic analysis runs after the program parses successfully."));
    return;
  }
  if (ctx.mode === "expression") return renderExpression(container, ctx, sem);
  const symbols = sem.symbols;
  const byId = Object.fromEntries(symbols.map((s) => [s.id, s]));
  const stats = sem.stats;
  container.append(
    viewHead("Semantic analysis", "Names are resolved through nested scopes and every expression is type-checked."),
    el("div", { class: "stats" }, stat(stats.scopes, "scopes"), stat(stats.variables, "variables"),
      stat(stats.parameters, "parameters"), stat(stats.functions, "functions"),
      stat(stats.errors, "errors"), stat(stats.warnings, "warnings")),
  );
  const semErrors = ctx.result.diagnostics.filter((d) => d.phase === "semantic");
  if (semErrors.length) {
    container.append(el("div", { class: `banner ${stats.errors ? "error" : "warn"}` },
      el("strong", {}, stats.errors ? `${stats.errors} semantic error(s)` : `${stats.warnings} warning(s)`),
      ...semErrors.slice(0, 6).map((d) => el("div", { class: "small" }, `line ${d.line}: ${d.message}`))));
  }

  // scope tree
  const children = {};
  for (const scope of sem.scopes) (children[scope.parent ?? "root"] ||= []).push(scope);
  const symChip = (s) => el("span", {
    class: "sym", title: `${s.kind} declared at line ${s.line}${s.ir_name !== s.name ? ` (IR name ${s.ir_name})` : ""}`,
    onclick: () => ctx.highlight(s.span, { strong: true }),
  }, s.kind === "func" ? s.signature : s.name, s.kind !== "func" ? el("span", { class: "t" }, ` : ${s.type}`) : null);
  function scopeNode(scope) {
    const label = scope.kind === "global" ? "global scope" : scope.kind === "function" ? `function ${scope.name}()`
      : scope.kind === "loop" ? "for-loop scope" : "block scope";
    return el("li", { class: "scope" },
      el("div", { class: "scope-head", onclick: () => scope.span && ctx.highlight(scope.span) },
        el("span", { class: "chip" }, `#${scope.id}`), label,
        scope.span ? el("span", { class: "muted small" }, `lines ${scope.span[0]}–${scope.span[2]}`) : null),
      el("div", { class: "scope-syms" }, ...(scope.symbols.length ? scope.symbols.map((id) => symChip(byId[id]))
        : [el("span", { class: "muted small" }, "(no declarations)")])),
      children[scope.id] ? el("ul", {}, ...children[scope.id].map(scopeNode)) : null);
  }
  container.append(el("div", { class: "card scope-tree" }, el("h3", {}, "Scope tree"),
    el("ul", {}, ...(children.root || []).map(scopeNode))));

  container.append(el("table", { class: "grid" },
    el("thead", {}, el("tr", {}, ...["Name", "Kind", "Type", "Scope", "Declared", "IR name", "Used"].map((h) => el("th", {}, h)))),
    el("tbody", {}, ...symbols.map((s) => el("tr", { class: "clickable", onclick: () => ctx.highlight(s.span, { strong: true }) },
      el("td", { class: "mono tok-identifier" }, s.name),
      el("td", {}, s.kind),
      el("td", { class: "mono" }, s.kind === "func" ? s.signature : s.type),
      el("td", { class: "mono" }, `#${s.scope}`),
      el("td", { class: "mono" }, `line ${s.line}`),
      el("td", { class: "mono muted" }, s.ir_name),
      el("td", {}, s.used ? "✓" : el("span", { class: "muted" }, "–")))))));
}

function renderExpression(container, ctx, sem) {
  container.append(viewHead("Symbol table", "Identifiers in the expression and their values from the Variables panel."));
  if (!sem.symbols.length) {
    container.append(empty("No identifiers", "This expression uses numbers only."));
    return;
  }
  container.append(el("table", { class: "grid" },
    el("thead", {}, el("tr", {}, el("th", {}, "Variable"), el("th", {}, "Value"))),
    el("tbody", {}, ...sem.symbols.map((s) => el("tr", {},
      el("td", { class: "mono tok-identifier" }, s.name),
      el("td", { class: "mono" }, s.defined ? String(s.value) : el("span", { class: "muted" }, "(no value)")))))));
}
