"""Tests for lore_dashboard_html.py — run with: python3 -m unittest discover scripts"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lore_dashboard_html import ASSETS_DIR, CSS_ASSETS, JS_ASSETS, build_html, encode_payload

PAYLOAD = {
    "meta": {"lore_name": "my-lore", "lore_path": "/home/u/lore",
             "generated_at": "2026-08-24 14:03",
             "git": {"repo": True, "head": "7f38be5", "dirty": False},
             "links": {"lore": "..", "wiki": "../wiki", "raw": "../raw"},
             "counts": {"pages": 1, "ghosts": 0, "edges": 0, "raw": 0}},
    "pages": [{"id": "A", "title": "A", "type": "concept", "status": "stable",
               "description": "d", "tags": [], "sources": [], "generated": {"by": "", "at": ""},
               "body": "text", "outlinks": [], "inlinks": [], "index_group": None,
               "index_hook": None, "footnote_ids": [], "contradictions": 0,
               "my_take": False, "fm_ok": True, "href": "../wiki/A.md", "abs": "/home/u/lore/wiki/A.md"}],
    "graph": {"nodes": [], "edges": [], "components": 0, "isolated": []},
    "index": {"line_count": 3, "entry_count": 1, "groups": [], "orphans": [],
              "ghost_entries": [], "over_cap": [], "misplaced_deprecated": []},
    "log": {"entries": [], "malformed": [], "last_lint": None},
    "raw": [],
    "health": {"score": 100, "dimensions": [], "last_lint": None},
    "stats": {},
}


class TestEncodePayload(unittest.TestCase):
    def test_round_trips_through_json(self):
        self.assertEqual(json.loads(encode_payload(PAYLOAD))["meta"]["lore_name"], "my-lore")

    def test_no_raw_angle_bracket_survives(self):
        payload = dict(PAYLOAD)
        payload["pages"] = [dict(PAYLOAD["pages"][0], body="</script><img src=x>")]
        encoded = encode_payload(payload)
        self.assertNotIn("<", encoded)
        self.assertIn("</script>", json.loads(encoded)["pages"][0]["body"])

    def test_unicode_is_kept_literal(self):
        payload = dict(PAYLOAD)
        payload["pages"] = [dict(PAYLOAD["pages"][0], body="> ⚠ CONTRADICTION: x")]
        self.assertIn("⚠", encode_payload(payload))


class TestBuildHtml(unittest.TestCase):
    def test_title_and_payload_are_embedded(self):
        page = build_html(PAYLOAD)
        self.assertIn("<title>my-lore — lore dashboard</title>", page)
        self.assertIn('id="lore-data"', page)
        self.assertIn('"lore_name":"my-lore"', page)

    def test_every_manifest_asset_is_inlined(self):
        page = build_html(PAYLOAD)
        for name in CSS_ASSETS + JS_ASSETS:
            marker = (ASSETS_DIR / name).read_text(encoding="utf-8").strip().split("\n")[0]
            self.assertIn(marker, page, f"{name} not inlined")

    def test_no_placeholder_is_left_behind(self):
        self.assertIsNone(re.search(r"__(TITLE|STYLE|SCRIPT|DATA)__", build_html(PAYLOAD)))

    def test_output_is_self_contained(self):
        page = build_html(PAYLOAD)
        # This invariant is about ASSETS: no CDN script, no web font, no
        # remote resource of any kind — the page must render with the network
        # switched off. It is NOT about the payload text. A lore whose page
        # body, description or sources[] contains an ordinary https:// link
        # legitimately produces a page containing "https://", and stripping
        # those would be destroying the user's own content, not fixing a
        # self-containment leak. PAYLOAD above deliberately carries no such
        # link so the blunt substring check below can stand in for the real
        # rule; if a future payload needs one, narrow the check to the
        # <head>/asset region rather than sanitising the data.
        # The SVG namespace identifier ("http://www.w3.org/2000/svg", required
        # by document.createElementNS in core.js's svgEl helper) is the one
        # "http://" string allowed anywhere in the build — it is an XML
        # namespace name, never fetched. Every other occurrence of "http://"
        # would be a real reference the self-contained build must not have,
        # so count them against each other instead of just asserting absence.
        self.assertEqual(page.count("http://www.w3.org/2000/svg"), page.count("http://"))
        self.assertNotIn("https://", page)
        self.assertNotIn("<link", page)

    def test_missing_asset_raises(self):
        empty = Path(tempfile.mkdtemp())
        with self.assertRaises(FileNotFoundError):
            build_html(PAYLOAD, assets_dir=empty)

    def test_injection_hazard_survives_single_pass_substitution(self):
        # A page body containing literal placeholder tokens, a script-closing
        # tag, and a raw angle bracket must not corrupt the build: the real
        # __SCRIPT__/__DATA__ slots must still be filled from the assets
        # (not re-scanned out of the payload), the lore-data block must
        # remain intact HTML, and the payload must round-trip unchanged.
        hazard = "__SCRIPT__ __DATA__ </script> <b>raw</b>"
        payload = dict(PAYLOAD)
        payload["pages"] = [dict(PAYLOAD["pages"][0], body=hazard)]
        page = build_html(payload)

        match = re.search(
            r'<script id="lore-data" type="application/json">(.*?)</script>',
            page, re.S)
        self.assertIsNotNone(match, "lore-data script block not found intact")
        blob = match.group(1)

        # No raw '<' inside the data blob — that's what would let
        # "</script>" in the payload prematurely close the tag.
        self.assertNotIn("<", blob)

        # The payload round-trips exactly: the hazard text was inserted
        # verbatim, never re-scanned as a template placeholder.
        data = json.loads(blob)
        self.assertEqual(data["pages"][0]["body"], hazard)

        # The real script/style content still landed at its own slot.
        self.assertIn("function boot()", page)
        self.assertIn(":root {", page)

    def test_hostile_lore_name_is_html_escaped_in_title(self):
        # lore_name is payload-derived (Task 7 populates it from a directory
        # basename, which is not restricted to HTML-safe characters) and it
        # lands inside <title>__TITLE__</title>. A hostile basename must not
        # be able to close the title element and inject markup into <head>.
        payload = dict(PAYLOAD)
        payload["meta"] = dict(
            PAYLOAD["meta"], lore_name="evil</title><script>alert(1)</script>")
        page = build_html(payload)

        # The raw, unescaped hazard must not survive anywhere in the page.
        self.assertNotIn("</title><script>alert(1)</script>", page)
        self.assertNotIn("<script>alert(1)</script>", page)

        # The <title> element is escaped and still closes exactly where it
        # should — pinned literally so the test fails if escaping is removed.
        expected_title = (
            "<title>evil&lt;/title&gt;&lt;script&gt;alert(1)&lt;/script&gt;"
            " — lore dashboard</title>"
        )
        self.assertIn(expected_title, page)


# safeHref(href) -> href | null. Pairs of (input, expected output). None means
# "blocked" (the link must render with no href at all); anything else means
# the href must survive untouched. safeHref is a pure string function, so
# these are executed for real in node rather than grepped out of the source —
# a case-sensitive guard, or one that skips control-char stripping, or one
# that forgets a dangerous scheme, changes these results.
SAFE_HREF_CASES = [
    # blocked: script-executing / data-smuggling schemes, including the
    # normalisation-defeating tricks the guard claims to handle
    ("javascript:alert(1)", None),
    ("JaVaScRiPt:alert(1)", None),
    ("java\tscript:alert(1)", None),
    ("\njavascript:alert(1)", None),
    (" javascript:alert(1)", None),
    ("\x00javascript:alert(1)", None),
    ("data:text/html,<script>alert(1)</script>", None),
    ("data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==", None),
    ("blob:http://example.com/uuid", None),
    # blocked: protocol-relative URLs. They carry no scheme of their own, so
    # the scheme allowlist never sees them, but they are not relative paths
    # either — they inherit the page's scheme and reach a remote host.
    ("//evil.example.com/p.pdf", None),
    (" //evil.example.com/p.pdf", None),
    ("/\t/evil.example.com/p.pdf", None),
    # allowed: what a real lore page actually links to
    ("../wiki/Some_Page.md", "../wiki/Some_Page.md"),
    ("raw/spec.pdf", "raw/spec.pdf"),
    ("/absolute/path.md", "/absolute/path.md"),   # one slash is a path, two is a host
    ("#page/Some_Page", "#page/Some_Page"),
    ("https://example.com", "https://example.com"),
    ("mailto:someone@example.com", "mailto:someone@example.com"),
]

# Loads md.js in node (safeHref has no DOM dependency — it never touches
# document/el/pageById) and calls the real function against SAFE_HREF_CASES.
SAFE_HREF_RUNNER_JS = """
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
(0, eval)(src);
const inputs = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
process.stdout.write(JSON.stringify(inputs.map(safeHref)));
"""


@unittest.skipUnless(shutil.which("node"), "node not installed — JS syntax check skipped")
class TestJsSyntax(unittest.TestCase):
    def test_every_js_asset_parses(self):
        for name in JS_ASSETS:
            result = subprocess.run(["node", "--check", str(ASSETS_DIR / name)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")

    def test_safe_href_blocks_dangerous_schemes_and_allows_real_links(self):
        inputs = [href for href, _ in SAFE_HREF_CASES]
        expected = [want for _, want in SAFE_HREF_CASES]
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "run_safe_href.js"
            cases = Path(tmp) / "cases.json"
            runner.write_text(SAFE_HREF_RUNNER_JS, encoding="utf-8")
            cases.write_text(json.dumps(inputs), encoding="utf-8")
            result = subprocess.run(
                ["node", str(runner), str(ASSETS_DIR / "md.js"), str(cases)],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(result.stdout)
        for href, want, got in zip(inputs, expected, actual):
            self.assertEqual(got, want, f"safeHref({href!r}) -> {got!r}, expected {want!r}")


class TestPageViewAssets(unittest.TestCase):
    def test_markdown_and_view_assets_are_in_the_manifest_in_order(self):
        self.assertEqual(JS_ASSETS.index("core.js"), 0)
        self.assertLess(JS_ASSETS.index("md.js"), JS_ASSETS.index("views.js"))
        self.assertEqual(JS_ASSETS[-1], "app.js")

    def test_page_view_styles_ship_in_the_stylesheet(self):
        css = (ASSETS_DIR / "app.css").read_text(encoding="utf-8")
        for selector in [".callout", ".my-take", ".fm-card", ".dead", "sup.fn"]:
            self.assertIn(selector, css)

    def test_renderer_never_emits_document_write_or_inner_html_of_page_text(self):
        source = (ASSETS_DIR / "md.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", source)      # DOM building only — page text is untrusted
        self.assertNotIn("document.write", source)

    def test_no_asset_uses_innerhtml_outerhtml_document_write_or_eval(self):
        # Global constraint (not just md.js): page bodies are untrusted
        # content, and every node — including the search snippet's
        # highlighted terms — must be built via el()/textContent — never
        # through string-based HTML injection or eval, in any file that
        # renders untrusted content.
        for name in ("md.js", "views.js", "search.js"):
            source = (ASSETS_DIR / name).read_text(encoding="utf-8")
            for hazard in ("innerHTML", "outerHTML", "document.write", "eval("):
                self.assertNotIn(hazard, source, f"{name} contains {hazard}")

    def test_markdown_links_sanitize_javascript_scheme_hrefs(self):
        # The brief's reference renderer wired a markdown `[text](href)`
        # link's href straight into the DOM (`href: href`), so a page
        # body containing `[x](javascript:alert(1))` produced a live,
        # clickable javascript: URI — exactly the raw-HTML/script
        # injection this renderer exists to prevent (a page body is
        # untrusted content). A sanitizer must sit between the parsed
        # href and the DOM and must actually name the scheme it blocks.
        source = (ASSETS_DIR / "md.js").read_text(encoding="utf-8")
        self.assertNotRegex(source, r'href:\s*href\s*,')
        self.assertRegex(source, r'javascript', re.IGNORECASE)


class TestBrowseView(unittest.TestCase):
    def test_browse_view_is_registered(self):
        source = (ASSETS_DIR / "views.js").read_text(encoding="utf-8")
        self.assertIn('defineView("browse"', source)

    def test_details_styling_ships(self):
        self.assertIn(".tree", (ASSETS_DIR / "app.css").read_text(encoding="utf-8"))

    def test_deprecated_group_collapses_other_groups_stay_open(self):
        # Spec: "## Deprecated" starts collapsed, every other group open.
        # Pins the exact polarity of the <details open> formula — an
        # inverted `open: group.deprecated` would still "mention"
        # .deprecated but would collapse every non-deprecated group and
        # open Deprecated, the opposite of the spec.
        source = (ASSETS_DIR / "views.js").read_text(encoding="utf-8")
        self.assertRegex(source, r"open:\s*!\s*group\.deprecated")

    def test_missing_index_entries_do_not_link_to_a_dead_page_route(self):
        # entry.exists is false when the index line's target has no
        # backing page (its id is not in LORE.pages). Routing such an
        # entry to "#page/<id>" would hit renderPage(id), find nothing,
        # and silently render an empty "No page with id ..." view. The
        # entry must render as inert text instead of a page link.
        source = (ASSETS_DIR / "views.js").read_text(encoding="utf-8")
        self.assertRegex(source, r"entry\.exists\s*\?\s*pageLink\(entry\.id")

    def test_ghost_entries_are_rendered_without_assuming_an_id_field(self):
        # LORE.index.ghost_entries entries carry only {title, target} —
        # no id (they never matched a page). The ghost-entries rendering
        # must not read entry.id.
        source = (ASSETS_DIR / "views.js").read_text(encoding="utf-8")
        start = source.index("ghost_entries")
        end = source.index('defineView("browse"')
        section = source[start:end]
        self.assertNotIn("entry.id", section)
        self.assertIn("entry.target", section)

    def test_orphans_and_ghosts_sections_read_from_the_index(self):
        source = (ASSETS_DIR / "views.js").read_text(encoding="utf-8")
        self.assertIn("LORE.index.orphans", source)
        self.assertIn("LORE.index.ghost_entries", source)
        self.assertIn("Not in the index", source)
        self.assertIn("Ghost entries", source)

    def test_group_summary_shows_entry_count(self):
        source = (ASSETS_DIR / "views.js").read_text(encoding="utf-8")
        self.assertIn("group.entries.length", source)


class TestSearchAsset(unittest.TestCase):
    def test_search_asset_loads_before_the_views_that_call_it(self):
        self.assertLess(JS_ASSETS.index("search.js"), JS_ASSETS.index("views.js"))

    def test_field_weights_are_the_agreed_ones(self):
        source = (ASSETS_DIR / "search.js").read_text(encoding="utf-8")
        self.assertIn("title: 8", source)
        self.assertIn("tags: 4", source)
        self.assertIn("description: 2", source)
        self.assertIn("body: 1", source)

    def test_search_view_is_registered(self):
        self.assertIn('defineView("search"', (ASSETS_DIR / "views.js").read_text(encoding="utf-8"))


# search.js's searchPages(query, filters) is a pure function over LORE.pages
# — the ranking arithmetic (field weights, AND across terms, the title
# tie-break, the tag: prefix) is exactly what a source-text assertion
# cannot pin, and Task 4's scoring tests asserted only
# assertLess(score, 1.0) and had to be redone with literal values after
# review. Every expected score/order/snippet below is hand-derived from
# the stated rule (title 8, tag 4, description 2, body 1; AND across
# terms; ties broken on title ascending; snippet = match plus/minus 60
# chars) — never obtained by calling searchPages and copying its output.
SEARCH_RUNNER_JS = """
const fs = require("fs");
global.LORE = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const src = fs.readFileSync(process.argv[2], "utf8");
(0, eval)(src);
const requests = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const out = requests.map(req => searchPages(req.query, req.filters || {}).map(r => ({
  id: r.page.id, score: r.score, field: r.field, snippet: r.snippet.text,
})));
process.stdout.write(JSON.stringify(out));
"""

# highlight(snippet) is the DOM-building half of search.js: it must never
# hand a raw string to innerHTML, so a hostile page body (a <script> or
# <img onerror=...> tag) has to survive as inert text, and a query term
# containing regex metacharacters must not be treated as a wildcard.
# document/el are stubbed to record what highlight() built without a
# real DOM (highlight has no other DOM dependency).
HIGHLIGHT_RUNNER_JS = """
const fs = require("fs");
global.document = { createTextNode: text => ({ kind: "text", text: String(text) }) };
global.el = (tag, attrs) => ({ kind: "el", tag: tag, text: (attrs && attrs.text) || "" });
const src = fs.readFileSync(process.argv[2], "utf8");
(0, eval)(src);
const req = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const nodes = highlight({ text: req.text, terms: req.terms });
process.stdout.write(JSON.stringify(nodes.map(n => ({ kind: n.kind, tag: n.tag, text: n.text }))));
"""


def _page(page_id, title, tags=(), description="", body="", page_type="concept", status="stable"):
    return {"id": page_id, "title": title, "tags": list(tags), "description": description,
            "body": body, "type": page_type, "status": status}


@unittest.skipUnless(shutil.which("node"), "node not installed — search engine check skipped")
class TestSearchEngine(unittest.TestCase):
    def _search(self, pages, requests):
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "run_search.js"
            lore = Path(tmp) / "lore.json"
            reqs = Path(tmp) / "requests.json"
            runner.write_text(SEARCH_RUNNER_JS, encoding="utf-8")
            lore.write_text(json.dumps({"pages": pages}), encoding="utf-8")
            reqs.write_text(json.dumps(requests), encoding="utf-8")
            result = subprocess.run(
                ["node", str(runner), str(ASSETS_DIR / "search.js"), str(lore), str(reqs)],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def _highlight(self, text, terms):
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "run_highlight.js"
            req = Path(tmp) / "req.json"
            runner.write_text(HIGHLIGHT_RUNNER_JS, encoding="utf-8")
            req.write_text(json.dumps({"text": text, "terms": terms}), encoding="utf-8")
            result = subprocess.run(
                ["node", str(runner), str(ASSETS_DIR / "search.js"), str(req)],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    # -- ranking ---------------------------------------------------------

    def test_field_weight_scoring_and_title_tiebreak_are_pinned(self):
        # title 8 > tag 4 > description 2 > body 1, and equal scores
        # break on title ascending. Hand-derived: "zephyr" appears in
        # the title of 4 pages (tie at 8, alphabetical), the tag of one
        # (4), the description of one (2), the body of one (1); one
        # page has no "zephyr" anywhere and must be dropped entirely.
        pages = [
            _page("alpha-zephyr", "Alpha Zephyr", tags=["other"]),
            _page("bravo-zephyr", "Bravo Zephyr", tags=["other"]),
            _page("networking-zephyr", "Zephyr Networking Guide"),
            _page("title-zephyr", "Zephyr Overview", description="unrelated text", body="unrelated text"),
            _page("tag-zephyr", "Second Page", tags=["zephyr-tag"]),
            _page("desc-zephyr", "Third Page", description="This mentions zephyr in description"),
            _page("body-zephyr", "Fourth Page",
                  body="A passage mentioning zephyr deep inside the body text."),
            _page("no-match", "Unrelated Page", description="nothing here", body="nothing here either"),
        ]
        [results] = self._search(pages, [{"query": "zephyr", "filters": {}}])
        self.assertEqual(
            [(r["id"], r["score"], r["field"]) for r in results],
            [
                ("alpha-zephyr", 8, "title"),
                ("bravo-zephyr", 8, "title"),
                ("networking-zephyr", 8, "title"),
                ("title-zephyr", 8, "title"),
                ("tag-zephyr", 4, "tags"),
                ("desc-zephyr", 2, "description"),
                ("body-zephyr", 1, "body"),
            ])

    def test_and_semantics_drop_pages_missing_any_term(self):
        # Only "Zephyr Networking Guide" contains both "zephyr" (title,
        # 8) and "networking" (title, 8) = 16. Every other page here
        # contains "zephyr" but not "networking" and must be dropped,
        # even though it would score high on "zephyr" alone.
        pages = [
            _page("alpha-zephyr", "Alpha Zephyr", tags=["other"]),
            _page("networking-zephyr", "Zephyr Networking Guide"),
            _page("title-zephyr", "Zephyr Overview"),
        ]
        [results] = self._search(pages, [{"query": "zephyr networking", "filters": {}}])
        self.assertEqual([(r["id"], r["score"], r["field"]) for r in results],
                          [("networking-zephyr", 16, "title")])

    def test_tag_prefix_term_matches_via_tag_substring_only(self):
        # tag:zephyr must match only through a tag containing "zephyr"
        # (substring), weight 4 — never through title/description/body.
        pages = [
            _page("tag-zephyr", "Second Page", tags=["zephyr-tag"]),
            _page("title-zephyr", "Zephyr Overview"),  # "zephyr" in title only — must be excluded
        ]
        [results] = self._search(pages, [{"query": "tag:zephyr", "filters": {}}])
        self.assertEqual([(r["id"], r["score"], r["field"]) for r in results],
                          [("tag-zephyr", 4, "tags")])

    def test_a_tag_term_and_a_plain_term_sum_their_scores_in_one_query(self):
        # The one query that crosses scoreTerm's two branches: "tag:zephyr"
        # scores 4 through the tags branch and "overview" scores 8 through
        # the title branch, for 12 — and the reported field is the plain
        # term's, since a tag: term names no field of its own.
        pages = [
            _page("tag-and-title", "Zephyr Overview", tags=["zephyr-tag"]),
            _page("tag-only", "Unrelated Page", tags=["zephyr-tag"]),   # no "overview"
        ]
        [results] = self._search(pages, [{"query": "tag:zephyr overview", "filters": {}}])
        self.assertEqual([(r["id"], r["score"], r["field"]) for r in results],
                          [("tag-and-title", 12, "title")])

    def test_type_status_tag_filters_apply_before_ranking(self):
        # The three <select> filters are exact-match page-attribute
        # gates, applied before scoring — distinct from the substring
        # "tag:" query term above (the <select> narrows to an exact tag
        # string; "tag:" narrows to any tag containing the text).
        pages = [
            _page("alpha-zephyr", "Alpha Zephyr", tags=["other"]),
            _page("bravo-zephyr", "Bravo Zephyr", tags=["other"]),
            _page("networking-zephyr", "Zephyr Networking Guide", page_type="source"),
            _page("desc-zephyr", "Third Page", description="This mentions zephyr in description",
                  status="draft"),
        ]
        requests = [
            {"query": "zephyr", "filters": {"type": "source"}},
            {"query": "zephyr", "filters": {"status": "draft"}},
            {"query": "zephyr", "filters": {"tag": "other"}},
        ]
        by_type, by_status, by_tag = self._search(pages, requests)
        self.assertEqual([(r["id"], r["score"]) for r in by_type], [("networking-zephyr", 8)])
        self.assertEqual([(r["id"], r["score"]) for r in by_status], [("desc-zephyr", 2)])
        self.assertEqual([(r["id"], r["score"]) for r in by_tag],
                          [("alpha-zephyr", 8), ("bravo-zephyr", 8)])

    def test_regex_metacharacters_in_terms_match_literally_not_as_wildcards(self):
        # scoreTerm matches with String.includes, never a RegExp built
        # from the term, so "." in a query is a literal period — a page
        # containing "aXc" (which a naive `.` wildcard would match) must
        # NOT match a query for "a.c".
        pages = [
            _page("dot-literal", "Version a.c release notes"),
            _page("dot-wildcard-decoy", "Version aXc release notes"),
        ]
        [results] = self._search(pages, [{"query": "a.c", "filters": {}}])
        self.assertEqual([(r["id"], r["score"], r["field"]) for r in results],
                          [("dot-literal", 8, "title")])

    def test_empty_and_whitespace_only_queries_return_no_results(self):
        pages = [_page("p1", "Anything")]
        empty, whitespace = self._search(pages, [
            {"query": "", "filters": {}},
            {"query": "   ", "filters": {}},
        ])
        self.assertEqual(empty, [])
        self.assertEqual(whitespace, [])

    def test_tag_colon_alone_matches_any_page_with_at_least_one_tag(self):
        # Documented edge case: "tag:" has an empty `wanted` suffix, and
        # every string (including a tag) contains "". some() over an
        # empty tags array is false, so a bare "tag:" term matches every
        # page that has at least one tag and drops every page with none
        # — not a crash, not a no-op, but this specific asymmetry.
        pages = [
            _page("has-tags", "Has Tags Page", tags=["foo", "bar"]),
            _page("no-tags", "No Tags Page"),
        ]
        [results] = self._search(pages, [{"query": "tag:", "filters": {}}])
        self.assertEqual([(r["id"], r["score"], r["field"]) for r in results],
                          [("has-tags", 4, "tags")])

    # -- snippet -----------------------------------------------------------

    def test_snippet_pads_60_chars_either_side_of_the_match(self):
        body = "a" * 100 + "keyword" + "b" * 100
        pages = [_page("snip-mid", "Snippet Mid Page", body=body)]
        [results] = self._search(pages, [{"query": "keyword", "filters": {}}])
        expected = "…" + "a" * 60 + "keyword" + "b" * 60 + "…"
        self.assertEqual([(r["id"], r["score"], r["field"], r["snippet"]) for r in results],
                          [("snip-mid", 1, "body", expected)])

    def test_snippet_omits_ellipsis_at_body_start_and_end(self):
        lead_body = "keyword" + "c" * 200
        trail_body = "d" * 200 + "keyword"
        pages = [
            _page("snip-lead", "Snippet Lead Page", body=lead_body),
            _page("snip-trail", "Snippet Trail Page", body=trail_body),
        ]
        [results] = self._search(pages, [{"query": "keyword", "filters": {}}])
        snippets = {r["id"]: r["snippet"] for r in results}
        self.assertEqual(snippets["snip-lead"], "keyword" + "c" * 60 + "…")
        self.assertEqual(snippets["snip-trail"], "…" + "d" * 60 + "keyword")

    def test_snippet_collapses_consecutive_newlines_in_the_window(self):
        body = "e" * 60 + "keyword" + "\n\n\n" + "f" * 57
        pages = [_page("snip-newlines", "Snippet Newline Page", body=body)]
        [results] = self._search(pages, [{"query": "keyword", "filters": {}}])
        expected = "e" * 60 + "keyword" + " " + "f" * 57
        self.assertEqual(results[0]["snippet"], expected)

    def test_snippet_falls_back_to_description_when_body_has_no_match(self):
        pages = [_page("snip-fallback", "This has uniqueterm inside",
                        description="Fallback description text",
                        body="nothing relevant here at all")]
        [results] = self._search(pages, [{"query": "uniqueterm", "filters": {}}])
        self.assertEqual([(r["id"], r["score"], r["field"], r["snippet"]) for r in results],
                          [("snip-fallback", 8, "title", "Fallback description text")])

    def test_snippet_uses_the_globally_earliest_match_and_its_own_length(self):
        # Query terms are "zeb apple" (in that order) but "apple"
        # occurs earlier in the body than "zeb" — the snippet must
        # anchor on "apple" (the earliest match by position, not by
        # query-term order) and pad using "apple"'s own length (5), not
        # "zeb"'s (3): a wrong hit-length would put the trailing "…"
        # two characters earlier than pinned here.
        body = "g" * 10 + "apple" + "h" * 200 + "zeb" + "i" * 10
        pages = [_page("snip-earliest", "Snippet Order Test Page", description="filler", body=body)]
        [results] = self._search(pages, [{"query": "zeb apple", "filters": {}}])
        expected = "g" * 10 + "apple" + "h" * 60 + "…"
        self.assertEqual([(r["id"], r["score"], r["field"], r["snippet"]) for r in results],
                          [("snip-earliest", 2, "body", expected)])

    # -- highlight (DOM node construction) ----------------------------------

    def test_highlight_escapes_regex_metacharacters_before_building_the_pattern(self):
        nodes = self._highlight("prefix aXc middle a.c suffix", ["a.c"])
        self.assertEqual(
            [(n["kind"], n.get("tag"), n["text"]) for n in nodes],
            [
                ("text", None, "prefix aXc middle "),
                ("el", "mark", "a.c"),
                ("text", None, " suffix"),
            ])

    def test_highlight_renders_hostile_markup_as_inert_text_nodes(self):
        text = "before <script>alert(1)</script> after <img src=x onerror=alert(1)> end"
        nodes = self._highlight(text, ["alert"])
        self.assertEqual(
            [(n["kind"], n.get("tag"), n["text"]) for n in nodes],
            [
                ("text", None, "before <script>"),
                ("el", "mark", "alert"),
                ("text", None, "(1)</script> after <img src=x onerror="),
                ("el", "mark", "alert"),
                ("text", None, "(1)> end"),
            ])
        # No node kind other than the two safe DOM primitives exists —
        # the hostile substrings survive only as plain string data
        # inside text/mark nodes, never inside anything that could be
        # parsed as markup, and nothing was dropped or altered.
        self.assertEqual("".join(n["text"] for n in nodes), text)


class TestHealthAndStatsViews(unittest.TestCase):
    def test_both_views_are_registered(self):
        source = (ASSETS_DIR / "views.js").read_text(encoding="utf-8")
        self.assertIn('defineView("health"', source)
        self.assertIn('defineView("stats"', source)

    def test_bars_are_inline_svg_from_core(self):
        core = (ASSETS_DIR / "core.js").read_text(encoding="utf-8")
        self.assertIn("http://www.w3.org/2000/svg", core)
        self.assertIn("function bar(", core)

    def test_no_chart_library_is_referenced(self):
        for name in JS_ASSETS:
            source = (ASSETS_DIR / name).read_text(encoding="utf-8")
            for library in ["d3", "chart.js", "plotly", "echarts"]:
                self.assertNotIn(library, source.lower())


class TestLogAndInboxViews(unittest.TestCase):
    def test_both_views_are_registered(self):
        source = (ASSETS_DIR / "views.js").read_text(encoding="utf-8")
        self.assertIn('defineView("log"', source)
        self.assertIn('defineView("inbox"', source)

    def test_state_badge_styles_exist_for_every_ledger_state(self):
        css = (ASSETS_DIR / "app.css").read_text(encoding="utf-8")
        for state in ["NEW", "CHANGED", "PROCESSED", "SKIPPED"]:
            self.assertIn(".badge." + state, css)


# bar(fraction, options) is a pure function of its arguments — the geometry
# it hands back (clamped rect width, threshold-picked colour) is exactly
# what a source-text assertion cannot pin. Loaded and called for real in
# node, with document.createElementNS stubbed to a plain recording object
# (svgEl has no other DOM dependency). Every expected value below is
# hand-derived from the stated formula — filled = clamp01(fraction) * width,
# colour by fraction >= 0.9 / >= 0.6 / else — and cross-checked by actually
# running bar() against these inputs, never guessed digit-by-digit for the
# floating-point cases (0.9 * 160 and 0.6 * 160 both land on an exact
# integer in IEEE 754 double, confirmed by that run: 144 and 96).
BAR_RUNNER_JS = """
const fs = require("fs");
function makeSvgNode(tag) {
  return {
    tag: tag, attrs: {}, children: [],
    setAttribute(key, value) { this.attrs[key] = value; },
    append(...kids) { for (const k of kids) this.children.push(k); },
  };
}
global.document = {
  getElementById: () => ({ textContent: JSON.stringify({ pages: [] }) }),
  createElementNS: (ns, tag) => makeSvgNode(tag),
};
const src = fs.readFileSync(process.argv[2], "utf8");
(0, eval)(src);
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
function serialize(node) {
  return { tag: node.tag, attrs: node.attrs, children: node.children.map(serialize) };
}
const out = cases.map(c => serialize(bar(c.fraction, c.options)));
process.stdout.write(JSON.stringify(out));
"""


def _bar_svg(width, height, aria_label, track_width, filled_width, colour):
    return {
        "tag": "svg",
        "attrs": {"width": width, "height": height, "class": "bar",
                  "role": "img", "aria-label": aria_label},
        "children": [
            {"tag": "rect", "attrs": {"x": 0, "y": 0, "width": track_width, "height": height,
                                       "rx": 4, "fill": "var(--surface-3)"}, "children": []},
            {"tag": "rect", "attrs": {"x": 0, "y": 0, "width": filled_width, "height": height,
                                       "rx": 4, "fill": colour}, "children": []},
        ],
    }


@unittest.skipUnless(shutil.which("node"), "node not installed — bar geometry check skipped")
class TestBarGeometry(unittest.TestCase):
    def test_bar_geometry_is_pinned_including_boundaries_and_out_of_range(self):
        cases = [
            {"fraction": 0, "options": None},
            {"fraction": 1, "options": None},
            {"fraction": 2, "options": None},   # above 1 — must not overflow the track
            {"fraction": -1, "options": None},  # below 0 — must not go negative
            {"fraction": 0.9, "options": None},   # colour threshold: >= 0.9 is "good"
            {"fraction": 0.6, "options": None},   # colour threshold: >= 0.6 (and < 0.9) is "warn"
            {"fraction": 0.5, "options": {"width": 200, "height": 10, "color": "#ffffff"}},
        ]
        expected = [
            _bar_svg(160, 8, "0%", 160, 0, "var(--bad)"),
            _bar_svg(160, 8, "100%", 160, 160, "var(--good)"),
            # fraction=2: aria-label reflects the raw (unclamped) fmtPct(2) = "200%",
            # but the visual fill is clamped to the track width, not overflowing it.
            _bar_svg(160, 8, "200%", 160, 160, "var(--good)"),
            # fraction=-1: aria-label is fmtPct(-1) = "-100%", but the fill clamps to 0,
            # never negative.
            _bar_svg(160, 8, "-100%", 160, 0, "var(--bad)"),
            _bar_svg(160, 8, "90%", 160, 144, "var(--good)"),
            _bar_svg(160, 8, "60%", 160, 96, "var(--warn)"),
            # explicit options.color overrides the threshold colour entirely.
            _bar_svg(200, 10, "50%", 200, 100, "#ffffff"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "run_bar.js"
            cases_path = Path(tmp) / "cases.json"
            runner.write_text(BAR_RUNNER_JS, encoding="utf-8")
            cases_path.write_text(json.dumps(cases), encoding="utf-8")
            result = subprocess.run(
                ["node", str(runner), str(ASSETS_DIR / "core.js"), str(cases_path)],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), expected)


# offenderNode(offender) is the branch that decides how a Health-tab
# offender renders: a "page" offender becomes a pageLink(...) call, a "raw"
# offender becomes a plain "#inbox" link, and everything else — including a
# "page" offender whose ref does NOT match any page in the payload (a dead
# wikilink target, or any other id the health checks can name without it
# backing a real page record) — must fall through to inert text. Routing
# that case to pageLink would build a link into renderPage() for an id with
# no matching page: a silently empty "No page with id ..." view. This is
# executed for real in node with pageById/pageLink/el stubbed (el as a
# plain recording object, matching the existing highlight() test pattern)
# so the assertion is "pageLink was never called for the unmatched ref",
# not a source-text guess about which branch runs.
OFFENDER_RUNNER_JS = """
const fs = require("fs");
global.defineView = () => {};
const pageLinkCalls = [];
global.pageById = (id) => (id === "known" ? { id: "known", title: "Known Page" } : null);
global.pageLink = (id) => { pageLinkCalls.push(id); return { kind: "pageLink", id: id }; };
global.el = (tag, attrs, children) => ({
  kind: "el", tag: tag,
  class: (attrs && attrs.class) || null,
  text: (attrs && attrs.text) || null,
  href: (attrs && attrs.href) || null,
  children: [].concat(children || []),
});
const src = fs.readFileSync(process.argv[2], "utf8");
(0, eval)(src);
const offenders = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const nodes = offenders.map(offenderNode);
process.stdout.write(JSON.stringify({ nodes: nodes, pageLinkCalls: pageLinkCalls }));
"""


@unittest.skipUnless(shutil.which("node"), "node not installed — offender rendering check skipped")
class TestOffenderRendering(unittest.TestCase):
    def _render(self, offenders):
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "run_offender.js"
            cases_path = Path(tmp) / "offenders.json"
            runner.write_text(OFFENDER_RUNNER_JS, encoding="utf-8")
            cases_path.write_text(json.dumps(offenders), encoding="utf-8")
            result = subprocess.run(
                ["node", str(runner), str(ASSETS_DIR / "views.js"), str(cases_path)],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_page_offender_with_known_ref_links_via_pagelink(self):
        out = self._render([{"ref": "known", "kind": "page", "detail": "dead wikilinks: x"}])
        self.assertEqual(out["pageLinkCalls"], ["known"])
        [node] = out["nodes"]
        self.assertEqual(node["tag"], "li")
        self.assertEqual(node["children"][0], {"kind": "pageLink", "id": "known"})
        self.assertEqual(node["children"][1]["text"], " — dead wikilinks: x")

    def test_page_offender_with_unmatched_ref_renders_as_inert_text_not_a_dead_link(self):
        # ref "ghost" has no matching page (pageById returns null) — this
        # must NOT call pageLink and must NOT produce a link into an empty
        # page view.
        out = self._render([{"ref": "ghost", "kind": "page", "detail": "dead wikilinks: y"}])
        self.assertEqual(out["pageLinkCalls"], [])
        [node] = out["nodes"]
        self.assertEqual(node, {"kind": "el", "tag": "li", "class": "muted",
                                "text": "ghost — dead wikilinks: y", "href": None, "children": []})

    def test_raw_offender_links_to_inbox_not_a_page_route(self):
        out = self._render([{"ref": "notes.pdf", "kind": "raw", "detail": "new"}])
        self.assertEqual(out["pageLinkCalls"], [])
        [node] = out["nodes"]
        self.assertEqual(node["tag"], "li")
        link = node["children"][0]
        self.assertEqual((link["tag"], link["href"], link["text"]), ("a", "#inbox", "notes.pdf"))

    def test_other_kind_offender_renders_as_plain_text(self):
        out = self._render([{"ref": "index.md", "kind": "lore", "detail": "3 lines over target"}])
        self.assertEqual(out["pageLinkCalls"], [])
        [node] = out["nodes"]
        self.assertEqual(node, {"kind": "el", "tag": "li", "class": "muted",
                                "text": "index.md — 3 lines over target", "href": None,
                                "children": []})


class TestGraphAsset(unittest.TestCase):
    def test_graph_asset_loads_before_views(self):
        self.assertLess(JS_ASSETS.index("graph.js"), JS_ASSETS.index("views.js"))

    def test_graph_view_is_registered(self):
        self.assertIn('defineView("graph"', (ASSETS_DIR / "views.js").read_text(encoding="utf-8"))

    def test_the_old_standalone_graph_script_is_gone(self):
        scripts = ASSETS_DIR.parent
        self.assertFalse((scripts / "lore_graph.py").exists())
        self.assertFalse((scripts / "test_lore_graph.py").exists())

    def test_graph_uses_deterministic_layout_seeding(self):
        source = (ASSETS_DIR / "graph.js").read_text(encoding="utf-8")
        self.assertNotIn("Math.random", source)     # golden-angle spiral, stable across runs


# graph.js separates the parts of the graph that are pure functions of the
# payload (node filtering, the focus/hops subgraph, the radius formula, the
# isolated/clustered split, and the deterministic layout seed) from the
# canvas drawing/force-simulation that only means anything in a real
# browser. This runner loads graph.js alone — none of its top-level pure
# helpers touch `document`/`window`/`LORE` until called, so no DOM stub is
# needed at all — and calls the real functions by name via a small generic
# dispatch table, exactly the "actually run it" style BAR_RUNNER_JS and
# SEARCH_RUNNER_JS already use above. A Set result is returned sorted (order
# is not part of the contract); a Map result as [[key, value], ...] entries;
# an array of node objects as just their ids (what the hand-derived
# expectations below care about, not object identity).
GRAPH_PURE_RUNNER_JS = """
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
(0, eval)(src);
const spec = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const fns = { radiusOf, withinHops, visibleNodes, isDimmed, isolatedIdSet,
              idRanks, seedPosition, isolatedGridPosition };
function normalise(result) {
  if (result instanceof Set) return [...result].sort();
  if (result instanceof Map) return [...result.entries()];
  if (Array.isArray(result)) {
    return result.map(item => (item && item.id !== undefined) ? item.id : item);
  }
  return result;
}
const out = spec.calls.map(call => normalise(fns[call.fn](...call.args)));
process.stdout.write(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node not installed — graph helper check skipped")
class TestGraphPureFunctions(unittest.TestCase):
    def _call(self, calls):
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "run_graph_pure.js"
            spec_path = Path(tmp) / "calls.json"
            runner.write_text(GRAPH_PURE_RUNNER_JS, encoding="utf-8")
            spec_path.write_text(json.dumps({"calls": calls}), encoding="utf-8")
            result = subprocess.run(
                ["node", str(runner), str(ASSETS_DIR / "graph.js"), str(spec_path)],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_radius_grows_with_inbound_degree_capped_at_8_plus_a_base_of_6(self):
        # Contract (both the Interfaces section and the controller's
        # decisions doc): "6 + min(node.in, 8)". The brief's own Step 3
        # sample wrote `5 + Math.min(node.in || 0, 8)` — a base of 5, not
        # 6 — which disagrees with the stated contract; the contract wins.
        # This case set discriminates 5-vs-6 at every boundary: in=0 (base
        # only), in=3 (under the cap), in=8 (exactly at the cap), in=20
        # (over the cap, must clamp), and a node with no `in` field at all
        # (the `|| 0` fallback).
        nodes = [{"in": 0}, {"in": 3}, {"in": 8}, {"in": 20}, {}]
        radii = self._call([{"fn": "radiusOf", "args": [n]} for n in nodes])
        self.assertEqual(radii, [6, 9, 14, 14, 6])

    def test_hops_1_to_3_expand_the_focus_subgraph_by_exactly_that_many_steps(self):
        # Path graph A-B-C-D-E. From A: 1 hop reaches B, 2 hops reach C,
        # 3 hops reach D (never E — that would take 4). From C (mid-chain),
        # 1 hop reaches both neighbours B and D. A node absent from every
        # edge returns just itself, not a crash.
        edges = [{"source": "A", "target": "B"}, {"source": "B", "target": "C"},
                 {"source": "C", "target": "D"}, {"source": "D", "target": "E"}]
        cases = [("A", 1), ("A", 2), ("A", 3), ("C", 1), ("Z", 2)]
        results = self._call([{"fn": "withinHops", "args": [start, hops, edges]}
                               for start, hops in cases])
        self.assertEqual(results, [
            ["A", "B"],
            ["A", "B", "C"],
            ["A", "B", "C", "D"],
            ["B", "C", "D"],
            ["Z"],
        ])

    def test_hide_deprecated_checked_hides_deprecated_nodes_not_the_opposite(self):
        # Pins the exact polarity the controller flagged as a likely error:
        # state.hideDeprecated: true (the checkbox's default, checked) must
        # HIDE the one deprecated node ("b"), not show only deprecated
        # nodes and hide everything else.
        nodes = [
            {"id": "a", "type": "concept", "status": "stable", "tags": ["x"]},
            {"id": "b", "type": "source", "status": "deprecated", "tags": ["y"]},
            {"id": "c", "type": "concept", "status": "draft", "tags": []},
        ]
        edges = [{"source": "a", "target": "b"}]

        def visible(**state):
            full_state = {"hideDeprecated": False, "type": "", "status": "", "tag": "",
                          "focus": None, "hops": 1}
            full_state.update(state)
            return {"fn": "visibleNodes", "args": [nodes, edges, full_state]}

        results = self._call([
            visible(hideDeprecated=True),                 # -> a, c (b hidden)
            visible(hideDeprecated=False),                # -> a, b, c (nothing hidden)
            visible(type="concept"),                       # -> a, c
            visible(status="deprecated"),                   # -> b
            visible(tag="y"),                               # -> b
            visible(focus="a", hops=1),                     # -> a, b (a's 1-hop neighbour)
        ])
        self.assertEqual([sorted(r) for r in results], [
            ["a", "c"],
            ["a", "b", "c"],
            ["a", "c"],
            ["b"],
            ["b"],
            ["a", "b"],
        ])

    def test_focus_node_is_exempt_from_hide_deprecated_but_its_neighbours_are_not(self):
        # Regression: the page view's mini graph always calls initGraph
        # with hideDeprecated defaulting to true and ships no controls to
        # change it. Before this fix, visibleNodes applied hideDeprecated
        # to the focus node exactly like everyone else, so a deprecated
        # page's own "Neighbourhood" widget silently dropped its own
        # subject node — and rendered as a bare empty array whenever the
        # focused (deprecated) page's neighbours were deprecated too,
        # which is a normal state for a real lore (deprecating a page
        # usually comes with deprecating what it links to). The prior
        # test above combines a focus with a deprecated *neighbour* but
        # never with a deprecated *focus node* itself — exactly why this
        # shipped — so this test targets that specific gap.
        #
        # Star graph: b (deprecated) is the focus, linked to a (stable),
        # c (deprecated), and d (stable). hideDeprecated=true must keep b
        # (it is the focus, exempt) and d/a (never deprecated), but still
        # drop c (a deprecated node that is NOT the focus).
        star_nodes = [
            {"id": "a", "type": "concept", "status": "stable", "tags": []},
            {"id": "b", "type": "source", "status": "deprecated", "tags": []},
            {"id": "c", "type": "concept", "status": "deprecated", "tags": []},
            {"id": "d", "type": "concept", "status": "stable", "tags": []},
        ]
        star_edges = [{"source": "b", "target": "a"}, {"source": "b", "target": "c"},
                     {"source": "b", "target": "d"}]
        star_state = {"hideDeprecated": True, "type": "", "status": "", "tag": "",
                     "focus": "b", "hops": 1}

        # p (deprecated) is the focus and its *only* neighbour q is also
        # deprecated. Pre-fix this filtered to [] entirely (p excluded
        # like any other deprecated node) — exactly the "renders
        # completely empty" failure mode reported. Post-fix p alone must
        # still render: q (not the focus) stays hidden, p (the focus)
        # does not.
        chain_nodes = [
            {"id": "p", "type": "concept", "status": "deprecated", "tags": []},
            {"id": "q", "type": "concept", "status": "deprecated", "tags": []},
        ]
        chain_edges = [{"source": "p", "target": "q"}]
        chain_state = {"hideDeprecated": True, "type": "", "status": "", "tag": "",
                       "focus": "p", "hops": 1}

        results = self._call([
            {"fn": "visibleNodes", "args": [star_nodes, star_edges, star_state]},
            {"fn": "visibleNodes", "args": [chain_nodes, chain_edges, chain_state]},
        ])
        # a and d (never deprecated) plus b (the deprecated focus, exempt)
        # survive; c (a deprecated non-focus neighbour) is dropped.
        self.assertEqual(sorted(results[0]), ["a", "b", "d"])
        # p (the deprecated focus) survives alone — never the empty list
        # the pre-fix filter produced for this exact shape.
        self.assertEqual(results[1], ["p"])

    def test_dimmed_matches_title_or_id_case_insensitively_empty_query_never_dims(self):
        node_a = {"title": "Concept A", "id": "concept-a"}
        node_b = {"title": "Foo", "id": "bar-id"}
        results = self._call([
            {"fn": "isDimmed", "args": [node_a, ""]},
            {"fn": "isDimmed", "args": [node_a, "concept"]},
            {"fn": "isDimmed", "args": [node_a, "ZZZ"]},
            {"fn": "isDimmed", "args": [node_b, "bar"]},
        ])
        self.assertEqual(results, [False, False, True, False])

    def test_isolated_id_set_is_every_node_untouched_by_any_edge(self):
        results = self._call([
            {"fn": "isolatedIdSet",
             "args": [[{"id": "a"}, {"id": "b"}, {"id": "c"}], [{"source": "a", "target": "b"}]]},
            {"fn": "isolatedIdSet", "args": [[{"id": "x"}, {"id": "y"}], []]},
        ])
        self.assertEqual(results, [["c"], ["x", "y"]])

    def test_layout_seed_is_keyed_by_sorted_id_rank_not_array_position(self):
        # Nodes deliberately supplied out of alphabetical order. If the seed
        # were keyed by array index (i from a forEach), ranks would come
        # back [0, 1, 2] in this input order — order-dependent, and only
        # "stable" because a caller happens to pass ids pre-sorted. Keyed by
        # id instead, the same three ids always rank the same way (alpha=0,
        # bravo=1, charlie=2) no matter what order they arrive in.
        nodes = [{"id": "charlie"}, {"id": "alpha"}, {"id": "bravo"}]
        [ranks] = self._call([{"fn": "idRanks", "args": [nodes]}])
        by_id = dict(ranks)
        self.assertEqual(by_id, {"alpha": 0, "bravo": 1, "charlie": 2})

    def test_seed_position_is_a_deterministic_pure_function_of_rank(self):
        # rank 0 lands at angle 0 (cos=1, sin=0), radius 24*sqrt(1) — exact,
        # no floating-point ambiguity. Calling the same rank twice in one
        # process additionally proves determinism directly (same input,
        # same output) without hand-deriving a transcendental cos/sin
        # decimal for a non-zero rank.
        results = self._call([
            {"fn": "seedPosition", "args": [0]},
            {"fn": "seedPosition", "args": [3]},
            {"fn": "seedPosition", "args": [3]},
        ])
        seed_zero, seed_three_a, seed_three_b = results
        self.assertEqual(seed_zero, {"x": 24, "y": 0})
        self.assertEqual(seed_three_a, seed_three_b)

    def test_isolated_grid_wraps_at_8_columns_below_the_main_cluster(self):
        results = self._call([{"fn": "isolatedGridPosition", "args": [row]}
                               for row in (0, 7, 8, 9)])
        self.assertEqual(results, [
            {"x": -300, "y": 340},
            {"x": 260, "y": 340},
            {"x": -300, "y": 380},   # wraps to a new row after column 8
            {"x": -220, "y": 380},
        ])


# graph.js's destroy lifecycle is the other half of the leak the controller
# flagged: the graph tab and the page view's mini graph both start a
# requestAnimationFrame loop and a window "resize"/"mouseup" listener, and
# the router (app.js) replaces the view's whole DOM subtree on every
# navigation with no per-view unmount hook to call destroy() from. So
# initGraph()'s own loop checks, once per frame, whether its host is still
# attached to the document — the same thing route()'s clear(main) does to
# every torn-down view's markup — and runs the exact same cleanup destroy()
# does. This runner proves both paths: an explicit destroy() call while
# still connected (scenario 1) and a host silently going away with no
# destroy() call at all (scenario 2, the actual navigation-away case).
# requestAnimationFrame is stubbed to record callbacks without invoking them
# — the test fires frames one at a time under its own control, so it can
# observe whether a given frame rescheduled another one or not.
GRAPH_LIFECYCLE_RUNNER_JS = """
const fs = require("fs");

function makeNode(tag) {
  return {
    tag, style: {}, children: [], listeners: {}, isConnected: true,
    setAttribute() {},
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    removeEventListener(type, fn) {
      if (!this.listeners[type]) return;
      this.listeners[type] = this.listeners[type].filter(f => f !== fn);
    },
    append(...kids) { for (const k of kids) this.children.push(k); },
    get firstChild() { return this.children[0] || null; },
    removeChild(child) {
      const i = this.children.indexOf(child);
      if (i >= 0) this.children.splice(i, 1);
      return child;
    },
    getBoundingClientRect() { return { left: 0, top: 0 }; },
    getContext() { return ctxStub; },
  };
}

// Every ctx.method(...) call and ctx.property = value assignment used by
// graph.js's draw()/tick() is swallowed generically — painting itself is
// exactly the part TestGraphPureFunctions above deliberately does not test.
const ctxStub = new Proxy({}, {
  get() { return function () {}; },
  set() { return true; },
});

global.document = {
  documentElement: {},
  getElementById: (id) => (id === "lore-data" ? { textContent: JSON.stringify({ pages: [] }) }
                                               : makeNode("div")),
  createElement: (tag) => makeNode(tag),
  createElementNS: (ns, tag) => makeNode(tag),
  createTextNode: (text) => ({ nodeType: 3, text: String(text) }),
};
// Counted, not just stubbed: every graph colour is a CSS custom property
// that never changes for the life of the graph, so they must be resolved
// once at init and never again from inside the per-frame draw loop.
let computedStyleCalls = 0;
global.getComputedStyle = () => { computedStyleCalls++; return { getPropertyValue: () => "" }; };

const winListeners = {};
global.window = {
  devicePixelRatio: 1,
  addEventListener(type, fn) { (winListeners[type] = winListeners[type] || []).push(fn); },
  removeEventListener(type, fn) {
    if (!winListeners[type]) return;
    winListeners[type] = winListeners[type].filter(f => f !== fn);
  },
};
function countOf(type) { return (winListeners[type] || []).length; }

let rafQueue = [];
global.requestAnimationFrame = (cb) => { rafQueue.push(cb); return rafQueue.length; };
function fireOneFrame() { const cb = rafQueue.shift(); if (cb) cb(); }

const coreSrc = fs.readFileSync(process.argv[2], "utf8");
const graphSrc = fs.readFileSync(process.argv[3], "utf8");
(0, eval)(coreSrc + "\\n" + graphSrc);

const sampleNodes = [
  { id: "a", title: "A", type: "concept", status: "stable", tags: [], ghost: false, in: 1, out: 1 },
  { id: "b", title: "B", type: "concept", status: "stable", tags: [], ghost: false, in: 1, out: 1 },
];
const sampleEdges = [{ source: "a", target: "b" }];

// --- Scenario 1: a caller explicitly calls destroy() on a still-connected host ---
const host1 = makeNode("div");
const resizeBefore1 = countOf("resize"), mouseupBefore1 = countOf("mouseup");
const graph1 = initGraph(host1, { nodes: sampleNodes, edges: sampleEdges, height: 100 });
const resizeAfterCreate1 = countOf("resize") - resizeBefore1;
const mouseupAfterCreate1 = countOf("mouseup") - mouseupBefore1;
const hostChildrenAfterCreate1 = host1.children.length;

// initGraph() resolves the palette and then runs loop() once synchronously,
// so this count covers the palette plus the first full draw of both nodes.
const computedStyleAfterCreate1 = computedStyleCalls;

const rafLenBeforeFrame1 = rafQueue.length;
fireOneFrame();   // still connected: tick/draw, then reschedule
const rescheduledWhileConnected1 = rafLenBeforeFrame1 > 0 && rafQueue.length === rafLenBeforeFrame1;
const computedStyleAfterFrame1 = computedStyleCalls;   // a whole extra draw

graph1.destroy();
const resizeAfterDestroy1 = countOf("resize") - resizeBefore1;
const mouseupAfterDestroy1 = countOf("mouseup") - mouseupBefore1;
const hostChildrenAfterDestroy1 = host1.children.length;

const rafLenBeforePostDestroyFrame = rafQueue.length;
fireOneFrame();   // the frame still queued when destroy() ran fires once more
const queueEmptyAfterDestroyFrame1 = rafLenBeforePostDestroyFrame > 0 && rafQueue.length === 0;

let destroyTwiceThrew = false;
try { graph1.destroy(); } catch (e) { destroyTwiceThrew = true; }   // must be idempotent

// --- Scenario 2: destroy() is never called; the host is simply detached,
// exactly what route()'s clear(main) does on every navigation ---
const host2 = makeNode("div");
const resizeBefore2 = countOf("resize");
initGraph(host2, { nodes: sampleNodes, edges: sampleEdges, height: 100 });
const resizeAfterCreate2 = countOf("resize") - resizeBefore2;
const rafLenAfterCreate2 = rafQueue.length;

fireOneFrame();   // still connected: reschedules
const rescheduledWhileConnected2 = rafLenAfterCreate2 > 0 && rafQueue.length === rafLenAfterCreate2;

host2.isConnected = false;
const rafLenBeforeDisconnectFrame = rafQueue.length;
fireOneFrame();   // must self-stop here — nothing else ever calls destroy() on host2
const resizeAfterSelfStop2 = countOf("resize") - resizeBefore2;
const hostChildrenAfterSelfStop2 = host2.children.length;
const queueEmptyAfterSelfStop2 = rafLenBeforeDisconnectFrame > 0 && rafQueue.length === 0;

process.stdout.write(JSON.stringify({
  resizeAfterCreate1, mouseupAfterCreate1, hostChildrenAfterCreate1, rescheduledWhileConnected1,
  computedStyleAfterCreate1, computedStyleAfterFrame1,
  resizeAfterDestroy1, mouseupAfterDestroy1, hostChildrenAfterDestroy1,
  queueEmptyAfterDestroyFrame1, destroyTwiceThrew,
  resizeAfterCreate2, rescheduledWhileConnected2,
  resizeAfterSelfStop2, hostChildrenAfterSelfStop2, queueEmptyAfterSelfStop2,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not installed — graph lifecycle check skipped")
class TestGraphLifecycle(unittest.TestCase):
    def _run(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "run_graph_lifecycle.js"
            runner.write_text(GRAPH_LIFECYCLE_RUNNER_JS, encoding="utf-8")
            result = subprocess.run(
                ["node", str(runner), str(ASSETS_DIR / "core.js"), str(ASSETS_DIR / "graph.js")],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_explicit_destroy_removes_listeners_clears_host_and_halts_the_loop(self):
        out = self._run()
        self.assertEqual(out["resizeAfterCreate1"], 1)
        self.assertEqual(out["mouseupAfterCreate1"], 1)
        self.assertEqual(out["hostChildrenAfterCreate1"], 2)   # canvas + tooltip
        self.assertTrue(out["rescheduledWhileConnected1"], "loop did not reschedule while connected")
        self.assertEqual(out["resizeAfterDestroy1"], 0)
        self.assertEqual(out["mouseupAfterDestroy1"], 0)
        self.assertEqual(out["hostChildrenAfterDestroy1"], 0)
        self.assertTrue(out["queueEmptyAfterDestroyFrame1"], "loop rescheduled itself after destroy()")
        self.assertFalse(out["destroyTwiceThrew"], "destroy() must be safe to call more than once")

    def test_the_colour_palette_is_resolved_once_at_init_never_per_frame(self):
        # getComputedStyle() is a layout-flushing round trip, and draw() used
        # to call it 2-4 times per node per animation frame for values that
        # cannot change (one dark palette, no theme toggle): at 400 nodes and
        # 60fps, ~100k lookups a second. A whole extra frame must cost zero.
        out = self._run()
        self.assertEqual(out["computedStyleAfterFrame1"], out["computedStyleAfterCreate1"],
                         "draw() resolved a CSS variable during a frame")
        self.assertLessEqual(out["computedStyleAfterCreate1"], 20,
                             "the palette should be a fixed, one-time set of lookups")

    def test_host_disconnection_alone_self_stops_the_loop_with_no_explicit_destroy_call(self):
        out = self._run()
        self.assertEqual(out["resizeAfterCreate2"], 1)
        self.assertTrue(out["rescheduledWhileConnected2"])
        self.assertEqual(out["resizeAfterSelfStop2"], 0)
        self.assertEqual(out["hostChildrenAfterSelfStop2"], 0)
        self.assertTrue(out["queueEmptyAfterSelfStop2"],
                        "loop kept scheduling frames after its host left the document")


# renderHealth() and renderStats() are the two views this task exists to
# deliver. bar() and offenderNode() above are leaf helpers; dimensionCard's
# clean/failing collapse and countTable's max-scaling, chip, and
# empty-table logic have no coverage beyond the source-text
# defineView("health"...)/defineView("stats"...) greps without exercising
# the actual render functions. This runs them for real: a single indirect
# eval() over core.js + views.js concatenated — matching exactly how
# lore_dashboard_html.py joins JS_ASSETS into one <script> block, since two
# separate eval() calls would each get their own top-level lexical scope in
# Node (unlike a browser's shared per-document scope across <script> tags),
# and core.js's top-level `const LORE = ...` would then not be visible to
# views.js's render functions — against a representative payload, with
# document stubbed to a plain recording DOM (createElement/
# createElementNS/createTextNode/getElementById), the same style of stub
# used by BAR_RUNNER_JS and OFFENDER_RUNNER_JS above.
RENDERED_VIEWS_RUNNER_JS = """
const fs = require("fs");

function makeNode(tag) {
  return {
    nodeType: 1, tag: tag, _className: "", attrs: {}, children: [], listeners: {}, _text: null,
    setAttribute(key, value) { this.attrs[key] = value; },
    addEventListener(type, fn) { this.listeners[type] = fn; },
    // Appending a DocumentFragment splices its children in and empties it,
    // exactly as the real DOM does — renderMarkdown() builds into a fragment
    // and renderPage() then appends that fragment to a <section>.
    append(...kids) {
      for (const k of kids) {
        if (k === undefined || k === null) continue;
        if (k.tag === "#fragment") { this.children.push(...k.children); k.children = []; }
        else this.children.push(k);
      }
    },
    // appendChild returns the appended child, as the DOM does — that return
    // value is how renderMarkdown() gets hold of a nested <ul>/<ol>.
    appendChild(child) { this.append(child); return child; },
    // firstChild/removeChild are what core.js's clear() walks — the Log
    // view's filters clear and refill their results <tbody> in place.
    get firstChild() { return this.children[0] || null; },
    removeChild(child) {
      const i = this.children.indexOf(child);
      if (i >= 0) this.children.splice(i, 1);
      return child;
    },
    get className() { return this._className; },
    set className(v) { this._className = v; },
    get textContent() { return this._text; },
    set textContent(v) { this._text = v; this.children = []; },
  };
}

const loreJson = fs.readFileSync(process.argv[2], "utf8");
// The header's search box lives outside #view, so renderSearch() reads and
// writes its .value rather than owning it — one persistent stub node.
const searchBox = makeNode("input");
searchBox.value = "";
global.document = {
  createElement: (tag) => makeNode(tag),
  createElementNS: (ns, tag) => makeNode(tag),
  createTextNode: (text) => ({ nodeType: 3, text: String(text) }),
  createDocumentFragment: () => makeNode("#fragment"),
  getElementById: (id) => (id === "lore-data" ? { textContent: loreJson }
                           : id === "global-search" ? searchBox : makeNode("div")),
};
global.window = { location: { hash: "" }, LORE_QUERY: undefined };
global.navigator = { clipboard: null };
// The search view's filter <select>s call route() to re-render the current
// tab in place, the way app.js wires up its filters; this harness never
// loads app.js, so route is stubbed inert here. (The Log view's own filters
// deliberately do not go through route(): they re-render just their results
// <tbody> and count heading, which is what keeps the free-text box from
// being destroyed — and so blurred — on every keystroke.)
global.route = function () {};
// renderGraph() defers mounting the canvas (initGraph, from graph.js, never
// loaded here) behind requestAnimationFrame so the host has real layout
// dimensions first; that callback is never invoked here, so it is stubbed
// inert and only renderGraph()'s synchronous control markup is exercised —
// exactly the DOM-buildable half of the graph tab a serialised tree can
// assert on, per the same split graph.js's own pure-function tests use for
// the canvas-drawing half.
global.requestAnimationFrame = function () {};

// argv[3:] are the JS assets to load, in manifest order (core.js, md.js,
// search.js, views.js — graph.js and app.js are the two the harness leaves
// out; every entry point into them here is behind a stubbed
// requestAnimationFrame or the stubbed route()).
const assetSrc = process.argv.slice(3).map(p => fs.readFileSync(p, "utf8")).join("\\n");
// Declared with `function`, not `const`, so indirect eval hoists it onto
// the global object the same way renderHealth/renderStats below are —
// closing over the same LORE binding those functions do, purely so this
// script can read LORE.log.entries back afterwards and confirm that
// exercising the log view's filters never mutates the payload's own array.
const introspectionSrc =
  "function __logEntryLines(){ return LORE.log.entries.map(function(e){ return e.line; }); }";
(0, eval)(assetSrc + "\\n" + introspectionSrc);

function findButton(node, label) {
  if (!node || node.nodeType !== 1) return null;
  if (node.tag === "button" &&
      node.children.some(c => c && c.nodeType === 3 && c.text === label)) {
    return node;
  }
  for (const child of node.children || []) {
    const found = findButton(child, label);
    if (found) return found;
  }
  return null;
}

function serialize(node) {
  if (node && node.nodeType === 3) return { kind: "text", text: node.text };
  if (!node || node.nodeType !== 1) return null;
  return {
    kind: "el", tag: node.tag, class: (node.attrs && node.attrs.class) || node.className || null,
    text: node.textContent, attrs: node.attrs,
    children: (node.children || []).map(serialize),
  };
}

const healthNode = renderHealth();
const statsNode = renderStats();

// Simulate clicking the "foo" tag chip before serialising — the click
// handler is a live closure that only exists on the un-serialised tree.
const chip = findButton(statsNode, "foo");
if (chip && chip.listeners.click) chip.listeners.click();
const tagClick = { loreQuery: window.LORE_QUERY, hash: window.location.hash };

const beforeFilterLines = __logEntryLines();
const logNode = renderLog();
// Snapshotted before any filter is fired: the filters now update logNode's
// own heading and <tbody> in place, so serialising it at the end of this
// script would capture the *filtered* table, not the pristine one.
const logSerialized = serialize(logNode);
const inboxNode = renderInbox();
const graphNode = renderGraph();

// Drive the filters the way a person would: pull the live (not yet
// serialised) control elements out of the filters row and fire the exact
// listener the browser would fire — change on the <select>/date inputs,
// input on the free-text box, one keystroke at a time.
const filtersRow = logNode.children[0];
const [verbSelect, fromInput, toInput, textInput] = filtersRow.children;

verbSelect.listeners.change({ target: { value: "ingest" } });
const logAfterVerb = serialize(logNode);          // same node, updated in place

textInput.listeners.input({ target: { value: "bbbb" } });
const logAfterText = serialize(logNode);
// The bug this pins: re-rendering the whole view through route() would swap
// in a brand-new <input>, and the browser blurs the node it removed. The
// element being typed into must still be the very same object, still in the
// filters row, after the results update.
const textInputSurvivedUpdate = filtersRow.children[3] === textInput;

// Clear both again, the way a person would, before the date-range case.
verbSelect.listeners.change({ target: { value: "" } });
textInput.listeners.input({ target: { value: "" } });

fromInput.listeners.change({ target: { value: "2026-02-01" } });
toInput.listeners.change({ target: { value: "2026-03-10" } });
const logAfterDateFilter = renderLog();

const afterFilterLines = __logEntryLines();

// renderMarkdown() over one representative page body, then the three views
// that had no executed coverage at all. renderPage() defers its mini graph
// behind requestAnimationFrame (stubbed inert), so graph.js is not needed;
// renderSearch() reads the header search box, which the tag chip click
// above already filled with "tag:foo".
const mdPage = pageById("concept-a");
const markdown = serialize(renderMarkdown(mdPage.body, mdPage));
const pageNode = serialize(renderPage("concept-a"));
const missingPageNode = serialize(renderPage("no-such-page"));
const browseNode = serialize(renderBrowse());
const searchNode = serialize(renderSearch());

process.stdout.write(JSON.stringify({
  markdown: markdown,
  page: pageNode,
  missingPage: missingPageNode,
  browse: browseNode,
  search: searchNode,
  searchBoxValue: searchBox.value,
  health: serialize(healthNode),
  stats: serialize(statsNode),
  chipFound: !!chip,
  tagClick: tagClick,
  log: logSerialized,
  inbox: serialize(inboxNode),
  graph: serialize(graphNode),
  logAfterVerb: logAfterVerb,
  logAfterText: logAfterText,
  textInputSurvivedUpdate: textInputSurvivedUpdate,
  logAfterDateFilter: serialize(logAfterDateFilter),
  logEntryLinesBefore: beforeFilterLines,
  logEntryLinesAfter: afterFilterLines,
}));
"""

# A representative payload covering, in LORE.health.dimensions: a dimension
# with a mix of clean and failing checks (Integrity: 3 clean, 2 failing),
# one where every check is clean (Schema: 2/2 clean), and one where none
# are (Connectivity: 0/2 clean) — the three branches of dimensionCard's
# clean/failing collapse. In LORE.stats: pages_by_type has rows with
# differing counts (8 and 2, both against max 8) to pin countTable's bar
# scaling by hand; pages_by_generator is deliberately empty to exercise
# countTable's "Nothing to show." fallback; tags includes "foo" to click.
#
# MARKDOWN_BODY is the one page body renderMarkdown() is pinned against. It
# exercises every construct the renderer has a branch for: an ATX heading, a
# paragraph carrying a wikilink, a [^id] footnote and a raw-HTML tag (which
# must come out as inert text), a fenced code block with a language, a
# pipe table, a two-level list, a plain blockquote, a ⚠ CONTRADICTION
# callout, and the "## My Take" heading that retargets everything after it
# into its own human-owned section.
MARKDOWN_BODY = """# Overview

Intro with a [[Wiki Page]] link, a footnote[^spec] and <b>raw html</b>.

```js
const x = 1;
```

| col a | col b |
| --- | --- |
| one | two |

- top level
  - nested one
- second top

> a plain quote

> ⚠ CONTRADICTION the spec says otherwise

## My Take

Human-owned commentary.
"""

RENDERED_VIEWS_PAYLOAD = {
    # Two full page records: renderPage() reads every frontmatter field, the
    # sources list, both link directions and the body; renderSearch() scores
    # over title/tags/description/body; renderMarkdown() resolves [[Wiki
    # Page]] against the second record and [^spec] against the first one's
    # sources[].
    "pages": [
        {"id": "concept-a", "title": "Concept A", "type": "concept", "status": "stable",
         "description": "what concept a is", "tags": ["foo"],
         "sources": [{"id": "spec", "resource": "raw/spec.pdf", "title": "The Spec",
                      "anchor": "", "href": "../raw/spec.pdf", "exists": True,
                      "abs": "/home/u/lore/raw/spec.pdf"}],
         "generated": {"by": "lore/test", "at": "2026-08-01"},
         "body": MARKDOWN_BODY, "outlinks": ["Wiki_Page"], "inlinks": [],
         "file": "wiki/concept-a.md", "href": "../wiki/concept-a.md",
         "abs": "/home/u/lore/wiki/concept-a.md"},
        {"id": "Wiki_Page", "title": "Wiki Page", "type": "source", "status": "deprecated",
         "description": "", "tags": [], "sources": [],
         "generated": {"by": "", "at": ""}, "body": "Plain body.",
         "outlinks": [], "inlinks": ["concept-a"],
         "file": "wiki/Wiki_Page.md", "href": "../wiki/Wiki_Page.md",
         "abs": "/home/u/lore/wiki/Wiki_Page.md"},
    ],
    # renderBrowse() reads only LORE.index: two groups (one of them the
    # ## Deprecated section, which must ship collapsed), one ghost entry
    # pointing at a file that does not exist, and no orphans.
    "index": {
        "line_count": 8, "entry_count": 3,
        "groups": [
            {"heading": "Concepts", "deprecated": False, "entries": [
                {"title": "Concept A", "target": "wiki/concept-a.md", "id": "concept-a",
                 "hook": "what concept a is", "chars": 60, "exists": True},
                {"title": "Gone", "target": "wiki/Gone.md", "id": "Gone",
                 "hook": "points nowhere", "chars": 40, "exists": False},
            ]},
            {"heading": "Deprecated", "deprecated": True, "entries": [
                {"title": "Wiki Page", "target": "wiki/Wiki_Page.md", "id": "Wiki_Page",
                 "hook": "", "chars": 40, "exists": True},
            ]},
        ],
        "orphans": [], "over_cap": [], "misplaced_deprecated": [],
        "ghost_entries": [{"title": "Gone", "target": "wiki/Gone.md"}],
    },
    # renderGraph() only reads LORE.graph.nodes to build its type/status/tag
    # filter <select>s — three nodes chosen to pin the exact option lists:
    # a "missing" ghost type (types include it, statuses filter it out since
    # its status is "" and .filter(Boolean) drops falsy entries), a
    # "deprecated" status, and one tag ("foo") to prove the tag <select> is
    # populated from LORE.graph.nodes.tags, not LORE.stats.tags.
    "graph": {
        "nodes": [
            {"id": "concept-a", "title": "Concept A", "type": "concept", "status": "stable",
             "tags": ["foo"], "ghost": False, "in": 3, "out": 1},
            {"id": "Wiki_Page", "title": "Wiki Page", "type": "source", "status": "deprecated",
             "tags": [], "ghost": False, "in": 0, "out": 0},
            {"id": "missing-target", "title": "Missing Target", "type": "missing", "status": "",
             "tags": [], "ghost": True, "in": 1, "out": 0},
        ],
        "edges": [{"source": "concept-a", "target": "Wiki_Page"},
                  {"source": "concept-a", "target": "missing-target"}],
        "components": 1,
        "isolated": [],
    },
    "health": {
        "score": 78,
        "last_lint": {"date": "2026-08-10", "fixed": 4, "reported": 2, "days": 14},
        "dimensions": [
            {   # mixed: 2 failing, 3 clean
                "key": "integrity", "label": "Integrity", "weight": 25, "score": 0.72,
                "checks": [
                    {"key": "orphans", "label": "Orphan pages", "score": 1.0, "offenders": []},
                    {"key": "ghost_entries", "label": "Ghost index entries", "score": 1.0,
                     "offenders": []},
                    {"key": "dead_wikilinks", "label": "Dead wikilinks", "score": 0.5,
                     "offenders": [{"ref": "concept-a", "kind": "page",
                                    "detail": "dead wikilinks: x"}]},
                    {"key": "duplicate_titles", "label": "Duplicate titles", "score": 0.6,
                     "offenders": [{"ref": "concept-a", "kind": "page",
                                    "detail": "title collides"}]},
                    {"key": "deprecated_placement", "label": "Deprecated pages misplaced",
                     "score": 1.0, "offenders": []},
                ],
            },
            {   # all clean
                "key": "schema", "label": "Schema", "weight": 20, "score": 1.0,
                "checks": [
                    {"key": "required_fields", "label": "Frontmatter fields", "score": 1.0,
                     "offenders": []},
                    {"key": "legacy_fields", "label": "Unsupported pre-0.3 fields", "score": 1.0,
                     "offenders": []},
                ],
            },
            {   # none clean
                "key": "connectivity", "label": "Connectivity", "weight": 15, "score": 0.15,
                "checks": [
                    {"key": "isolated", "label": "Isolated pages", "score": 0.0,
                     "offenders": [{"ref": "orphan-target", "kind": "page",
                                    "detail": "no inbound or outbound wikilinks"}]},
                    {"key": "no_inbound", "label": "Pages with no inbound link", "score": 0.3,
                     "offenders": [{"ref": "concept-a", "kind": "page",
                                    "detail": "no page links here"}]},
                ],
            },
        ],
    },
    "stats": {
        "pages_by_type": [{"key": "concept", "count": 8}, {"key": "source", "count": 2}],
        "pages_by_status": [{"key": "stable", "count": 6}, {"key": "draft", "count": 1}],
        "pages_by_generator": [],
        "raw_by_ext": [{"key": ".pdf", "count": 3, "bytes": 40000}],
        "raw_by_state": [{"key": "PROCESSED", "count": 3}],
        "raw_total_bytes": 40000,
        "coverage": {
            "raw_with_pages": 3, "raw_without_pages": 0,
            "pages_per_raw": [{"file": "notes.pdf", "count": 2}],
            "uncited": [],
        },
        "graph": {
            "nodes": 8, "pages": 7, "ghosts": 1, "edges": 10, "avg_degree": 2.5, "components": 1,
            "hubs": [{"id": "concept-a", "title": "Concept A", "count": 4}],
        },
        "tags": [{"key": "foo", "count": 5}, {"key": "bar", "count": 1}],
        "untagged": [],
        "log": {
            "by_verb": [{"key": "ingest", "count": 5}],
            "ingests_per_week": [{"week": "2026-W30", "count": 2}],
            "answers": 1, "discards": 0, "entries": 6, "malformed": 0,
        },
    },
    # LORE.log entries are supplied newest-first, exactly as parse_log()
    # sorts them (by (date, line) descending) — renderLog() must never
    # re-sort. The six entries below exercise, in order:
    #   1. "answer | Wiki Page" — subject with a space that maps (via
    #      s/ /_/) to the page id "Wiki_Page" above: the page-link branch.
    #   2. "skip | spec.pdf" — LORE.raw below has only "v2_spec.pdf", never
    #      an exact "spec.pdf" record; "spec.pdf" occurs *inside*
    #      "v2_spec.pdf" as a substring, so this pins the ledger's
    #      exact-basename-only matching rule and must fall through to
    #      plain text, not link to v2_spec.pdf.
    #   3. "ingest | Totally Unknown Thing" — matches neither a page nor a
    #      raw record at all: the third subjectNode() branch.
    #   4-6. three "notes.txt" ingest/skip entries at 2026-03-01, 2026-02-01
    #      and 2026-01-01 (newest first, as supplied) — LORE.raw has an
    #      exact "notes.txt" record (the raw-link branch), and the trio
    #      pins the per-file ledger's oldest-first inversion of this same
    #      newest-first order. 2026-02-01 and 2026-03-10 (entries 3 and 5)
    #      double as the inclusive from/to boundary dates for the
    #      date-range filter test.
    "log": {
        "entries": [
            {"line": 60, "date": "2026-04-01", "verb": "answer", "subject": "Wiki Page",
             "detail": "promoted from source review", "sha": None, "fixed": None, "reported": None},
            {"line": 55, "date": "2026-03-20", "verb": "skip", "subject": "spec.pdf",
             "detail": "duplicate of v2_spec.pdf", "sha": None, "fixed": None, "reported": None},
            {"line": 50, "date": "2026-03-10", "verb": "ingest", "subject": "Totally Unknown Thing",
             "detail": "no matching page or raw file", "sha": None, "fixed": None, "reported": None},
            {"line": 45, "date": "2026-03-01", "verb": "ingest", "subject": "notes.txt",
             "detail": "sha256:aaaaaaaaaaaa", "sha": "aaaaaaaaaaaa", "fixed": None, "reported": None},
            {"line": 40, "date": "2026-02-01", "verb": "skip", "subject": "notes.txt",
             "detail": "too large to process", "sha": None, "fixed": None, "reported": None},
            {"line": 35, "date": "2026-01-01", "verb": "ingest", "subject": "notes.txt",
             "detail": "sha256:bbbbbbbbbbbb", "sha": "bbbbbbbbbbbb", "fixed": None, "reported": None},
        ],
        "malformed": [{"line": 12, "text": "## nope missing pipe"}],
        "last_lint": None,
    },
    # Deliberately NOT in NEW/CHANGED/SKIPPED/PROCESSED order and NOT
    # alphabetical either — renderInbox() must preserve exactly this order
    # (scan_raw() already put NEW/CHANGED first; the view must not re-sort).
    "raw": [
        {"name": "v2_spec.pdf", "ext": ".pdf", "size": 9000, "sha": "ccc111222333",
         "state": "CHANGED", "latest_date": "2026-03-20", "skip_reason": None, "pages": [],
         "href": "../raw/v2_spec.pdf", "abs": "/home/u/lore/raw/v2_spec.pdf"},
        {"name": "notes.txt", "ext": ".txt", "size": 512, "sha": "aaaaaaaaaaaa",
         "state": "NEW", "latest_date": "2026-03-01", "skip_reason": None, "pages": [],
         "href": "../raw/notes.txt", "abs": "/home/u/lore/raw/notes.txt"},
        {"name": "old_batch.md", "ext": ".md", "size": 100, "sha": "dead00dead00",
         "state": "SKIPPED", "latest_date": "2026-01-01", "skip_reason": "too niche",
         "pages": [], "href": "../raw/old_batch.md", "abs": "/home/u/lore/raw/old_batch.md"},
        {"name": "chart.xlsx", "ext": ".xlsx", "size": 30000, "sha": "eee444555666",
         "state": "NEW", "latest_date": None, "skip_reason": None, "pages": [],
         "href": "../raw/chart.xlsx", "abs": "/home/u/lore/raw/chart.xlsx"},
        {"name": "report.csv", "ext": ".csv", "size": 2048, "sha": "fff777888999",
         "state": "PROCESSED", "latest_date": "2026-01-05", "skip_reason": None,
         "pages": ["Wiki_Page"], "href": "../raw/report.csv", "abs": "/home/u/lore/raw/report.csv"},
    ],
}

# Same shape, but log.entries/log.malformed/raw are all empty — exercises
# the "Every heading parses.", "No ingest or skip entries yet." and
# "raw/ is empty." fallbacks, none of which the non-empty payload above
# ever takes.
EMPTY_LOG_PAYLOAD = {**RENDERED_VIEWS_PAYLOAD,
                     "log": {"entries": [], "malformed": [], "last_lint": None},
                     "raw": []}


def _rv_all_text(node):
    """Concatenate every text/mark leaf under a serialised node."""
    if node is None:
        return ""
    if node.get("kind") == "text":
        return node.get("text") or ""
    parts = [node.get("text") or ""]
    for child in node.get("children") or []:
        parts.append(_rv_all_text(child))
    return "".join(parts)


def _rv_find_all(node, predicate):
    """Depth-first search over a serialised node tree for matching elements."""
    if node is None or node.get("kind") != "el":
        return
    if predicate(node):
        yield node
    for child in node.get("children") or []:
        yield from _rv_find_all(child, predicate)


def _rv_count_table_div(root, title):
    """The countTable() wrapper <div> whose first child is <h3 text=title>."""
    for div in _rv_find_all(root, lambda n: n.get("tag") == "div"):
        kids = [c for c in (div.get("children") or []) if c and c.get("kind") == "el"]
        if kids and kids[0].get("tag") == "h3" and kids[0].get("text") == title:
            return div
    return None


def _rv_direct_table_rows(node):
    """The <tbody> rows of the <table> that is a direct child of `node`."""
    table = next(c for c in node["children"] if c and c.get("tag") == "table")
    tbody = next(c for c in table["children"] if c.get("tag") == "tbody")
    return tbody["children"]


def _rv_ledger_groups(log_tree):
    """{raw filename: [row date, ...]} for each per-file <details class="tree">
    ledger block under the Log view, in the order its rows render."""
    groups = {}
    for details in _rv_find_all(log_tree, lambda n: n.get("tag") == "details"
                                                      and n.get("class") == "tree"):
        summary = next(c for c in details["children"] if c.get("tag") == "summary")
        name = _rv_all_text(summary["children"][0])
        rows = _rv_direct_table_rows(details)
        groups[name] = [row["children"][0]["text"] for row in rows]
    return groups


@unittest.skipUnless(shutil.which("node"), "node not installed — rendered-view check skipped")
class TestRenderedViews(unittest.TestCase):
    def _render(self, payload=None):
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "run_rendered_views.js"
            payload_path = Path(tmp) / "payload.json"
            runner.write_text(RENDERED_VIEWS_RUNNER_JS, encoding="utf-8")
            payload_path.write_text(json.dumps(payload if payload is not None
                                                else RENDERED_VIEWS_PAYLOAD), encoding="utf-8")
            result = subprocess.run(
                ["node", str(runner), str(payload_path)]
                + [str(ASSETS_DIR / name)
                   for name in ("core.js", "md.js", "search.js", "views.js")],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_dimension_with_mixed_checks_collapses_clean_ones_and_lists_failing_ones(self):
        out = self._render()
        dimensions = list(_rv_find_all(
            out["health"], lambda n: n.get("tag") == "section" and n.get("class") == "dimension"))
        self.assertEqual(len(dimensions), 3)
        mixed = dimensions[0]
        details = list(_rv_find_all(mixed, lambda n: n.get("tag") == "details"
                                                      and n.get("class") == "check"))
        self.assertEqual(len(details), 2)
        text = _rv_all_text(mixed)
        self.assertIn("Dead wikilinks", text)
        self.assertIn("Duplicate titles", text)
        self.assertIn("3 other check(s) clean.", text)
        self.assertNotIn("All 5 checks clean.", text)

    def test_dimension_with_all_checks_clean_collapses_to_one_line_with_no_details(self):
        out = self._render()
        dimensions = list(_rv_find_all(
            out["health"], lambda n: n.get("tag") == "section" and n.get("class") == "dimension"))
        clean_dim = dimensions[1]
        details = list(_rv_find_all(clean_dim, lambda n: n.get("tag") == "details"))
        self.assertEqual(details, [])
        text = _rv_all_text(clean_dim)
        self.assertIn("All 2 checks clean.", text)
        self.assertNotIn("other check(s) clean", text)

    def test_dimension_with_no_checks_clean_lists_all_and_omits_the_clean_line(self):
        out = self._render()
        dimensions = list(_rv_find_all(
            out["health"], lambda n: n.get("tag") == "section" and n.get("class") == "dimension"))
        none_clean = dimensions[2]
        details = list(_rv_find_all(none_clean, lambda n: n.get("tag") == "details"
                                                           and n.get("class") == "check"))
        self.assertEqual(len(details), 2)
        text = _rv_all_text(none_clean)
        self.assertNotIn("other check(s) clean", text)
        self.assertNotIn("All 2 checks clean.", text)

    def test_lint_line_and_standing_judgment_note_are_present(self):
        out = self._render()
        text = _rv_all_text(out["health"])
        self.assertIn("Last lint 2026-08-10 (14 days ago): 4 fixed, 2 reported.", text)
        self.assertIn("Judgment checks (not scored)", text)
        self.assertIn(
            "Active contradiction cross-check, footnote-discipline judgment, missing concept "
            "pages, missing cross-references, knowledge gaps and discard candidates need the "
            "agent; they are never computed here.", text)

    def test_count_table_scales_bars_against_the_largest_row(self):
        out = self._render()
        div = _rv_count_table_div(out["stats"], "By type")
        self.assertIsNotNone(div)
        table = next(c for c in div["children"] if c.get("tag") == "table")
        tbody = next(c for c in table["children"] if c.get("tag") == "tbody")
        rows = tbody["children"]
        self.assertEqual(len(rows), 2)
        widths = []
        for row in rows:
            bar_td = row["children"][2]
            svg = bar_td["children"][0]
            filled_rect = svg["children"][1]
            widths.append(filled_rect["attrs"]["width"])
        # Hand-derived from the stated rule (filled = count/max * 120px
        # track), never obtained by calling countTable/bar and copying the
        # result: count 8 of max 8 -> fraction 1 -> full 120px track; count
        # 2 of max 8 -> fraction 0.25 -> 30px. Both fractions are exact
        # powers of two, so there is no floating-point rounding to resolve.
        self.assertEqual(widths, [120, 30])

    def test_count_table_empty_rows_renders_the_empty_fallback(self):
        out = self._render()
        div = _rv_count_table_div(out["stats"], "By generator")
        self.assertIsNotNone(div)
        self.assertEqual([c.get("tag") for c in div["children"]], ["h3", "p"])
        fallback = div["children"][1]
        self.assertEqual(fallback.get("class"), "empty")
        self.assertEqual(fallback.get("text"), "Nothing to show.")

    def test_tag_chip_click_queries_search_by_tag_and_navigates(self):
        out = self._render()
        self.assertTrue(out["chipFound"], "no chip labelled 'foo' was found in the tags table")
        self.assertEqual(out["tagClick"], {"loreQuery": "tag:foo", "hash": "#search"})

    def test_log_table_is_newest_first_and_the_count_line_matches(self):
        out = self._render()
        rows = _rv_direct_table_rows(out["log"])
        dates = [row["children"][0]["text"] for row in rows]
        self.assertEqual(dates, ["2026-04-01", "2026-03-20", "2026-03-10",
                                 "2026-03-01", "2026-02-01", "2026-01-01"])
        h2 = next(c for c in out["log"]["children"] if c.get("tag") == "h2")
        self.assertEqual(h2["text"], "6 of 6 entries")

    def test_subject_links_to_a_page_when_the_spaced_subject_matches_a_page_id(self):
        out = self._render()
        rows = _rv_direct_table_rows(out["log"])
        subject = rows[0]["children"][2]["children"][0]   # "answer | Wiki Page"
        self.assertEqual(subject["tag"], "a")
        self.assertEqual(subject["attrs"].get("href"), "#page/Wiki_Page")
        self.assertEqual(_rv_all_text(subject), "Wiki Page")

    def test_subject_links_to_the_raw_href_on_an_exact_basename_match(self):
        out = self._render()
        rows = _rv_direct_table_rows(out["log"])
        subject = rows[3]["children"][2]["children"][0]   # "ingest | notes.txt" 2026-03-01
        self.assertEqual(subject["tag"], "a")
        self.assertEqual(subject["class"], "mono")
        self.assertEqual(subject["attrs"].get("href"), "../raw/notes.txt")
        self.assertEqual(_rv_all_text(subject), "notes.txt")

    def test_subject_matching_never_treats_a_basename_as_a_substring(self):
        # LORE.raw only has "v2_spec.pdf"; "spec.pdf" occurs inside that
        # name but a substring-based lookup would wrongly link this cell to
        # v2_spec.pdf's href. It must fall through to plain, unlinked text.
        out = self._render()
        rows = _rv_direct_table_rows(out["log"])
        subject = rows[1]["children"][2]["children"][0]   # "skip | spec.pdf"
        self.assertEqual(subject["tag"], "span")
        self.assertEqual(subject["text"], "spec.pdf")

    def test_subject_matching_neither_page_nor_raw_renders_plain_text(self):
        out = self._render()
        rows = _rv_direct_table_rows(out["log"])
        subject = rows[2]["children"][2]["children"][0]   # "ingest | Totally Unknown Thing"
        self.assertEqual(subject["tag"], "span")
        self.assertEqual(subject["text"], "Totally Unknown Thing")

    def test_malformed_lines_show_raw_text_flagged_with_their_line_number(self):
        out = self._render()
        [li] = list(_rv_find_all(out["log"], lambda n: n.get("tag") == "li"
                                                        and n.get("class") == "mono dead"))
        self.assertEqual(li["text"], "log.md:12  ## nope missing pipe")
        headings = [c["text"] for c in out["log"]["children"] if c.get("tag") == "h2"]
        self.assertIn("Malformed lines (1)", headings)

    def test_no_malformed_lines_and_no_ledger_entries_render_their_fallbacks(self):
        out = self._render(EMPTY_LOG_PAYLOAD)
        headings = [c["text"] for c in out["log"]["children"] if c.get("tag") == "h2"]
        self.assertIn("Malformed lines (0)", headings)
        fallbacks = [c["text"] for c in out["log"]["children"]
                     if c.get("tag") == "p" and c.get("class") == "empty"]
        self.assertIn("Every heading parses.", fallbacks)
        self.assertIn("No ingest or skip entries yet.", fallbacks)

    def test_per_file_ledger_lists_that_files_entries_oldest_first(self):
        # The main table above (asserted newest-first, separately) supplies
        # these same three notes.txt rows in the exact opposite order —
        # this is the inversion a naive "just reuse the same list" bug
        # would get backwards.
        out = self._render()
        groups = _rv_ledger_groups(out["log"])
        self.assertEqual(groups["notes.txt"], ["2026-01-01", "2026-02-01", "2026-03-01"])

    def test_verb_select_and_free_text_box_filter_the_table_in_place(self):
        # Fired as a person fires them: change on the verb <select>, then
        # input on the free-text box, both on the live tree — no re-render
        # in between. Before the fix these called route(), which rebuilt the
        # whole view: nothing at all happened to the tree the person was
        # looking at (route is inert here), and in a browser the <input>
        # being typed into was removed and replaced, so it lost focus and
        # its caret after every keystroke.
        out = self._render()
        after_verb = [row["children"][0]["text"]
                      for row in _rv_direct_table_rows(out["logAfterVerb"])]
        # verb=ingest keeps entries 3, 4 and 6; the two skips and the answer go.
        self.assertEqual(after_verb, ["2026-03-10", "2026-03-01", "2026-01-01"])
        verb_h2 = next(c for c in out["logAfterVerb"]["children"] if c.get("tag") == "h2")
        self.assertEqual(verb_h2["text"], "3 of 6 entries")

        after_text = [row["children"][0]["text"]
                      for row in _rv_direct_table_rows(out["logAfterText"])]
        # "bbbb" occurs only in entry 6's sha256 detail, and the verb filter
        # is still applied on top of it — the two compose.
        self.assertEqual(after_text, ["2026-01-01"])
        text_h2 = next(c for c in out["logAfterText"]["children"] if c.get("tag") == "h2")
        self.assertEqual(text_h2["text"], "1 of 6 entries")

        # ...and the box that was typed into is still the very same element,
        # still sitting in the filters row: a whole-view re-render would have
        # built a replacement, and a browser blurs the node it removes.
        self.assertTrue(out["textInputSurvivedUpdate"],
                        "the <input> being typed into was replaced by the filter update")

    def test_the_per_file_ledger_table_labels_its_columns_like_the_main_one(self):
        out = self._render()
        details = list(_rv_find_all(out["log"], lambda n: n.get("tag") == "details"
                                                           and n.get("class") == "tree"))
        self.assertTrue(details)
        for block in details:
            table = next(c for c in block["children"] if c.get("tag") == "table")
            thead = next(c for c in table["children"] if c.get("tag") == "thead")
            row = thead["children"][0]
            self.assertEqual([cell["text"] for cell in row["children"]],
                             ["date", "verb", "subject", "detail"])

    def test_date_range_filter_is_inclusive_of_entries_exactly_on_from_and_to(self):
        out = self._render()
        rows = _rv_direct_table_rows(out["logAfterDateFilter"])
        dates = [row["children"][0]["text"] for row in rows]
        # from=2026-02-01 is entry 5's own date and to=2026-03-10 is entry
        # 3's own date — both boundary entries are included; 2026-03-20 and
        # 2026-01-01, just outside either edge, are excluded.
        self.assertEqual(dates, ["2026-03-10", "2026-03-01", "2026-02-01"])
        h2 = next(c for c in out["logAfterDateFilter"]["children"] if c.get("tag") == "h2")
        self.assertEqual(h2["text"], "3 of 6 entries")

    def test_filtering_the_log_view_never_mutates_the_payloads_entries_array(self):
        out = self._render()
        self.assertEqual(out["logEntryLinesBefore"], [60, 55, 50, 45, 40, 35])
        self.assertEqual(out["logEntryLinesAfter"], out["logEntryLinesBefore"])

    def test_inbox_summary_line_counts_every_state(self):
        out = self._render()
        h2 = next(c for c in out["inbox"]["children"] if c.get("tag") == "h2")
        self.assertEqual(h2["text"], "raw/ — 5 file(s): 2 NEW · 1 CHANGED · 1 SKIPPED · 1 PROCESSED")

    def test_inbox_table_preserves_payload_order_instead_of_resorting(self):
        out = self._render()
        rows = _rv_direct_table_rows(out["inbox"])
        names = [_rv_all_text(next(_rv_find_all(row["children"][0], lambda n: n.get("tag") == "a")))
                 for row in rows]
        # Payload order, not alphabetical (chart, notes, old_batch, report,
        # v2_spec) and not grouped by state.
        self.assertEqual(names, ["v2_spec.pdf", "notes.txt", "old_batch.md",
                                 "chart.xlsx", "report.csv"])
        states = [_rv_all_text(row["children"][3]) for row in rows]
        self.assertEqual(states, ["CHANGED", "NEW", "SKIPPED", "NEW", "PROCESSED"])
        skip_reason = rows[2]["children"][6]["text"]
        self.assertEqual(skip_reason, "too niche")
        pages_link = next(_rv_find_all(rows[4]["children"][5], lambda n: n.get("tag") == "a"))
        self.assertEqual(pages_link["attrs"].get("href"), "#page/Wiki_Page")

    def test_empty_raw_renders_its_fallback_and_a_zero_count_summary(self):
        out = self._render(EMPTY_LOG_PAYLOAD)
        h2 = next(c for c in out["inbox"]["children"] if c.get("tag") == "h2")
        self.assertEqual(h2["text"], "raw/ — 0 file(s): empty")
        fallback = next(c for c in out["inbox"]["children"] if c.get("tag") == "p")
        self.assertEqual((fallback["class"], fallback["text"]), ("empty", "raw/ is empty."))

    # -- graph tab controls (the DOM-buildable half; initGraph/canvas is
    #    covered separately in TestGraphPureFunctions/TestGraphLifecycle) ---

    def test_graph_view_filter_selects_are_populated_from_graph_nodes(self):
        out = self._render()
        selects = list(_rv_find_all(out["graph"], lambda n: n.get("tag") == "select"))
        self.assertEqual(len(selects), 4)   # type, status, tag, hops

        def option_texts(select):
            return [c.get("text") for c in select["children"] if c.get("tag") == "option"]

        # types includes "missing" (the ghost node's type); statuses drops
        # the ghost's "" status via .filter(Boolean); tags comes from
        # LORE.graph.nodes, not LORE.stats.tags.
        self.assertEqual(option_texts(selects[0]), ["type: all", "concept", "missing", "source"])
        self.assertEqual(option_texts(selects[1]), ["status: all", "deprecated", "stable"])
        self.assertEqual(option_texts(selects[2]), ["tag: all", "foo"])
        self.assertEqual(option_texts(selects[3]), ["1 hop(s)", "2 hop(s)", "3 hop(s)"])

    def test_hide_deprecated_checkbox_defaults_checked_and_focus_checkbox_does_not(self):
        # Pins the exact polarity the brief flagged as a likely error site:
        # "hide deprecated" ships checked (the payload's one deprecated node
        # is hidden until a person opts in to see it), "focus on click"
        # ships unchecked (clicking a node navigates by default).
        out = self._render()
        checkboxes = list(_rv_find_all(
            out["graph"], lambda n: n.get("tag") == "input" and n["attrs"].get("type") == "checkbox"))
        self.assertEqual(len(checkboxes), 2)
        hide_deprecated, focus_on_click = checkboxes
        self.assertEqual(hide_deprecated["attrs"].get("checked"), "")
        self.assertNotIn("checked", focus_on_click["attrs"])

    def test_graph_view_has_a_dimming_search_box_and_a_clear_focus_button(self):
        out = self._render()
        search_inputs = list(_rv_find_all(
            out["graph"], lambda n: n.get("tag") == "input" and n["attrs"].get("type") == "search"))
        self.assertEqual(len(search_inputs), 1)
        self.assertEqual(search_inputs[0]["attrs"].get("placeholder"), "dim non-matching")

        buttons = list(_rv_find_all(out["graph"], lambda n: n.get("tag") == "button"))
        self.assertEqual([_rv_all_text(b) for b in buttons], ["clear focus"])

    def test_graph_view_is_registered_and_mounts_a_canvas_host(self):
        out = self._render()
        hosts = list(_rv_find_all(out["graph"], lambda n: n.get("class") == "graph-host"))
        self.assertEqual(len(hosts), 1)

    # -- renderMarkdown, and the page/browse/search views ------------------
    #    md.js is the largest and most security-sensitive JS here: ~180
    #    lines of stateful line-scanning over a page body, which is
    #    untrusted content. Everything below runs the real renderer against
    #    MARKDOWN_BODY and pins the tree it produces.

    def test_markdown_block_structure_is_pinned_end_to_end(self):
        out = self._render()
        blocks = [(c["tag"], c.get("class")) for c in out["markdown"]["children"]]
        self.assertEqual(blocks, [
            ("h2", None),                       # "# Overview": rendered one level down
            ("p", None),
            ("pre", None),
            ("table", None),
            ("ul", None),
            ("blockquote", None),
            ("div", "callout contradiction"),
            ("section", "my-take"),
        ])

    def test_markdown_inline_wikilink_and_footnote_resolve_against_the_page(self):
        out = self._render()
        paragraph = out["markdown"]["children"][1]
        link = next(_rv_find_all(paragraph, lambda n: n.get("class") == "wikilink"))
        self.assertEqual(link["attrs"].get("href"), "#page/Wiki_Page")
        self.assertEqual(_rv_all_text(link), "Wiki Page")     # spaces -> underscores in the id
        footnote = next(_rv_find_all(paragraph, lambda n: n.get("tag") == "sup"))
        self.assertEqual(footnote["class"], "fn")             # "fn dead" if sources[] lacked it
        anchor = footnote["children"][0]
        self.assertEqual(anchor["attrs"].get("href"), "../raw/spec.pdf")
        self.assertEqual(anchor["attrs"].get("title"), "raw/spec.pdf")
        self.assertEqual(_rv_all_text(anchor), "spec")

    def test_raw_html_in_a_body_renders_as_inert_text(self):
        # The whole point of building this tree with el()/textContent: a page
        # body is untrusted, so "<b>raw html</b>" must survive as characters
        # in a text node and never become an element.
        out = self._render()
        self.assertIn("<b>raw html</b>", _rv_all_text(out["markdown"]))
        self.assertEqual(list(_rv_find_all(out["markdown"], lambda n: n.get("tag") == "b")), [])

    def test_markdown_fence_table_and_nested_list(self):
        out = self._render()
        pre, table, unordered = (out["markdown"]["children"][i] for i in (2, 3, 4))
        self.assertEqual(pre["attrs"].get("data-lang"), "js")
        self.assertEqual(pre["children"][0]["tag"], "code")
        self.assertEqual(pre["children"][0]["text"], "const x = 1;")

        head_row = table["children"][0]["children"][0]
        self.assertEqual([_rv_all_text(cell) for cell in head_row["children"]], ["col a", "col b"])
        body_rows = table["children"][1]["children"]
        # The separator row is consumed, never rendered as data.
        self.assertEqual([[_rv_all_text(c) for c in row["children"]] for row in body_rows],
                         [["one", "two"]])

        first, second = unordered["children"]
        self.assertEqual(first["children"][0]["text"], "top level")
        nested = first["children"][1]
        self.assertEqual(nested["tag"], "ul")            # nested inside its parent <li>
        self.assertEqual(_rv_all_text(nested), "nested one")
        self.assertEqual(_rv_all_text(second), "second top")

    def test_markdown_quote_callout_and_my_take_retargeting(self):
        out = self._render()
        quote, callout, my_take = (out["markdown"]["children"][i] for i in (5, 6, 7))
        self.assertEqual(_rv_all_text(quote), "a plain quote")
        # The ⚠ marker is lifted into its own <strong> and stripped from the
        # quoted text, and the block becomes a callout div, not a blockquote.
        self.assertEqual(callout["children"][0]["text"], "⚠ ")
        self.assertEqual(_rv_all_text(callout), "⚠ CONTRADICTION the spec says otherwise")
        # Everything after the "## My Take" heading is retargeted into the
        # human-owned section rather than continuing at the top level — which
        # is why the fragment above has exactly 8 children, not 9.
        self.assertEqual([c["tag"] for c in my_take["children"]], ["h3", "p", "p"])
        self.assertEqual(my_take["children"][0]["text"], "My Take")
        self.assertEqual(my_take["children"][1]["text"],
                         "human-owned — the agent never edits this")
        self.assertEqual(_rv_all_text(my_take["children"][2]), "Human-owned commentary.")

    def test_page_view_embeds_the_rendered_body_and_both_link_directions(self):
        out = self._render()
        body = next(_rv_find_all(out["page"], lambda n: n.get("class") == "md"))
        # The fragment's blocks are spliced into <section class="md">, not
        # wrapped in another node.
        self.assertEqual([c["tag"] for c in body["children"]],
                         [c["tag"] for c in out["markdown"]["children"]])
        self.assertEqual([c["text"] for c in out["page"]["children"] if c.get("tag") == "h3"],
                         ["Sources", "Linked from (0)", "Links to (1)", "Health flags"])
        outbound = out["page"]["children"][10]
        self.assertEqual(outbound["class"], "linklist")
        self.assertEqual(next(_rv_find_all(outbound, lambda n: n.get("tag") == "a"))
                         ["attrs"].get("href"), "#page/Wiki_Page")
        flags = [li["text"] for li in _rv_find_all(out["page"]["children"][12],
                                                   lambda n: n.get("tag") == "li")]
        self.assertEqual(flags, ["Integrity · Dead wikilinks — dead wikilinks: x",
                                 "Integrity · Duplicate titles — title collides",
                                 "Connectivity · Pages with no inbound link — no page links here"])

    def test_page_view_for_an_unknown_id_is_an_empty_notice(self):
        out = self._render()
        missing = out["missingPage"]
        self.assertEqual((missing["tag"], missing["class"], missing["text"]),
                         ("p", "empty", "No page with id no-such-page"))

    def test_browse_view_renders_groups_a_ghost_entry_and_the_index_header(self):
        out = self._render()
        header = out["browse"]["children"][0]
        self.assertEqual(header["text"], "index.md — 3 entries, 8 lines")
        details = list(_rv_find_all(out["browse"], lambda n: n.get("tag") == "details"))
        self.assertEqual([_rv_all_text(d["children"][0]) for d in details],
                         ["Concepts  2", "Deprecated  1"])
        self.assertEqual(details[0]["attrs"].get("open"), "")
        self.assertNotIn("open", details[1]["attrs"])   # ## Deprecated ships collapsed
        # The entry pointing at a missing file is inert text plus a note —
        # never a link into a page route that cannot resolve.
        ghost_entry = details[0]["children"][1]["children"][1]
        self.assertEqual(list(_rv_find_all(ghost_entry, lambda n: n.get("tag") == "a")), [])
        self.assertEqual(_rv_all_text(ghost_entry), "Gone — points nowhere (missing file)")

    def test_search_view_runs_the_query_a_tag_chip_click_left_behind(self):
        out = self._render()
        self.assertEqual(out["searchBoxValue"], "tag:foo")
        heading = next(c for c in out["search"]["children"] if c.get("tag") == "h2")
        self.assertEqual(heading["text"], "1 result(s) for “tag:foo”")
        results = next(c for c in out["search"]["children"] if c.get("class") == "results")
        [result] = results["children"]
        self.assertEqual(next(_rv_find_all(result, lambda n: n.get("tag") == "a"))
                         ["attrs"].get("href"), "#page/concept-a")
        self.assertIn("matched in tags", _rv_all_text(result))
        # No body match for a tag: term, so the snippet falls back to the
        # page description.
        snippet = next(_rv_find_all(result, lambda n: n.get("class") == "muted snippet"))
        self.assertEqual(_rv_all_text(snippet), "what concept a is")


if __name__ == "__main__":
    unittest.main()
