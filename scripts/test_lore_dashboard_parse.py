"""Tests for lore_dashboard_parse.py — run with: python3 -m unittest discover scripts"""
import tempfile
import unittest
from pathlib import Path

from lore_dashboard_parse import (
    link_target_id,
    load_pages,
    parse_frontmatter,
    parse_yaml_block,
)

FULL_FM = """\
type: concept
title: Link Setup Frame
description: How the link comes up
tags: [rf, protocol]
sources:
  - id: spec
    resource: raw/spec.pdf#p12
    title: The Spec
  - id: sheet
    resource: raw/budget.xlsx#Sheet1
generated:
  by: lore/claude-opus-5
  at: 2026-08-20
status: draft
"""


def make_lore(pages: dict) -> Path:
    """A throwaway lore with wiki/ pages. pages: {filename: file content}."""
    root = Path(tempfile.mkdtemp())
    (root / "wiki").mkdir()
    (root / "raw").mkdir()
    (root / "index.md").write_text("# Lore Index\n")
    (root / "log.md").write_text("# Lore Log\n")
    for name, content in pages.items():
        (root / "wiki" / name).write_text(content)
    return root


def page_file(title, ptype="concept", body="", extra="") -> str:
    return (f"---\ntype: {ptype}\ntitle: {title}\n"
            f"description: about {title}\ntags: [x]\n"
            f"generated:\n  by: lore/test\n  at: 2026-08-01\n{extra}---\n\n{body}\n")


class TestYamlBlock(unittest.TestCase):
    def test_scalars_lists_and_nested_maps(self):
        fm = parse_yaml_block(FULL_FM)
        self.assertEqual(fm["type"], "concept")
        self.assertEqual(fm["title"], "Link Setup Frame")
        self.assertEqual(fm["tags"], ["rf", "protocol"])
        self.assertEqual(fm["generated"], {"by": "lore/claude-opus-5", "at": "2026-08-20"})
        self.assertEqual(fm["status"], "draft")

    def test_sources_is_a_list_of_dicts_keeping_anchors(self):
        fm = parse_yaml_block(FULL_FM)
        self.assertEqual(fm["sources"][0],
                         {"id": "spec", "resource": "raw/spec.pdf#p12", "title": "The Spec"})
        self.assertEqual(fm["sources"][1]["resource"], "raw/budget.xlsx#Sheet1")

    def test_block_style_tags_list(self):
        fm = parse_yaml_block("tags:\n  - rf\n  - protocol\n")
        self.assertEqual(fm["tags"], ["rf", "protocol"])

    def test_quotes_are_stripped_and_trailing_comments_removed(self):
        fm = parse_yaml_block('title: "Quoted Title"   # a comment\n')
        self.assertEqual(fm["title"], "Quoted Title")

    def test_hash_inside_a_value_is_not_a_comment(self):
        fm = parse_yaml_block("resource: raw/spec.pdf#p12\n")
        self.assertEqual(fm["resource"], "raw/spec.pdf#p12")

    def test_unknown_and_legacy_fields_are_kept_verbatim(self):
        fm = parse_yaml_block("captured: 2025-01-01\ntrust: high\n")
        self.assertEqual(fm["captured"], "2025-01-01")
        self.assertEqual(fm["trust"], "high")


class TestParseFrontmatter(unittest.TestCase):
    def test_splits_fields_from_body(self):
        fields, body, ok = parse_frontmatter("---\ntitle: A\n---\n\nbody text\n")
        self.assertTrue(ok)
        self.assertEqual(fields["title"], "A")
        self.assertEqual(body.strip(), "body text")

    def test_missing_frontmatter_is_not_ok_and_keeps_whole_text_as_body(self):
        fields, body, ok = parse_frontmatter("no frontmatter here\n")
        self.assertFalse(ok)
        self.assertEqual(fields, {})
        self.assertEqual(body.strip(), "no frontmatter here")

    def test_unterminated_frontmatter_is_not_ok(self):
        _, _, ok = parse_frontmatter("---\ntitle: A\nbody with no closing marker\n")
        self.assertFalse(ok)


class TestLinkTargetId(unittest.TestCase):
    def test_spaces_alias_and_anchor_resolve_to_the_page_id(self):
        self.assertEqual(link_target_id("Link Setup Frame"), "Link_Setup_Frame")
        self.assertEqual(link_target_id("Power Budget|the budget"), "Power_Budget")
        self.assertEqual(link_target_id("Power Budget#section"), "Power_Budget")
        self.assertEqual(link_target_id("  Spaced  "), "Spaced")


class TestLoadPages(unittest.TestCase):
    def test_one_record_per_wiki_page_sorted_by_id(self):
        lore = make_lore({"B_Page.md": page_file("B Page"), "A_Page.md": page_file("A Page")})
        pages = load_pages(lore)
        self.assertEqual([p["id"] for p in pages], ["A_Page", "B_Page"])
        self.assertEqual(pages[0]["file"], "wiki/A_Page.md")

    def test_outlinks_are_deduped_resolved_ids_in_order(self):
        lore = make_lore({"A.md": page_file("A", body="[[B]] then [[B|again]] and [[C Page#x]]")})
        self.assertEqual(load_pages(lore)[0]["outlinks"], ["B", "C_Page"])

    def test_body_markers_are_counted(self):
        body = ("claim one[^spec] and two[^sheet]\n\n"
                "> ⚠ CONTRADICTION: A says 5 [[S_A]]; B says 6 [[S_B]]\n\n"
                "## My Take\nmine\n")
        lore = make_lore({"A.md": page_file("A", body=body)})
        p = load_pages(lore)[0]
        self.assertEqual(p["footnote_ids"], ["spec", "sheet"])
        self.assertEqual(p["contradictions"], 1)
        self.assertTrue(p["my_take"])

    def test_status_defaults_to_stable_when_absent(self):
        lore = make_lore({"A.md": page_file("A")})
        self.assertEqual(load_pages(lore)[0]["status"], "stable")

    def test_malformed_page_falls_back_without_raising(self):
        lore = make_lore({"Odd_Page.md": "no frontmatter at all\n"})
        p = load_pages(lore)[0]
        self.assertFalse(p["fm_ok"])
        self.assertEqual(p["title"], "Odd Page")
        self.assertEqual(p["type"], "")
        self.assertEqual(p["tags"], [])
        self.assertEqual(p["sources"], [])

    def test_scalar_where_a_list_belongs_does_not_raise(self):
        lore = make_lore({"A.md": page_file("A", extra="tags: rf\nsources: raw/spec.pdf\n")})
        p = load_pages(lore)[0]
        self.assertIsInstance(p["tags"], list)
        self.assertIsInstance(p["sources"], list)


if __name__ == "__main__":
    unittest.main()
