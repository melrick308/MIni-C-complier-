// Small DOM helpers. User-provided text is only ever inserted as text nodes.

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key === "style" && typeof value === "object") Object.assign(node.style, value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  append(node, children);
  return node;
}

export function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

const SVG_NS = "http://www.w3.org/2000/svg";
export function svg(tag, attrs = {}, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined) continue;
    if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export const ICONS = {
  first: "M3 3h2v10H3zM13 3v10L6 8z",
  prev: "M11 3v10L4 8z",
  next: "M5 3v10l7-5z",
  last: "M11 3h2v10h-2zM3 3v10l7-5z",
  play: "M4 2.5v11l9-5.5z",
  pause: "M4 3h3v10H4zM9 3h3v10H9z",
};

export function icon(name) {
  return svg("svg", { viewBox: "0 0 16 16", "aria-hidden": "true" }, svg("path", { d: ICONS[name] }));
}

export const storage = {
  get(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
  },
};

let toastTimer = null;
export function toast(message) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 2600);
}

export function stat(value, label) {
  return el("div", { class: "stat" }, el("div", { class: "v" }, value), el("div", { class: "k" }, label));
}

export function empty(title, text) {
  return el("div", { class: "empty" }, el("strong", {}, title), text || "");
}

export function viewHead(title, subtitle, ...extra) {
  return el("div", { class: "view-head" }, el("h2", {}, title),
    subtitle ? el("span", { class: "muted" }, subtitle) : null, el("span", { class: "spacer" }), ...extra);
}

export function spanText(span) {
  if (!span) return "";
  return `${span[0]}:${span[1]}`;
}

export function plural(n, word, many) {
  return `${n} ${n === 1 ? word : (many || word + "s")}`;
}
