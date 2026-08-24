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
