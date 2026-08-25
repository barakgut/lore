// search.js — linear AND-match search over the inlined pages. No index, no regex.
const FIELD_WEIGHTS = { title: 8, tags: 4, description: 2, body: 1 };
const SNIPPET_PAD = 60;

function fieldText(page, field) {
  return field === "tags" ? page.tags.join(" ") : String(page[field] || "");
}

function scoreTerm(page, term) {
  if (term.startsWith("tag:")) {
    const wanted = term.slice(4);
    return page.tags.some(tag => tag.toLowerCase().includes(wanted)) ? FIELD_WEIGHTS.tags : 0;
  }
  let best = 0, where = null;
  for (const field of Object.keys(FIELD_WEIGHTS)) {
    if (fieldText(page, field).toLowerCase().includes(term)) {
      if (FIELD_WEIGHTS[field] > best) { best = FIELD_WEIGHTS[field]; where = field; }
    }
  }
  return best ? { score: best, field: where } : 0;
}

function snippetFor(page, terms) {
  const body = String(page.body || "");
  const lower = body.toLowerCase();
  const plain = terms.filter(term => !term.startsWith("tag:"));
  let at = -1, hit = "";
  for (const term of plain) {
    const found = lower.indexOf(term);
    if (found !== -1 && (at === -1 || found < at)) { at = found; hit = term; }
  }
  if (at === -1) return { text: page.description || "", terms: plain };
  const start = Math.max(0, at - SNIPPET_PAD);
  const end = Math.min(body.length, at + hit.length + SNIPPET_PAD);
  return { text: (start ? "…" : "") + body.slice(start, end).replace(/\n+/g, " ") +
                 (end < body.length ? "…" : ""), terms: plain };
}

function searchPages(query, filters) {
  const terms = String(query || "").toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return [];
  const chosen = filters || {};
  const results = [];
  for (const page of LORE.pages) {
    if (chosen.type && page.type !== chosen.type) continue;
    if (chosen.status && page.status !== chosen.status) continue;
    if (chosen.tag && !page.tags.includes(chosen.tag)) continue;
    let total = 0, field = null, matchedAll = true;
    for (const term of terms) {
      const hit = scoreTerm(page, term);
      if (!hit) { matchedAll = false; break; }
      total += hit.score || hit;
      if (!field && hit.field) field = hit.field;
    }
    if (!matchedAll) continue;
    results.push({ page, score: total, field: field || "tags", snippet: snippetFor(page, terms) });
  }
  results.sort((a, b) => b.score - a.score || a.page.title.localeCompare(b.page.title));
  return results;
}

function highlight(snippet) {
  const nodes = [];
  const pattern = snippet.terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  if (!pattern) return [document.createTextNode(snippet.text)];
  const splitter = new RegExp("(" + pattern + ")", "ig");
  for (const chunk of snippet.text.split(splitter)) {
    if (!chunk) continue;
    if (splitter.test(chunk) || snippet.terms.includes(chunk.toLowerCase())) {
      nodes.push(el("mark", { text: chunk }));
    } else {
      nodes.push(document.createTextNode(chunk));
    }
    splitter.lastIndex = 0;
  }
  return nodes;
}
