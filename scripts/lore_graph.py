#!/usr/bin/env python3
"""Export a lore's wikilink graph as a self-contained interactive HTML file.

Standalone, human-only tool — not part of the lore plugin contract.
Usage: python3 lore_graph.py <lore-path> [-o out.html]
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")


def _frontmatter_field(fm_text: str, field: str) -> str | None:
    m = re.search(rf"^{field}:\s*(.+?)\s*$", fm_text, re.MULTILINE)
    return m.group(1) if m else None


def parse_lore(lore: Path) -> dict:
    nodes = []
    edges = []
    seen_edges = set()
    page_ids = set()
    for path in sorted((lore / "wiki").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm = FRONTMATTER_RE.match(text)
        title = _frontmatter_field(fm.group(1), "title") if fm else None
        ptype = _frontmatter_field(fm.group(1), "type") if fm else None
        page_ids.add(path.stem)
        nodes.append({
            "id": path.stem,
            "title": title or path.stem.replace("_", " "),
            "type": ptype or "unknown",
            "ghost": False,
        })
        body = text[fm.end():] if fm else text
        for target in WIKILINK_RE.findall(body):
            target_id = target.strip().replace(" ", "_")
            if (path.stem, target_id) not in seen_edges:
                seen_edges.add((path.stem, target_id))
                edges.append({"source": path.stem, "target": target_id})
    for _, target_id in sorted(seen_edges):
        if target_id not in page_ids:
            page_ids.add(target_id)
            nodes.append({
                "id": target_id,
                "title": target_id.replace("_", " "),
                "type": "missing",
                "ghost": True,
            })
    return {"nodes": nodes, "edges": edges}


# Categorical slots validated all-pairs in light AND dark modes
# (dataviz reference palette; card/unknown use neutral ink + square, not a 5th hue).
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__NAME__ — lore graph</title>
<style>
  :root {
    color-scheme: light dark;
    --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
    --hairline: #e1e0d9; --ring: rgba(11,11,11,0.10);
    --c-concept: #2a78d6; --c-source: #eda100; --c-answer: #e87ba4;
    --c-decision: #008300; --c-card: #898781; --c-unknown: #898781;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
      --hairline: #2c2c2a; --ring: rgba(255,255,255,0.10);
      --c-concept: #3987e5; --c-source: #c98500; --c-answer: #d55181;
      --c-decision: #008300;
    }
  }
  * { margin: 0; box-sizing: border-box; }
  body { background: var(--surface); color: var(--ink); overflow: hidden;
         font: 13px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; }
  #hud { position: fixed; top: 0; left: 0; right: 0; padding: 10px 14px;
         display: flex; gap: 18px; align-items: baseline; flex-wrap: wrap;
         pointer-events: none; }
  #hud h1 { font-size: 14px; font-weight: 600; }
  #hud .hint { color: var(--muted); font-size: 12px; }
  .legend { display: flex; gap: 14px; flex-wrap: wrap; }
  .legend span { display: inline-flex; align-items: center; gap: 5px;
                 color: var(--ink-2); font-size: 12px; }
  .swatch { width: 10px; height: 10px; border-radius: 50%;
            box-shadow: inset 0 0 0 1px var(--ring); }
  .swatch.square { border-radius: 2px; }
  .swatch.ghost { background: none; border: 1px dashed var(--muted); }
  #tip { position: fixed; display: none; padding: 6px 9px; max-width: 300px;
         background: var(--surface); color: var(--ink);
         border: 1px solid var(--hairline); border-radius: 6px;
         box-shadow: 0 2px 8px rgba(0,0,0,0.15); pointer-events: none; }
  #tip .t { color: var(--ink-2); font-size: 11px; }
  canvas { display: block; cursor: grab; }
</style>
</head>
<body>
<canvas id="c"></canvas>
<div id="hud">
  <h1>__NAME__</h1>
  <div class="legend">
    <span><i class="swatch" style="background:var(--c-concept)"></i>concept</span>
    <span><i class="swatch" style="background:var(--c-source)"></i>source</span>
    <span><i class="swatch" style="background:var(--c-answer)"></i>answer</span>
    <span><i class="swatch" style="background:var(--c-decision)"></i>decision</span>
    <span><i class="swatch square" style="background:var(--c-card)"></i>card</span>
    <span><i class="swatch ghost"></i>missing page</span>
  </div>
  <span class="hint">drag nodes · drag background to pan · wheel to zoom</span>
</div>
<div id="tip"></div>
<script>
const GRAPH = __DATA__;
const canvas = document.getElementById("c"), ctx = canvas.getContext("2d");
const tip = document.getElementById("tip");
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
let W, H, dpr;
function resize() {
  dpr = window.devicePixelRatio || 1;
  W = window.innerWidth; H = window.innerHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.width = W + "px"; canvas.style.height = H + "px";
}
resize();
window.addEventListener("resize", () => { resize(); draw(); });

const nodes = GRAPH.nodes, edges = GRAPH.edges;
const byId = {};
nodes.forEach((n, i) => {
  // deterministic golden-angle spiral start (no RNG: stable output)
  const a = i * 2.39996, r = 24 * Math.sqrt(i + 1);
  n.x = Math.cos(a) * r; n.y = Math.sin(a) * r;
  n.vx = 0; n.vy = 0; n.deg = 0;
  byId[n.id] = n;
});
const links = edges
  .map(e => ({ s: byId[e.source], t: byId[e.target] }))
  .filter(l => l.s && l.t);
links.forEach(l => { l.s.deg++; l.t.deg++; });

let alpha = 1;
let dragging = null, panning = false, px0 = 0, py0 = 0;
function tick() {
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      let dx = a.x - b.x, dy = a.y - b.y;
      let d2 = dx * dx + dy * dy || 1;
      if (d2 < 250000) {
        const f = 1600 / d2;
        dx *= f; dy *= f;
        a.vx += dx; a.vy += dy; b.vx -= dx; b.vy -= dy;
      }
    }
  }
  links.forEach(l => {
    const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y;
    const d = Math.sqrt(dx * dx + dy * dy) || 1;
    const f = 0.02 * (d - 90) / d;
    l.s.vx += dx * f; l.s.vy += dy * f;
    l.t.vx -= dx * f; l.t.vy -= dy * f;
  });
  nodes.forEach(n => {
    n.vx -= n.x * 0.002; n.vy -= n.y * 0.002;   // gentle centering
    if (n !== dragging) { n.x += n.vx * alpha; n.y += n.vy * alpha; }
    n.vx *= 0.6; n.vy *= 0.6;
  });
  alpha = Math.max(alpha * 0.995, 0.03);
}

let scale = 1, ox = 0, oy = 0;                   // view transform
const toScreen = n => [W / 2 + (n.x + ox) * scale, H / 2 + (n.y + oy) * scale];
function nodeColor(n) {
  if (n.ghost) return css("--muted");
  return css("--c-" + n.type) || css("--c-unknown");
}
function draw() {
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  ctx.strokeStyle = css("--hairline"); ctx.lineWidth = 1;
  links.forEach(l => {
    const [x1, y1] = toScreen(l.s), [x2, y2] = toScreen(l.t);
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  });
  const showLabels = scale > 0.5;
  nodes.forEach(n => {
    const [x, y] = toScreen(n);
    const r = 6 + Math.min(n.deg, 8);
    ctx.beginPath();
    if (n.ghost) {
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = css("--muted"); ctx.lineWidth = 1.5;
      ctx.arc(x, y, r, 0, 7); ctx.stroke();
      ctx.setLineDash([]);
    } else {
      ctx.fillStyle = nodeColor(n);
      if (n.type === "card") ctx.rect(x - r, y - r, 2 * r, 2 * r);
      else ctx.arc(x, y, r, 0, 7);
      ctx.fill();
      ctx.strokeStyle = css("--ring"); ctx.lineWidth = 1; ctx.stroke();
    }
    if (showLabels) {
      ctx.fillStyle = css("--ink-2");
      ctx.font = "11px system-ui, sans-serif";
      ctx.fillText(n.title, x + r + 4, y + 4);
    }
  });
}
function loop() { tick(); draw(); requestAnimationFrame(loop); }
loop();

const fromScreen = (px, py) => [(px - W / 2) / scale - ox, (py - H / 2) / scale - oy];
function nodeAt(px, py) {
  for (let i = nodes.length - 1; i >= 0; i--) {
    const [x, y] = toScreen(nodes[i]);
    const r = 6 + Math.min(nodes[i].deg, 8) + 4;   // hit target > mark
    if ((px - x) ** 2 + (py - y) ** 2 < r * r) return nodes[i];
  }
  return null;
}
canvas.addEventListener("mousedown", e => {
  dragging = nodeAt(e.clientX, e.clientY);
  if (!dragging) { panning = true; px0 = e.clientX; py0 = e.clientY; }
  canvas.style.cursor = "grabbing";
});
window.addEventListener("mousemove", e => {
  if (dragging) {
    const [wx, wy] = fromScreen(e.clientX, e.clientY);
    dragging.x = wx; dragging.y = wy; alpha = Math.max(alpha, 0.3);
  } else if (panning) {
    ox += (e.clientX - px0) / scale; oy += (e.clientY - py0) / scale;
    px0 = e.clientX; py0 = e.clientY;
  } else {
    const n = nodeAt(e.clientX, e.clientY);
    if (n) {
      tip.style.display = "block";
      tip.style.left = (e.clientX + 12) + "px";
      tip.style.top = (e.clientY + 12) + "px";
      tip.innerHTML = "<b></b><div class='t'></div>";
      tip.querySelector("b").textContent = n.title;
      tip.querySelector(".t").textContent = n.ghost ? "missing page" : n.type;
    } else tip.style.display = "none";
  }
});
window.addEventListener("mouseup", () => {
  dragging = null; panning = false; canvas.style.cursor = "grab";
});
canvas.addEventListener("wheel", e => {
  e.preventDefault();
  const k = e.deltaY < 0 ? 1.1 : 1 / 1.1;
  const [wx, wy] = fromScreen(e.clientX, e.clientY);
  scale *= k;
  const [wx2, wy2] = fromScreen(e.clientX, e.clientY);
  ox += wx2 - wx; oy += wy2 - wy;
}, { passive: false });
</script>
</body>
</html>
"""


def build_html(graph: dict, name: str) -> str:
    data = json.dumps(graph, indent=1).replace("</", "<\\/")
    return (HTML_TEMPLATE
            .replace("__NAME__", html.escape(name))
            .replace("__DATA__", data))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Export a lore's wikilink graph as a self-contained HTML viewer.")
    parser.add_argument("lore", help="path to the lore folder (must contain wiki/)")
    parser.add_argument("-o", "--output", default="lore-graph.html",
                        help="output HTML file (default: ./lore-graph.html)")
    args = parser.parse_args(argv)

    lore = Path(args.lore).expanduser().resolve()
    if not (lore / "wiki").is_dir():
        sys.exit(f"error: {lore} has no wiki/ directory — not a lore")

    graph = parse_lore(lore)
    Path(args.output).write_text(build_html(graph, lore.name), encoding="utf-8")
    ghosts = sum(1 for n in graph["nodes"] if n["ghost"])
    print(f"{args.output}: {len(graph['nodes'])} nodes "
          f"({ghosts} missing), {len(graph['edges'])} edges")


if __name__ == "__main__":
    main()
