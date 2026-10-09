// CodeMirror wrapper: MiniC highlighting, diagnostics, cross-highlighting, execution line.
/* global CodeMirror */

CodeMirror.defineSimpleMode("minic", {
  start: [
    { regex: /"(?:[^\\"]|\\.)*"?/, token: "string" },
    { regex: /\/\/.*/, token: "comment" },
    { regex: /\/\*/, token: "comment", next: "comment" },
    { regex: /\b(?:int|float|bool|void)\b/, token: "type" },
    { regex: /\b(?:if|else|while|do|for|return|break|continue|print)\b/, token: "keyword" },
    { regex: /\b(?:true|false)\b/, token: "atom" },
    { regex: /\d+(?:\.\d+)?/, token: "number" },
    { regex: /[-+*/%=<>!&|]+/, token: "operator" },
    { regex: /[A-Za-z_]\w*(?=\s*\()/, token: "def" },
    { regex: /[A-Za-z_]\w*/, token: "variable" },
  ],
  comment: [
    { regex: /.*?\*\//, token: "comment", next: "start" },
    { regex: /.*/, token: "comment" },
  ],
  meta: { lineComment: "//" },
});

function toPos(line, col) {
  return { line: line - 1, ch: col - 1 };
}

export class Editor {
  constructor(host) {
    this.cm = CodeMirror(host, {
      mode: "minic",
      lineNumbers: true,
      indentUnit: 4,
      tabSize: 4,
      indentWithTabs: false,
      styleActiveLine: true,
      matchBrackets: true,
      autoCloseBrackets: true,
      gutters: ["gutter-diag", "hits", "CodeMirror-linenumbers"],
      extraKeys: {
        Tab: (cm) => cm.execCommand("insertSoftTab"),
        "Ctrl-/": "toggleComment",
      },
    });
    this.diagMarks = [];
    this.hlMarks = [];
    this.execLine = null;
  }

  get value() { return this.cm.getValue(); }
  set value(text) { this.cm.setValue(text); this.cm.clearHistory(); }

  onChange(fn) { this.cm.on("changes", () => fn(this.value)); }
  onCursor(fn) {
    this.cm.on("cursorActivity", () => {
      const pos = this.cm.getCursor();
      fn(pos.line + 1, pos.ch + 1);
    });
  }
  refresh() { this.cm.refresh(); }
  focus() { this.cm.focus(); }

  _range(span) {
    let from = toPos(span[0], span[1]);
    let to = toPos(span[2], span[3]);
    if (from.line === to.line && from.ch === to.ch) {
      // zero-width span (e.g. missing ';' after a token): mark the previous character
      if (from.ch > 0) from = { line: from.line, ch: from.ch - 1 };
      else to = { line: to.line, ch: to.ch + 1 };
    }
    return [from, to];
  }

  setDiagnostics(diagnostics) {
    this.diagMarks.forEach((m) => m.clear());
    this.diagMarks = [];
    this.cm.clearGutter("gutter-diag");
    for (const d of diagnostics) {
      if (!d.span) continue;
      const [from, to] = this._range(d.span);
      this.diagMarks.push(this.cm.markText(from, to, {
        className: d.severity === "error" ? "mark-error" : "mark-warning",
        attributes: { title: `${d.code}: ${d.message}` },
      }));
      const marker = document.createElement("span");
      marker.className = `gutter-marker ${d.severity}`;
      marker.title = d.message;
      this.cm.setGutterMarker(from.line, "gutter-diag", marker);
    }
  }

  highlight(span, { strong = false, scroll = true, keep = false } = {}) {
    if (!keep) this.clearHighlight();
    if (!span) return;
    const [from, to] = this._range(span);
    this.hlMarks.push(this.cm.markText(from, to, { className: strong ? "mark-hl-strong" : "mark-hl" }));
    if (scroll) this.cm.scrollIntoView({ from, to }, 80);
  }

  highlightLines(lines) {
    this.clearHighlight();
    for (const line of lines) {
      const text = this.cm.getLine(line - 1) || "";
      this.hlMarks.push(this.cm.markText({ line: line - 1, ch: 0 }, { line: line - 1, ch: text.length || 1 },
        { className: "mark-hl" }));
    }
    if (lines.length) this.cm.scrollIntoView({ line: lines[0] - 1, ch: 0 }, 80);
  }

  clearHighlight() {
    this.hlMarks.forEach((m) => m.clear());
    this.hlMarks = [];
  }

  setExecLine(line, isError = false) {
    if (this.execLine !== null) {
      this.cm.removeLineClass(this.execLine, "background", "line-exec");
      this.cm.removeLineClass(this.execLine, "background", "line-error");
    }
    this.execLine = null;
    if (!line) return;
    this.execLine = line - 1;
    this.cm.addLineClass(this.execLine, "background", isError ? "line-error" : "line-exec");
    this.cm.scrollIntoView({ line: this.execLine, ch: 0 }, 100);
  }

  setHits(counts) {
    this.cm.clearGutter("hits");
    if (!counts) return;
    const max = Math.max(1, ...Object.values(counts));
    for (const [line, n] of Object.entries(counts)) {
      const marker = document.createElement("span");
      marker.className = "hit" + (n >= max * 0.5 && n > 1 ? " hot" : "");
      marker.textContent = n > 999 ? "999+" : String(n);
      marker.title = `line ${line} executed ${n} time(s) so far`;
      this.cm.setGutterMarker(Number(line) - 1, "hits", marker);
    }
  }

  goto(line, col) {
    this.cm.focus();
    this.cm.setCursor(toPos(line, col || 1));
    this.cm.scrollIntoView(null, 120);
  }
}
