// app.js — header, tab chrome, hash routing, global search box. Loaded last.
defineView("overview", "Overview", () => {
  const counts = LORE.meta.counts;
  const cards = [
    ["Health", LORE.health.score, "/ 100"],
    ["Pages", counts.pages, ""],
    ["Wikilinks", counts.edges, ""],
    ["Missing targets", counts.ghosts, ""],
    ["Raw files", counts.raw, ""],
  ].map(([label, value, suffix]) =>
    el("div", { class: "card" }, [
      el("div", { class: "n", text: String(value) + (suffix ? " " : "") }),
      el("div", { class: "k", text: label + (suffix ? " " + suffix : "") }),
    ]));
  const lint = LORE.health.last_lint;
  const lintLine = lint
    ? `Last lint ${lint.date} (${lint.days} days ago): ${lint.fixed} fixed, ${lint.reported} reported.`
    : "No lint entry in log.md yet.";
  return el("section", {}, [
    el("h2", { text: "At a glance" }),
    el("div", { class: "cards" }, cards),
    el("h2", { text: "Judgment checks" }),
    el("p", { class: "muted", text: lintLine }),
    el("p", { class: "muted", text:
      "Judgment-only lint checks (contradiction cross-check, missing concept pages, "
      + "cross-references, knowledge gaps, discard candidates) are not scored here — "
      + "run /lore:lore-lint for those." }),
  ]);
});

function renderHeader() {
  document.getElementById("lore-name").textContent = LORE.meta.lore_name;
  const git = LORE.meta.git;
  const gitText = git.repo
    ? `git ${git.head}${git.dirty ? " (dirty)" : ""}`
    : "not a repo";
  const meta = document.getElementById("lore-meta");
  clear(meta).append(
    el("span", { class: "mono", text: LORE.meta.lore_path }),
    copyButton(LORE.meta.lore_path),
    el("span", { text: " · generated " + LORE.meta.generated_at + " · " + gitText }));
}

function renderTabs(active) {
  const nav = clear(document.getElementById("tabs"));
  for (const key of TAB_ORDER) {
    const view = VIEWS[key];
    if (!view) continue;
    nav.append(el("button", {
      type: "button", "aria-current": key === active ? "true" : null,
      text: view.label, onclick: () => navigate("#" + key),
    }));
  }
}

function route() {
  const hash = (window.location.hash || "#overview").slice(1);
  const [key, ...rest] = hash.split("/");
  const arg = rest.length ? decodeURIComponent(rest.join("/")) : null;
  const view = VIEWS[key] || (key === "page" ? VIEWS.page : null) || VIEWS.overview;
  const main = document.getElementById("view");
  main.classList.toggle("wide", key === "graph");
  clear(main).append(view.render(arg) || el("p", { class: "empty", text: "Nothing to show." }));
  renderTabs(key === "page" ? "browse" : key);
  window.scrollTo(0, 0);
}

function boot() {
  renderHeader();
  const search = document.getElementById("global-search");
  search.addEventListener("input", () => {
    if (!VIEWS.search) return;
    window.LORE_QUERY = search.value;
    if (!window.location.hash.startsWith("#search")) navigate("#search");
    else route();
  });
  document.getElementById("random-page").addEventListener("click", () => {
    if (!LORE.pages.length) return;
    const page = LORE.pages[Math.floor(Math.random() * LORE.pages.length)];
    navigate("#page/" + encodeURIComponent(page.id));
  });
  window.addEventListener("hashchange", route);
  route();
}

boot();
