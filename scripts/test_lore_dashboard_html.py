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

    def test_neither_asset_uses_innerhtml_outerhtml_document_write_or_eval(self):
        # Global constraint (not just md.js): page bodies are untrusted
        # content, and every node in the page view must be built via
        # el()/textContent — never through string-based HTML injection
        # or eval, in either file that renders the page view.
        for name in ("md.js", "views.js"):
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


if __name__ == "__main__":
    unittest.main()
