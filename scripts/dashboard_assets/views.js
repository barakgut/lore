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
    el("div", { id: "mini-graph" }),
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
