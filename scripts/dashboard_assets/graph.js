// graph.js — canvas force-directed wikilink graph. Deterministic layout, no RNG.
//
// Pure helpers (neighbourMap, withinHops, radiusOf, isolatedIdSet, idRanks,
// seedPosition, isolatedGridPosition, visibleNodes, isDimmed) hold every bit
// of logic that can be exercised without a canvas: node filtering, the
// focus/hops subgraph, the radius formula, the isolated/clustered split, and
// the deterministic layout seed. initGraph() wires those into the
// interactive canvas (drag/pan/zoom/hover/click) and the force simulation,
// which cannot usefully be asserted on outside a real browser.
const NODE_COLOURS = { concept: "--c-concept", source: "--c-source", answer: "--c-answer",
                       decision: "--c-decision", card: "--c-card", unknown: "--c-unknown" };

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function neighbourMap(edges) {
  const map = new Map();
  for (const edge of edges) {
    if (!map.has(edge.source)) map.set(edge.source, new Set());
    if (!map.has(edge.target)) map.set(edge.target, new Set());
    map.get(edge.source).add(edge.target);
    map.get(edge.target).add(edge.source);
  }
  return map;
}

function withinHops(startId, hops, edges) {
  const neighbours = neighbourMap(edges);
  const seen = new Set([startId]);
  let frontier = [startId];
  for (let step = 0; step < hops; step++) {
    const next = [];
    for (const id of frontier) {
      for (const other of neighbours.get(id) || []) {
        if (!seen.has(other)) { seen.add(other); next.push(other); }
      }
    }
    frontier = next;
  }
  return seen;
}

// Radius grows with inbound degree only (a page many others cite reads as a
// bigger node than one that merely cites a lot) — contract: 6 + min(in, 8).
function radiusOf(node) {
  return 6 + Math.min(node.in || 0, 8);
}

// A node with no edge touching it at all (neither as source nor target) is
// isolated — recomputed from the edge list rather than trusting a caller to
// pass LORE.graph.isolated, so a custom {nodes, edges} pair (e.g. the mini
// graph's focus subset) is handled the same way as the full graph.
function isolatedIdSet(nodes, edges) {
  const touched = new Set();
  for (const edge of edges) { touched.add(edge.source); touched.add(edge.target); }
  const isolated = new Set();
  for (const node of nodes) if (!touched.has(node.id)) isolated.add(node.id);
  return isolated;
}

// Deterministic layout seeding, keyed by each node's id rather than its
// position in whatever array was passed in: two runs over the same lore
// produce the same picture regardless of node array order, because the seed
// is a pure function of the *set* of ids present, never of iteration order
// or any source of randomness.
function idRanks(nodes) {
  const sortedIds = nodes.map(node => node.id).slice().sort();
  const ranks = new Map();
  sortedIds.forEach((id, rank) => ranks.set(id, rank));
  return ranks;
}

function seedPosition(rank) {                 // golden-angle spiral: stable, no RNG
  const angle = rank * 2.39996, radius = 24 * Math.sqrt(rank + 1);
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

function isolatedGridPosition(row) {           // labelled grid below the main cluster
  return { x: -300 + (row % 8) * 80, y: 340 + Math.floor(row / 8) * 40 };
}

// The focus node itself is exempt from the hideDeprecated filter (never
// from the type/status/tag selects, and never its neighbours): the page
// view's mini graph always focuses the page it is showing with
// hideDeprecated defaulting to true and ships no controls to change it, so
// a deprecated page's own "Neighbourhood" widget must not drop its own
// subject — and must not render completely empty when its neighbours are
// deprecated too, which is a normal state (deprecating a page usually
// comes with deprecating what it linked to). The graph tab's focus mode
// has the same problem — focusing a deprecated node with "hide deprecated"
// checked would hide the very thing just focused — so one exemption here
// covers both call sites.
function visibleNodes(nodes, edges, state) {
  const inFocus = state.focus ? withinHops(state.focus, state.hops, edges) : null;
  return nodes.filter(node => {
    if (inFocus && !inFocus.has(node.id)) return false;
    const isFocusNode = Boolean(state.focus) && node.id === state.focus;
    if (state.hideDeprecated && node.status === "deprecated" && !isFocusNode) return false;
    if (state.type && node.type !== state.type) return false;
    if (state.status && node.status !== state.status) return false;
    if (state.tag && !(node.tags || []).includes(state.tag)) return false;
    return true;
  });
}

function isDimmed(node, query) {
  if (!query) return false;
  return !(node.title + " " + node.id).toLowerCase().includes(query.toLowerCase());
}

function initGraph(host, options) {
  const opts = options || {};
  const allNodes = (opts.nodes || LORE.graph.nodes).map(node => Object.assign({}, node));
  const allEdges = opts.edges || LORE.graph.edges;
  const state = { type: "", status: "", tag: "", hideDeprecated: true, query: "",
                  focusMode: false, focus: opts.focus || null, hops: opts.hops || 1 };
  const interactive = opts.interactive !== false;

  const canvas = el("canvas", { class: "graph-canvas" });
  host.append(canvas);
  const ctx = canvas.getContext("2d");
  let width = 0, height = opts.height || 600, dpr = 1;

  const byId = new Map(allNodes.map(node => [node.id, node]));
  const isolatedIds = [...isolatedIdSet(allNodes, allEdges)].sort();
  const isolatedRowOf = new Map(isolatedIds.map((id, row) => [id, row]));
  const ranks = idRanks(allNodes);
  for (const node of allNodes) {
    node.isolated = isolatedRowOf.has(node.id);
    const pos = node.isolated ? isolatedGridPosition(isolatedRowOf.get(node.id))
                               : seedPosition(ranks.get(node.id));
    node.x = pos.x; node.y = pos.y;
    node.vx = 0; node.vy = 0;
  }

  // Mutable view/interaction state, declared up front so every closure
  // below (including rebuild(), called immediately after) can safely
  // reference it.
  let alpha = 1, scale = 1, ox = 0, oy = 0;
  let dragging = null, panning = false, lastX = 0, lastY = 0, hovered = null;
  const onMouseUp = () => { dragging = null; panning = false; };

  let nodes = [];
  let links = [];
  function rebuild() {
    nodes = visibleNodes(allNodes, allEdges, state);
    const shown = new Set(nodes.map(node => node.id));
    links = allEdges.filter(edge => shown.has(edge.source) && shown.has(edge.target))
                    .map(edge => ({ s: byId.get(edge.source), t: byId.get(edge.target) }));
    alpha = 1;
  }
  rebuild();

  function resize() {
    dpr = window.devicePixelRatio || 1;
    width = host.clientWidth || 800;
    canvas.width = width * dpr; canvas.height = height * dpr;
    canvas.style.width = width + "px"; canvas.style.height = height + "px";
  }
  resize();
  const onResize = () => { resize(); draw(); };
  window.addEventListener("resize", onResize);

  function tick() {
    const moving = nodes.filter(node => !node.isolated);
    for (let i = 0; i < moving.length; i++) {
      for (let j = i + 1; j < moving.length; j++) {
        const a = moving[i], b = moving[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        const d2 = dx * dx + dy * dy || 1;
        if (d2 < 250000) {
          const force = 1600 / d2;
          dx *= force; dy *= force;
          a.vx += dx; a.vy += dy; b.vx -= dx; b.vy -= dy;
        }
      }
    }
    for (const link of links) {
      if (link.s.isolated || link.t.isolated) continue;
      const dx = link.t.x - link.s.x, dy = link.t.y - link.s.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = 0.02 * (distance - 90) / distance;
      link.s.vx += dx * force; link.s.vy += dy * force;
      link.t.vx -= dx * force; link.t.vy -= dy * force;
    }
    for (const node of moving) {
      node.vx -= node.x * 0.002; node.vy -= node.y * 0.002;      // gentle centering
      if (node !== dragging) { node.x += node.vx * alpha; node.y += node.vy * alpha; }
      node.vx *= 0.6; node.vy *= 0.6;
    }
    alpha = Math.max(alpha * 0.995, 0.03);
  }

  const toScreen = node => [width / 2 + (node.x + ox) * scale, height / 2 + (node.y + oy) * scale];
  const fromScreen = (px, py) => [(px - width / 2) / scale - ox, (py - height / 2) / scale - oy];

  function draw() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = cssVar("--hairline"); ctx.lineWidth = 1;
    for (const link of links) {
      const [x1, y1] = toScreen(link.s), [x2, y2] = toScreen(link.t);
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
    const showLabels = scale > 0.5;
    for (const node of nodes) {
      const [x, y] = toScreen(node);
      const r = radiusOf(node);
      ctx.globalAlpha = isDimmed(node, state.query) ? 0.25 : 1;
      ctx.beginPath();
      if (node.ghost) {
        ctx.setLineDash([3, 3]);
        ctx.strokeStyle = cssVar("--c-missing"); ctx.lineWidth = 1.5;
        ctx.arc(x, y, r, 0, 7); ctx.stroke();
        ctx.setLineDash([]);
      } else {
        ctx.fillStyle = cssVar(NODE_COLOURS[node.type] || NODE_COLOURS.unknown);
        if (node.type === "card") ctx.rect(x - r, y - r, 2 * r, 2 * r);
        else ctx.arc(x, y, r, 0, 7);
        ctx.fill();
        ctx.strokeStyle = node.id === state.focus ? cssVar("--ink") : cssVar("--ring");
        ctx.lineWidth = node.id === state.focus ? 2 : 1;
        ctx.stroke();
      }
      if (showLabels) {
        ctx.fillStyle = cssVar("--ink-2");
        ctx.font = "11px system-ui, sans-serif";
        ctx.fillText(node.title, x + r + 4, y + 4);
      }
      ctx.globalAlpha = 1;
    }
    if (nodes.some(node => node.isolated)) {
      const [x, y] = toScreen({ x: -320, y: 310 });
      ctx.fillStyle = cssVar("--muted");
      ctx.font = "11px system-ui, sans-serif";
      ctx.fillText("isolated pages", x, y);
    }
  }

  // running / stop() / loop() form the lifecycle: stop() is both what
  // destroy() calls and what the loop calls on itself the moment it notices
  // its host has been removed from the document — which is exactly what
  // happens every time the router (app.js) swaps in a different tab. That
  // self-check is what makes cleanup work for a navigation the view itself
  // never gets a chance to react to (there is no per-view unmount hook),
  // not just for a caller that explicitly holds onto and calls destroy().
  let running = true;
  function stop() {
    if (!running) return;
    running = false;
    window.removeEventListener("resize", onResize);
    window.removeEventListener("mouseup", onMouseUp);
    clear(host);
  }
  function loop() {
    if (!running) return;
    if (host.isConnected === false) { stop(); return; }
    tick(); draw();
    requestAnimationFrame(loop);
  }
  loop();

  function nodeAt(px, py) {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const [x, y] = toScreen(nodes[i]);
      const r = radiusOf(nodes[i]) + 4;
      if ((px - x) ** 2 + (py - y) ** 2 < r * r) return nodes[i];
    }
    return null;
  }

  const tip = el("div", { class: "graph-tip" });
  host.append(tip);

  function localPoint(event) {
    const box = canvas.getBoundingClientRect();
    return [event.clientX - box.left, event.clientY - box.top];
  }

  if (interactive) {
    canvas.addEventListener("mousedown", event => {
      const [px, py] = localPoint(event);
      dragging = nodeAt(px, py);
      if (!dragging) { panning = true; lastX = event.clientX; lastY = event.clientY; }
    });
    window.addEventListener("mouseup", onMouseUp);
    canvas.addEventListener("mousemove", event => {
      const [px, py] = localPoint(event);
      if (dragging) {
        const [wx, wy] = fromScreen(px, py);
        dragging.x = wx; dragging.y = wy; alpha = Math.max(alpha, 0.3);
      } else if (panning) {
        ox += (event.clientX - lastX) / scale; oy += (event.clientY - lastY) / scale;
        lastX = event.clientX; lastY = event.clientY;
      } else {
        hovered = nodeAt(px, py);
        if (hovered) {
          const page = pageById(hovered.id);
          tip.style.display = "block";
          tip.style.left = (px + 12) + "px";
          tip.style.top = (py + 12) + "px";
          clear(tip).append(el("strong", { text: hovered.title }),
                            el("div", { class: "muted",
                                        text: hovered.ghost ? "missing page"
                                              : (page && page.description) || hovered.type }));
        } else tip.style.display = "none";
      }
    });
    canvas.addEventListener("click", event => {
      const [px, py] = localPoint(event);
      const node = nodeAt(px, py);
      if (!node || node.ghost) return;
      if (state.focusMode) { state.focus = node.id; rebuild(); draw(); }
      else navigate("#page/" + encodeURIComponent(node.id));
    });
    canvas.addEventListener("wheel", event => {
      event.preventDefault();
      const [px, py] = localPoint(event);
      const [wx, wy] = fromScreen(px, py);
      scale *= event.deltaY < 0 ? 1.1 : 1 / 1.1;
      const [wx2, wy2] = fromScreen(px, py);
      ox += wx2 - wx; oy += wy2 - wy;
    }, { passive: false });
  }

  return {
    state,
    apply() { rebuild(); draw(); },
    destroy: stop,
  };
}
