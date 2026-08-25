// views.js — tab and page renderers. Each view returns one DOM node.
// Structure: shared helpers first, then one render function per view, then
// the defineView(...) registration for each. Tasks 9-13 append further
// helper/render/defineView groups below the "page" view already here.
function offendersFor(pageId) {
  const hits = [];
  for (const dimension of LORE.health.dimensions) {
    for (const check of dimension.checks) {
      for (const offender of check.offenders) {
        if (offender.kind === "page" && offender.ref === pageId) {
          hits.push({ dimension: dimension.label, check: check.label, detail: offender.detail });
        }
      }
    }
  }
  return hits;
}

function indexOrder() {
  const order = [];
  for (const group of LORE.index.groups) {
    for (const entry of group.entries) if (entry.exists) order.push(entry.id);
  }
  for (const page of LORE.pages) if (!order.includes(page.id)) order.push(page.id);
  return order;
}

function tagChips(tags) {
  return tags.map(tag => el("button", {
    class: "badge tag", type: "button",
    onclick: () => { window.LORE_QUERY = "tag:" + tag; navigate("#search"); },
  }, tag));
}

function fileLink(href, absolute, label) {
  return el("span", {}, [el("a", { href: href, class: "mono" }, label), copyButton(absolute)]);
}

function frontmatterCard(page) {
  const rows = [
    ["type", el("span", { class: "badge", text: page.type || "—" })],
    ["status", el("span", { class: "badge " + page.status, text: page.status })],
    ["tags", el("span", {}, page.tags.length ? tagChips(page.tags) : [el("span", { class: "muted", text: "none" })])],
    ["generated", el("span", { text: (page.generated.by || "—") + " · " + (page.generated.at || "—") })],
    ["file", fileLink(page.href, page.abs, page.file)],
  ];
  return el("div", { class: "fm-card" }, rows.map(([key, value]) =>
    el("div", { class: "fm-row" }, [el("span", { class: "k", text: key }), value])));
}

function linkList(ids, emptyText) {
  if (!ids.length) return el("p", { class: "empty", text: emptyText });
  return el("ul", { class: "linklist" }, ids.map(id => {
    const page = pageById(id);
    return el("li", {}, [
      page ? pageLink(id) : el("span", { class: "dead", text: id }),
      page ? null : el("span", { class: "muted", text: " — missing page" }),
    ]);
  }));
}

function sourcesList(page) {
  if (!page.sources.length) return el("p", { class: "empty", text: "No sources recorded." });
  return el("ul", { class: "linklist" }, page.sources.map(source => el("li", {}, [
    source.id ? el("code", { text: source.id }) : null,
    source.id ? " " : null,
    source.href
      ? fileLink(source.href + (source.anchor ? "#" + source.anchor : ""), source.abs, source.resource)
      : el("span", { class: "muted", text: "(no resource)" }),
    source.exists ? null : el("span", { class: "dead", text: " — file not found" }),
    source.title ? el("span", { class: "muted", text: " — " + source.title }) : null,
  ])));
}

function renderPage(id) {
  const page = pageById(id);
  if (!page) return el("p", { class: "empty", text: "No page with id " + id });
  const order = indexOrder();
  const at = order.indexOf(page.id);
  const prev = at > 0 ? order[at - 1] : null;
  const next = at >= 0 && at < order.length - 1 ? order[at + 1] : null;
  const issues = offendersFor(page.id);
  return el("article", { class: "page-view" }, [
    el("nav", { class: "prevnext" }, [
      prev ? pageLink(prev, "← " + pageById(prev).title) : el("span", {}),
      next ? pageLink(next, pageById(next).title + " →") : el("span", {}),
    ]),
    el("h2", { text: page.title }),
    el("p", { class: "muted", text: page.description || "" }),
    frontmatterCard(page),
    el("section", { class: "md" }, [renderMarkdown(page.body, page)]),
    el("h3", { text: "Sources" }), sourcesList(page),
    el("h3", { text: "Linked from (" + page.inlinks.length + ")" }),
    linkList(page.inlinks, "No page links here."),
    el("h3", { text: "Links to (" + page.outlinks.length + ")" }),
    linkList(page.outlinks, "This page links nowhere."),
    el("h3", { text: "Health flags" }),
    issues.length
      ? el("ul", { class: "linklist" }, issues.map(issue =>
          el("li", { text: issue.dimension + " · " + issue.check + " — " + issue.detail })))
      : el("p", { class: "empty", text: "No mechanical issues on this page." }),
    (() => {
      const host = el("div", { id: "mini-graph", class: "graph-host mini" });
      requestAnimationFrame(() => initGraph(host, { focus: page.id, hops: 1, height: 220 }));
      return el("div", {}, [el("h3", { text: "Neighbourhood" }), host]);
    })(),
  ]);
}

defineView("page", "Page", renderPage);

function browseEntry(entry) {
  return el("li", {}, [
    entry.exists ? pageLink(entry.id, entry.title) : el("span", { class: "dead", text: entry.title }),
    entry.hook ? el("span", { class: "muted", text: " — " + entry.hook }) : null,
    entry.exists ? null : el("span", { class: "muted", text: " (missing file)" }),
  ]);
}

function renderBrowse() {
  const groups = LORE.index.groups.map(group => el("details", {
    class: "tree", open: !group.deprecated,
  }, [
    el("summary", {}, [
      el("span", { text: group.heading || "(ungrouped)" }),
      el("span", { class: "muted", text: "  " + group.entries.length }),
    ]),
    el("ul", { class: "linklist" }, group.entries.map(browseEntry)),
  ]));
  const orphans = LORE.index.orphans;
  const ghosts = LORE.index.ghost_entries;
  return el("section", {}, [
    el("h2", { text: "index.md — " + LORE.index.entry_count + " entries, "
                     + LORE.index.line_count + " lines" }),
    groups.length ? el("div", {}, groups) : el("p", { class: "empty", text: "The index has no entries." }),
    el("h2", { text: "Not in the index (" + orphans.length + ")" }),
    orphans.length
      ? el("ul", { class: "linklist" }, orphans.map(id => el("li", {}, [pageLink(id)])))
      : el("p", { class: "empty", text: "Every page is indexed." }),
    el("h2", { text: "Ghost entries (" + ghosts.length + ")" }),
    ghosts.length
      ? el("ul", { class: "linklist" }, ghosts.map(entry =>
          el("li", {}, [el("span", { class: "dead", text: entry.title }),
                        el("span", { class: "muted", text: " → " + entry.target })])))
      : el("p", { class: "empty", text: "No index line points at a missing file." }),
  ]);
}

defineView("browse", "Browse", renderBrowse);

const SEARCH_FILTERS = { type: "", status: "", tag: "" };

function filterSelect(key, label, values, onChange) {
  const select = el("select", { "aria-label": label, onchange: event => {
    SEARCH_FILTERS[key] = event.target.value;
    onChange();
  } }, [el("option", { value: "", text: label + ": all" })]);
  for (const value of values) {
    select.append(el("option", { value: value, text: value,
                                 selected: SEARCH_FILTERS[key] === value }));
  }
  return select;
}

function renderSearch() {
  const box = document.getElementById("global-search");
  if (window.LORE_QUERY !== undefined && box.value !== window.LORE_QUERY) {
    box.value = window.LORE_QUERY;
  }
  const query = box.value;
  const types = [...new Set(LORE.pages.map(p => p.type).filter(Boolean))].sort();
  const statuses = [...new Set(LORE.pages.map(p => p.status))].sort();
  const tags = [...new Set(LORE.pages.flatMap(p => p.tags))].sort();
  const rerun = () => route();
  const results = searchPages(query, SEARCH_FILTERS);
  return el("section", {}, [
    el("div", { class: "filters" }, [
      filterSelect("type", "type", types, rerun),
      filterSelect("status", "status", statuses, rerun),
      filterSelect("tag", "tag", tags, rerun),
    ]),
    el("h2", { text: query ? results.length + " result(s) for “" + query + "”"
                           : "Type in the search box above" }),
    el("ul", { class: "results" }, results.map(result => el("li", {}, [
      el("div", {}, [
        pageLink(result.page.id, result.page.title),
        el("span", { class: "badge", text: result.page.type || "—" }),
        el("span", { class: "muted", text: " matched in " + result.field }),
      ]),
      el("div", { class: "muted snippet" }, highlight(result.snippet)),
    ]))),
  ]);
}

defineView("search", "Search", renderSearch);

function offenderNode(offender) {
  const label = offender.ref + (offender.detail ? " — " + offender.detail : "");
  if (offender.kind === "page" && pageById(offender.ref)) {
    return el("li", {}, [pageLink(offender.ref),
                         el("span", { class: "muted", text: " — " + offender.detail })]);
  }
  if (offender.kind === "raw") {
    return el("li", {}, [el("a", { href: "#inbox", text: offender.ref }),
                         el("span", { class: "muted", text: " — " + offender.detail })]);
  }
  return el("li", { class: "muted", text: label });
}

function checkRow(check) {
  return el("details", { class: "check" }, [
    el("summary", {}, [
      el("span", { text: check.label }),
      el("span", { class: "muted", text: "  " + check.offenders.length + " offender(s) · "
                                         + fmtPct(check.score) }),
    ]),
    el("ul", { class: "linklist" }, check.offenders.map(offenderNode)),
  ]);
}

function dimensionCard(dimension) {
  const failing = dimension.checks.filter(check => check.score < 1);
  const clean = dimension.checks.length - failing.length;
  return el("section", { class: "dimension" }, [
    el("div", { class: "dim-head" }, [
      el("strong", { text: dimension.label }),
      el("span", { class: "muted", text: "weight " + dimension.weight }),
      bar(dimension.score, { width: 200 }),
      el("span", { text: fmtPct(dimension.score) }),
    ]),
    failing.length
      ? el("div", {}, failing.map(checkRow))
      : el("p", { class: "empty", text: "All " + dimension.checks.length + " checks clean." }),
    clean && failing.length
      ? el("p", { class: "muted", text: clean + " other check(s) clean." })
      : null,
  ]);
}

function renderHealth() {
  const lint = LORE.health.last_lint;
  return el("section", {}, [
    el("div", { class: "score" }, [
      el("div", { class: "score-n", text: String(LORE.health.score) }),
      el("div", { class: "muted", text: "/ 100 — mechanical health" }),
      bar(LORE.health.score / 100, { width: 260, height: 10 }),
    ]),
    el("div", {}, LORE.health.dimensions.map(dimensionCard)),
    el("h2", { text: "Judgment checks (not scored)" }),
    el("p", { class: "muted", text: lint
      ? "Last lint " + lint.date + " (" + lint.days + " days ago): "
        + lint.fixed + " fixed, " + lint.reported + " reported."
      : "No lint entry in log.md yet — run /lore:lore-lint." }),
    el("p", { class: "muted", text:
      "Active contradiction cross-check, footnote-discipline judgment, missing concept pages, "
      + "missing cross-references, knowledge gaps and discard candidates need the agent; "
      + "they are never computed here." }),
  ]);
}

defineView("health", "Health", renderHealth);

function countTable(title, rows, options) {
  const opts = options || {};
  if (!rows.length) return el("div", {}, [el("h3", { text: title }),
                                          el("p", { class: "empty", text: "Nothing to show." })]);
  const max = Math.max(...rows.map(row => row.count));
  const body = rows.map(row => el("tr", {}, [
    el("td", {}, opts.chip ? [el("button", {
      class: "badge tag", type: "button",
      onclick: () => { window.LORE_QUERY = "tag:" + row.key; navigate("#search"); },
    }, row.key)] : [el("span", { text: row.key })]),
    el("td", { text: String(row.count) }),
    el("td", {}, [bar(row.count / max, { width: 120, color: "var(--accent)" })]),
    opts.bytes ? el("td", { text: fmtBytes(row.bytes || 0) }) : null,
  ].filter(Boolean)));
  const headers = ["", "count", ""].concat(opts.bytes ? ["size"] : []);
  return el("div", {}, [
    el("h3", { text: title }),
    el("table", {}, [el("thead", {}, el("tr", {}, headers.map(h => el("th", { text: h })))),
                     el("tbody", {}, body)]),
  ]);
}

function renderStats() {
  const stats = LORE.stats;
  const coverage = stats.coverage;
  const graph = stats.graph;
  return el("section", {}, [
    el("h2", { text: "Pages" }),
    countTable("By type", stats.pages_by_type),
    countTable("By status", stats.pages_by_status),
    countTable("By generator", stats.pages_by_generator),
    el("h2", { text: "Inbox" }),
    countTable("By extension", stats.raw_by_ext, { bytes: true }),
    countTable("By state", stats.raw_by_state),
    el("p", { class: "muted", text: "Total raw bytes: " + fmtBytes(stats.raw_total_bytes) }),
    el("h2", { text: "Sources coverage" }),
    el("p", {}, [el("span", { text: coverage.raw_with_pages + " raw file(s) feed at least one page; " }),
                 el("span", { class: coverage.raw_without_pages ? "dead" : "muted",
                              text: coverage.raw_without_pages + " feed none." })]),
    countTable("Pages per raw file (top 10)",
               coverage.pages_per_raw.map(row => ({ key: row.file, count: row.count }))),
    coverage.uncited.length
      ? el("p", { class: "muted", text: "Uncited: " + coverage.uncited.join(", ") })
      : null,
    el("h2", { text: "Graph" }),
    el("div", { class: "cards" }, [
      ["Nodes", graph.nodes], ["Pages", graph.pages], ["Missing", graph.ghosts],
      ["Edges", graph.edges], ["Avg degree", graph.avg_degree], ["Components", graph.components],
    ].map(([label, value]) => el("div", { class: "card" }, [
      el("div", { class: "n", text: String(value) }), el("div", { class: "k", text: label })]))),
    countTable("Top hubs by inbound links",
               graph.hubs.map(hub => ({ key: hub.title, count: hub.count }))),
    el("h2", { text: "Tags" }),
    countTable("By tag", stats.tags, { chip: true }),
    stats.untagged.length
      ? el("p", { class: "muted", text: "Untagged pages: " + stats.untagged.join(", ") })
      : el("p", { class: "muted", text: "Every page is tagged." }),
    el("h2", { text: "Log" }),
    countTable("Entries by verb", stats.log.by_verb),
    countTable("Ingests per week",
               stats.log.ingests_per_week.map(row => ({ key: row.week, count: row.count }))),
    el("p", { class: "muted", text: stats.log.answers + " answer(s) promoted · "
                                    + stats.log.discards + " discard(s) · "
                                    + stats.log.malformed + " malformed line(s)" }),
  ]);
}

defineView("stats", "Stats", renderStats);

const LOG_FILTERS = { verb: "", from: "", to: "", text: "" };

function subjectNode(entry) {
  const asPage = pageById(entry.subject.replace(/ /g, "_"));
  if (asPage) return pageLink(asPage.id, entry.subject);
  const raw = LORE.raw.find(record => record.name.split("/").pop() === entry.subject);
  if (raw) return el("a", { href: raw.href, class: "mono" }, entry.subject);
  return el("span", { text: entry.subject });
}

const LOG_COLUMNS = ["date", "verb", "subject", "detail"];

function logHead() {
  return el("thead", {}, el("tr", {}, LOG_COLUMNS.map(h => el("th", { text: h }))));
}

function logRows(entries) {
  return entries.map(entry => el("tr", {}, [
    el("td", { class: "mono", text: entry.date }),
    el("td", {}, [el("span", { class: "badge", text: entry.verb })]),
    el("td", {}, [subjectNode(entry)]),
    el("td", { class: "muted", text: entry.detail }),
  ]));
}

function renderLog() {
  const verbs = [...new Set(LORE.log.entries.map(entry => entry.verb))].sort();
  // Only the count heading and the results <tbody> depend on the filters, so
  // a filter change re-renders exactly those two nodes in place. Calling
  // route() instead — which is what every other filtered view does — would
  // clear(main) and rebuild this whole view, replacing the very <input>
  // being typed into: the browser blurs a node it removes, so the free-text
  // box lost focus and its caret after every single keystroke.
  const heading = el("h2");
  const tbody = el("tbody");
  function refresh() {
    const needle = LOG_FILTERS.text.toLowerCase();
    // LORE.log.entries is the payload's own array — .filter() below returns
    // a new array and leaves it untouched, so re-filtering never mutates the
    // newest-first order every other view relies on.
    const entries = LORE.log.entries.filter(entry =>
      (!LOG_FILTERS.verb || entry.verb === LOG_FILTERS.verb)
      && (!LOG_FILTERS.from || entry.date >= LOG_FILTERS.from)
      && (!LOG_FILTERS.to || entry.date <= LOG_FILTERS.to)
      && (!needle || (entry.subject + " " + entry.detail).toLowerCase().includes(needle)));
    heading.textContent = entries.length + " of " + LORE.log.entries.length + " entries";
    clear(tbody);
    for (const row of logRows(entries)) tbody.append(row);
  }

  const verbSelect = el("select", { onchange: event => { LOG_FILTERS.verb = event.target.value; refresh(); } },
    [el("option", { value: "", text: "verb: all" })].concat(verbs.map(verb =>
      el("option", { value: verb, text: verb, selected: LOG_FILTERS.verb === verb }))));
  const from = el("input", { type: "date", value: LOG_FILTERS.from, "aria-label": "from",
                             onchange: event => { LOG_FILTERS.from = event.target.value; refresh(); } });
  const to = el("input", { type: "date", value: LOG_FILTERS.to, "aria-label": "to",
                           onchange: event => { LOG_FILTERS.to = event.target.value; refresh(); } });
  const text = el("input", { type: "search", value: LOG_FILTERS.text, placeholder: "filter text",
                             oninput: event => { LOG_FILTERS.text = event.target.value; refresh(); } });
  refresh();

  // ingest/skip headings are log.md's ledger convention (see the lore
  // schema doc): only those two verbs carry a raw/ filename as their
  // subject, so only they belong in the per-file ledger below.
  const ledger = new Map();
  for (const entry of LORE.log.entries) {
    if (entry.verb !== "ingest" && entry.verb !== "skip") continue;
    if (!ledger.has(entry.subject)) ledger.set(entry.subject, []);
    ledger.get(entry.subject).push(entry);
  }

  return el("section", {}, [
    el("div", { class: "filters" }, [verbSelect, from, to, text]),
    heading,
    el("table", {}, [logHead(), tbody]),
    el("h2", { text: "Malformed lines (" + LORE.log.malformed.length + ")" }),
    LORE.log.malformed.length
      ? el("ul", { class: "linklist" }, LORE.log.malformed.map(bad =>
          el("li", { class: "mono dead", text: "log.md:" + bad.line + "  " + bad.text })))
      : el("p", { class: "empty", text: "Every heading parses." }),
    el("h2", { text: "Per-file ledger" }),
    ledger.size
      // LORE.log.entries is newest-first, so entries pushed above while
      // scanning it in order are newest-first too, per subject; reverse a
      // *copy* (items is this loop's own array, never the payload's) to get
      // the oldest-first order the ledger convention calls for.
      ? el("div", {}, [...ledger.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(
          ([name, items]) => el("details", { class: "tree" }, [
            el("summary", {}, [el("span", { class: "mono", text: name }),
                               el("span", { class: "muted", text: "  " + items.length + " entry(ies)" })]),
            el("table", {}, [logHead(), el("tbody", {}, logRows([...items].reverse()))]),
          ])))
      : el("p", { class: "empty", text: "No ingest or skip entries yet." }),
  ]);
}

defineView("log", "Log", renderLog);

function renderInbox() {
  const counts = {};
  for (const record of LORE.raw) counts[record.state] = (counts[record.state] || 0) + 1;
  const summary = ["NEW", "CHANGED", "SKIPPED", "PROCESSED"]
    .filter(state => counts[state])
    .map(state => counts[state] + " " + state).join(" · ") || "empty";
  return el("section", {}, [
    el("h2", { text: "raw/ — " + LORE.raw.length + " file(s): " + summary }),
    // LORE.raw already sorts NEW and CHANGED first (lore_dashboard_parse.py)
    // — render it as-is, no client-side re-sort.
    LORE.raw.length ? el("table", {}, [
      el("thead", {}, el("tr", {}, ["file", "ext", "size", "state", "latest", "pages", "note"]
        .map(h => el("th", { text: h })))),
      el("tbody", {}, LORE.raw.map(record => el("tr", {}, [
        el("td", {}, [el("a", { href: record.href, class: "mono" }, record.name),
                      copyButton(record.abs)]),
        el("td", { class: "muted", text: record.ext || "—" }),
        el("td", { text: fmtBytes(record.size) }),
        el("td", {}, [el("span", { class: "badge " + record.state, text: record.state })]),
        el("td", { class: "mono muted", text: record.latest_date || "—" }),
        el("td", {}, record.pages.length
          ? record.pages.map((id, at) => el("span", {}, [at ? ", " : "", pageLink(id)]))
          : [el("span", { class: "muted", text: "none" })]),
        el("td", { class: "muted", text: record.skip_reason || "" }),
      ]))),
    ]) : el("p", { class: "empty", text: "raw/ is empty." }),
  ]);
}

defineView("inbox", "Inbox", renderInbox);

function renderGraph() {
  const host = el("div", { class: "graph-host" });
  const types = [...new Set(LORE.graph.nodes.map(n => n.type))].sort();
  const statuses = [...new Set(LORE.graph.nodes.map(n => n.status).filter(Boolean))].sort();
  const tags = [...new Set(LORE.graph.nodes.flatMap(n => n.tags || []))].sort();
  let graph = null;
  const set = (key, value) => { if (graph) { graph.state[key] = value; graph.apply(); } };
  const controls = el("div", { class: "filters graph-controls" }, [
    el("select", { onchange: e => set("type", e.target.value) },
      [el("option", { value: "", text: "type: all" })].concat(
        types.map(t => el("option", { value: t, text: t })))),
    el("select", { onchange: e => set("status", e.target.value) },
      [el("option", { value: "", text: "status: all" })].concat(
        statuses.map(s => el("option", { value: s, text: s })))),
    el("select", { onchange: e => set("tag", e.target.value) },
      [el("option", { value: "", text: "tag: all" })].concat(
        tags.map(t => el("option", { value: t, text: t })))),
    el("label", {}, [
      el("input", { type: "checkbox", checked: true,
                    onchange: e => set("hideDeprecated", e.target.checked) }),
      " hide deprecated"]),
    el("input", { type: "search", placeholder: "dim non-matching",
                  oninput: e => set("query", e.target.value) }),
    el("label", {}, [
      el("input", { type: "checkbox", onchange: e => set("focusMode", e.target.checked) }),
      " focus on click"]),
    el("select", { onchange: e => set("hops", Number(e.target.value)) },
      [1, 2, 3].map(n => el("option", { value: n, text: n + " hop(s)" }))),
    el("button", { type: "button", onclick: () => { set("focus", null); } }, "clear focus"),
  ]);
  requestAnimationFrame(() => {
    graph = initGraph(host, { height: Math.max(420, window.innerHeight - 220) });
  });
  return el("section", { class: "graph-section" }, [
    controls,
    host,
    el("p", { class: "muted", text: "drag nodes · drag background to pan · wheel to zoom · "
                                    + "click a node to open its page" }),
  ]);
}

defineView("graph", "Graph", renderGraph);
