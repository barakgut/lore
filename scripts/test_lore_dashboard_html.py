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
        self.assertNotIn("http://", page)
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
    # allowed: what a real lore page actually links to
    ("../wiki/Some_Page.md", "../wiki/Some_Page.md"),
    ("raw/spec.pdf", "raw/spec.pdf"),
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


if __name__ == "__main__":
    unittest.main()
