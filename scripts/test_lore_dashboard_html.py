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


@unittest.skipUnless(shutil.which("node"), "node not installed — JS syntax check skipped")
class TestJsSyntax(unittest.TestCase):
    def test_every_js_asset_parses(self):
        for name in JS_ASSETS:
            result = subprocess.run(["node", "--check", str(ASSETS_DIR / name)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
