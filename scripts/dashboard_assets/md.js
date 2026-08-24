// md.js — small markdown renderer for lore wiki pages. DOM building only —
// no raw-HTML string injection, ever.
// Page bodies are untrusted content (agent- or human-authored, never sanitized
// upstream): every node here is built with el()/textContent, and any href that
// comes straight from the markdown text is passed through safeHref() first so
// a `javascript:`/`vbscript:` link can never execute on click.
const INLINE_SPLIT_RE = /(`[^`]+`|\[\[[^\]]+\]\]|\[\^[^\]]+\]|\[[^\]]*\]\([^)\s]+\)|\*\*[^*]+\*\*|\*[^*]+\*)/;
const HEADING_RE = /^(#{1,6})\s+(.*)$/;
const LIST_RE = /^(\s*)(?:([-*+])|(\d+)\.)\s+(.*)$/;
const FENCE_RE = /^```(.*)$/;
const TABLE_SEP_RE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const CONTRADICTION_LINE_RE = /^>\s*⚠\s*CONTRADICTION/;
const MY_TAKE_HEADING_RE = /^##+\s*My Take\s*$/i;
const UNSAFE_HREF_SCHEME_RE = /^(?:javascript|vbscript):/i;

// Blocks script-executing URI schemes (javascript:, vbscript:) in links that
// come straight from page text — including whitespace/control-char tricks
// like "java\tscript:" — by stripping those characters before the scheme
// check. Returns null (a non-link) for anything unsafe.
function safeHref(href) {
  const stripped = String(href).replace(/[\s\u0000-\u001f]+/g, "");
  return UNSAFE_HREF_SCHEME_RE.test(stripped) ? null : href;
}

function wikiLinkNode(raw, page) {
  const [targetPart, alias] = raw.split("|");
  const target = targetPart.split("#")[0].trim().replace(/ /g, "_");
  const exists = !!pageById(target);
  return el("a", {
    href: "#page/" + encodeURIComponent(target),
    class: exists ? "wikilink" : "wikilink dead",
    title: exists ? null : "no page named " + target,
  }, (alias || targetPart).trim());
}

function footnoteNode(id, page) {
  const source = (page && page.sources || []).find(s => s.id === id);
  const known = !!source;
  return el("sup", { class: known ? "fn" : "fn dead" }, [
    el("a", {
      href: known && source.href ? source.href : "#page/" + encodeURIComponent(page ? page.id : ""),
      title: known ? source.resource : "no sources[] entry with id " + id,
    }, id),
  ]);
}

function renderInline(text, page) {
  const nodes = [];
  for (const chunk of String(text).split(INLINE_SPLIT_RE)) {
    if (!chunk) continue;
    if (chunk.startsWith("`") && chunk.endsWith("`")) {
      nodes.push(el("code", { text: chunk.slice(1, -1) }));
    } else if (chunk.startsWith("[[")) {
      nodes.push(wikiLinkNode(chunk.slice(2, -2), page));
    } else if (chunk.startsWith("[^")) {
      nodes.push(footnoteNode(chunk.slice(2, -1), page));
    } else if (chunk.startsWith("[")) {
      const split = chunk.indexOf("](");
      const label = chunk.slice(1, split);
      const href = chunk.slice(split + 2, -1);
      nodes.push(el("a", { href: safeHref(href), rel: "noreferrer" }, label));
    } else if (chunk.startsWith("**")) {
      nodes.push(el("strong", { text: chunk.slice(2, -2) }));
    } else if (chunk.startsWith("*")) {
      nodes.push(el("em", { text: chunk.slice(1, -1) }));
    } else {
      nodes.push(document.createTextNode(chunk));
    }
  }
  return nodes;
}

function renderTable(rows, page) {
  const cells = row => row.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map(c => c.trim());
  const head = el("tr", {}, cells(rows[0]).map(c => el("th", {}, renderInline(c, page))));
  const body = rows.slice(2).map(row => el("tr", {}, cells(row).map(
    c => el("td", {}, renderInline(c, page)))));
  return el("table", {}, [el("thead", {}, head), el("tbody", {}, body)]);
}

function renderMarkdown(text, page) {
  const fragment = document.createDocumentFragment();
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  let target = fragment;                       // switches to the My Take container
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const fence = line.match(FENCE_RE);
    if (fence) {
      const body = [];
      i++;
      while (i < lines.length && !FENCE_RE.test(lines[i])) body.push(lines[i++]);
      i++;
      target.append(el("pre", { "data-lang": fence[1].trim() || null },
                       [el("code", { text: body.join("\n") })]));
      continue;
    }

    const heading = line.match(HEADING_RE);
    if (heading) {
      if (MY_TAKE_HEADING_RE.test(line)) {
        const box = el("section", { class: "my-take" },
                       [el("h3", { text: "My Take" }),
                        el("p", { class: "muted", text: "human-owned — the agent never edits this" })]);
        fragment.append(box);
        target = box;
      } else {
        target.append(el("h" + Math.min(heading[1].length + 1, 6), {},
                         renderInline(heading[2], page)));
      }
      i++;
      continue;
    }

    if (line.startsWith(">")) {
      const quoted = [];
      const contradiction = CONTRADICTION_LINE_RE.test(line);
      while (i < lines.length && lines[i].startsWith(">")) {
        quoted.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      const text = quoted.join(" ").replace(/^⚠\s*/, "");
      target.append(el(contradiction ? "div" : "blockquote",
                       { class: contradiction ? "callout contradiction" : null },
                       contradiction
                         ? [el("strong", { text: "⚠ " }), ...renderInline(text, page)]
                         : renderInline(text, page)));
      continue;
    }

    if (line.includes("|") && i + 1 < lines.length && TABLE_SEP_RE.test(lines[i + 1])) {
      const rows = [];
      while (i < lines.length && lines[i].includes("|")) rows.push(lines[i++]);
      target.append(renderTable(rows, page));
      continue;
    }

    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { target.append(el("hr")); i++; continue; }

    const list = line.match(LIST_RE);
    if (list) {
      const ordered = !list[2];
      const root = el(ordered ? "ol" : "ul");
      let lastItem = null, nested = null;
      while (i < lines.length) {
        const match = lines[i].match(LIST_RE);
        if (!match) break;
        const item = el("li", {}, renderInline(match[4], page));
        if (match[1].length >= 2 && lastItem) {
          nested = nested || lastItem.appendChild(el(ordered ? "ol" : "ul"));
          nested.append(item);
        } else {
          root.append(item);
          lastItem = item;
          nested = null;
        }
        i++;
      }
      target.append(root);
      continue;
    }

    const paragraph = [];
    while (i < lines.length && lines[i].trim() && !HEADING_RE.test(lines[i])
           && !lines[i].startsWith(">") && !LIST_RE.test(lines[i]) && !FENCE_RE.test(lines[i])) {
      paragraph.push(lines[i++]);
    }
    target.append(el("p", {}, renderInline(paragraph.join(" "), page)));
  }
  return fragment;
}
