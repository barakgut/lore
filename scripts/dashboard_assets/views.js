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
