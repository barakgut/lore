// core.js — payload access, DOM helpers, view registry. Loaded first.
const LORE = JSON.parse(document.getElementById("lore-data").textContent);
const VIEWS = {};
const TAB_ORDER = ["overview", "health", "stats", "graph", "browse", "search", "log", "inbox"];
const PAGES_BY_ID = new Map(LORE.pages.map(p => [p.id, p]));

function defineView(key, label, render) { VIEWS[key] = { key, label, render }; }
function pageById(id) { return PAGES_BY_ID.get(id) || null; }

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "text") node.textContent = value;
    else if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of [].concat(children || [])) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }
function fmtBytes(n) {
  const units = ["B", "KB", "MB", "GB"];
  let value = Number(n) || 0, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return (unit === 0 ? value : value.toFixed(1)) + " " + units[unit];
}
function fmtPct(x) { return Math.round((Number(x) || 0) * 100) + "%"; }

function pageLink(id, label) {
  const page = pageById(id);
  return el("a", { href: "#page/" + encodeURIComponent(id) }, label || (page ? page.title : id));
}
function navigate(hash) { window.location.hash = hash; }
function copyButton(text) {
  return el("button", {
    class: "copy", title: "Copy path", type: "button",
    onclick: () => navigator.clipboard && navigator.clipboard.writeText(text),
  }, "⧉");
}
function table(headers, rows) {
  const head = el("tr", {}, headers.map(h => el("th", { text: h })));
  return el("table", {}, [el("thead", {}, head),
                          el("tbody", {}, rows.map(cells => el("tr", {}, cells.map(
                            cell => el("td", {}, cell)))))]);
}

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs, children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined) continue;
    node.setAttribute(key, value);
  }
  for (const child of [].concat(children || [])) if (child) node.append(child);
  return node;
}

function bar(fraction, options) {
  const opts = options || {};
  const width = opts.width || 160, height = opts.height || 8;
  const filled = Math.max(0, Math.min(1, Number(fraction) || 0)) * width;
  const colour = opts.color || (fraction >= 0.9 ? "var(--good)"
                                : fraction >= 0.6 ? "var(--warn)" : "var(--bad)");
  return svgEl("svg", { width: width, height: height, class: "bar",
                        role: "img", "aria-label": fmtPct(fraction) }, [
    svgEl("rect", { x: 0, y: 0, width: width, height: height, rx: 4, fill: "var(--surface-3)" }),
    svgEl("rect", { x: 0, y: 0, width: filled, height: height, rx: 4, fill: colour }),
  ]);
}
