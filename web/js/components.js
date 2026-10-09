// Reusable UI pieces: step player, SVG tree, collapsible outline tree.
import { el, icon, svg, storage } from "./dom.js";

/* ------------------------------------------------------------------ stepper */
const registry = {};
const player = { timer: null, key: null };

export function stopPlayer() {
  clearInterval(player.timer);
  player.timer = null;
  player.key = null;
}

export function isPlaying(key) {
  return player.key === key && player.timer !== null;
}

function startPlayer(key) {
  stopPlayer();
  player.key = key;
  const speed = storage.get("speed", 350);
  player.timer = setInterval(() => {
    const entry = registry[key];
    if (!entry) return stopPlayer();
    const current = entry.get();
    if (current >= entry.count) {
      stopPlayer();
      entry.set(entry.count);
      return;
    }
    entry.set(current + 1);
  }, speed);
}

export function stepper({ key, count, value, onChange, describe }) {
  registry[key] = { get: () => registry[key].value, set: onChange, count, value };
  const go = (v) => onChange(Math.max(1, Math.min(count, v)));
  const playBtn = el("button", {
    title: isPlaying(key) ? "Pause" : "Play",
    onclick: () => {
      if (isPlaying(key)) { stopPlayer(); onChange(value); } else {
        if (value >= count) go(1);
        startPlayer(key);
        onChange(registry[key].value);
      }
    },
  }, icon(isPlaying(key) ? "pause" : "play"));
  const range = el("input", { type: "range", min: 1, max: Math.max(1, count), value });
  range.addEventListener("input", () => { stopPlayer(); go(Number(range.value)); });
  const speed = el("select", { title: "Playback speed" },
    ...[[900, "0.5×"], [350, "1×"], [150, "2×"], [40, "5×"]].map(([ms, label]) =>
      el("option", { value: ms, selected: storage.get("speed", 350) === ms }, label)));
  speed.addEventListener("change", () => {
    storage.set("speed", Number(speed.value));
    if (isPlaying(key)) startPlayer(key);
  });
  const bar = el("div", { class: "stepper" },
    el("button", { title: "First step", onclick: () => { stopPlayer(); go(1); } }, icon("first")),
    el("button", { title: "Previous step (←)", onclick: () => { stopPlayer(); go(value - 1); } }, icon("prev")),
    playBtn,
    el("button", { title: "Next step (→)", onclick: () => { stopPlayer(); go(value + 1); } }, icon("next")),
    el("button", { title: "Last step", onclick: () => { stopPlayer(); go(count); } }, icon("last")),
    range,
    el("span", { class: "pos" }, `${value} / ${count}`),
    speed,
    describe ? el("div", { class: "now" }, describe(value)) : null);
  bar.dataset.stepperKey = key;
  return bar;
}

// Keyboard ← / → drive whichever stepper is visible.
document.addEventListener("keydown", (event) => {
  if (event.target.closest("input, select, textarea, .CodeMirror")) return;
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  const bar = document.querySelector("#view .stepper");
  if (!bar) return;
  const entry = registry[bar.dataset.stepperKey];
  if (!entry) return;
  event.preventDefault();
  stopPlayer();
  const delta = event.key === "ArrowLeft" ? -1 : 1;
  entry.set(Math.max(1, Math.min(entry.count, entry.get() + delta)));
});

/* ----------------------------------------------------------------- SVG tree */
const LEVEL = 66;
const GAP = 12;
const BOX_H = 30;

function boxWidth(text, sub) {
  const longest = Math.max(text.length, sub ? sub.length * 0.8 : 0);
  return Math.max(34, Math.round(longest * 8.2 + 18));
}

/**
 * Draw a tree from {root, nodes:[{id, children:[ids]}]}.
 * describe(node) -> {text, sub, cls}; state(node) -> "ghost" | "new" | "" ; skip(node) -> bool
 */
export function svgTree(flat, { describe, state = () => "", skip = () => false, onClick, selected }) {
  const byId = new Map(flat.nodes.map((n) => [n.id, n]));
  const kids = (n) => n.children.map((id) => byId.get(id)).filter((c) => c && !skip(c));
  const pos = new Map();
  let cursor = 0;
  let maxDepth = 0;
  // iterative post-order layout: leaves get consecutive x slots, parents are centred
  const stack = [[byId.get(flat.root), 0, false]];
  while (stack.length) {
    const [node, depth, done] = stack.pop();
    const info = describe(node);
    const w = boxWidth(info.text, info.sub);
    const children = kids(node);
    if (!done && children.length) {
      stack.push([node, depth, true]);
      for (let i = children.length - 1; i >= 0; i--) stack.push([children[i], depth + 1, false]);
      continue;
    }
    maxDepth = Math.max(maxDepth, depth);
    let x;
    if (!children.length) {
      x = cursor + w / 2;
      cursor += w + GAP;
    } else {
      x = (pos.get(children[0].id).x + pos.get(children[children.length - 1].id).x) / 2;
      const left = x - w / 2;
      if (left < 0) x -= left;
    }
    pos.set(node.id, { x, y: depth * LEVEL + 22, w, info });
  }
  const width = Math.max(cursor, 120) + 10;
  const height = (maxDepth + 1) * LEVEL;
  const edges = svg("g");
  const nodes = svg("g");
  for (const node of flat.nodes) {
    const p = pos.get(node.id);
    if (!p) continue;
    const st = state(node);
    for (const child of kids(node)) {
      const c = pos.get(child.id);
      const ghost = state(child) === "ghost" ? " ghost" : "";
      edges.append(svg("path", {
        class: "edge" + ghost,
        d: `M${p.x},${p.y + BOX_H / 2} C${p.x},${p.y + LEVEL / 2} ${c.x},${c.y - LEVEL / 2} ${c.x},${c.y - BOX_H / 2}`,
      }));
    }
    const classes = ["node", p.info.cls || "", st, selected === node.id ? "selected" : ""].join(" ");
    const g = svg("g", { class: classes, transform: `translate(${p.x},${p.y})` },
      svg("title", {}, p.info.title || p.info.text),
      svg("rect", { x: -p.w / 2, y: -BOX_H / 2, width: p.w, height: BOX_H, rx: 7 }),
      svg("text", { y: p.info.sub ? -4 : 1 }, p.info.text),
      p.info.sub ? svg("text", { class: "sub", y: 9 }, p.info.sub) : null);
    if (onClick) g.addEventListener("click", () => onClick(node));
    nodes.append(g);
  }
  return svg("svg", { class: "tree", width, height, viewBox: `0 0 ${width} ${height}` }, edges, nodes);
}

/* ------------------------------------------------------------- outline tree */
export function outlineTree(flat, { render, onClick, selected, openDepth = 8, skip = () => false }) {
  const byId = new Map(flat.nodes.map((n) => [n.id, n]));
  function build(node, depth) {
    const children = node.children.map((id) => byId.get(id)).filter((c) => c && !skip(c));
    const twisty = el("span", { class: "twisty" }, children.length ? (depth < openDepth ? "▾" : "▸") : "·");
    const row = el("span", { class: "row" + (selected === node.id ? " selected" : "") }, twisty, render(node));
    const li = el("li", {}, row);
    let list = null;
    if (children.length) {
      list = el("ul", {}, ...(depth < openDepth ? children.map((c) => build(c, depth + 1)) : []));
      list.hidden = depth >= openDepth;
      li.append(list);
    }
    twisty.addEventListener("click", (event) => {
      event.stopPropagation();
      if (!list) return;
      if (!list.childNodes.length) children.forEach((c) => list.append(build(c, openDepth)));
      list.hidden = !list.hidden;
      twisty.textContent = list.hidden ? "▸" : "▾";
    });
    row.addEventListener("click", () => onClick && onClick(node));
    return li;
  }
  return el("div", { class: "outline" }, el("ul", {}, build(byId.get(flat.root), 0)));
}
