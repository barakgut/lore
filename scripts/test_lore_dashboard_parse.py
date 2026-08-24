"""Tests for lore_dashboard_parse.py — run with: python3 -m unittest discover scripts"""
import tempfile
import unittest
from pathlib import Path

from lore_dashboard_parse import (
    link_target_id,
    load_pages,
    parse_frontmatter,
    parse_index,
    parse_log,
    parse_yaml_block,
    scan_raw,
    sha12,
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


class TestParseIndex(unittest.TestCase):
    def _lore(self, index_text, pages=None):
        lore = make_lore(pages or {"A_Page.md": page_file("A Page")})
        (lore / "index.md").write_text(index_text)
        return lore

    def test_groups_and_entries_are_parsed_with_hooks_and_char_counts(self):
        lore = self._lore("# Lore Index\n\n## RF\n\n- [A Page](wiki/A_Page.md) — the hook\n")
        pages = load_pages(lore)
        index = parse_index(lore, pages)
        group = index["groups"][0]
        self.assertEqual(group["heading"], "RF")
        entry = group["entries"][0]
        self.assertEqual((entry["title"], entry["id"], entry["hook"]),
                         ("A Page", "A_Page", "the hook"))
        self.assertTrue(entry["exists"])
        self.assertEqual(entry["chars"], len("- [A Page](wiki/A_Page.md) — the hook"))

    def test_page_records_are_stamped_with_their_group_and_hook(self):
        lore = self._lore("## RF\n\n- [A Page](wiki/A_Page.md) — the hook\n")
        pages = load_pages(lore)
        parse_index(lore, pages)
        self.assertEqual(pages[0]["index_group"], "RF")
        self.assertEqual(pages[0]["index_hook"], "the hook")

    def test_html_comments_and_prose_are_not_entries(self):
        lore = self._lore("# Lore Index\n\n<!-- One line per wiki page -->\nsome prose\n")
        index = parse_index(lore, load_pages(lore))
        self.assertEqual(index["entry_count"], 0)

    def test_orphans_and_ghost_entries_are_detected(self):
        lore = self._lore("## RF\n\n- [Gone](wiki/Gone.md) — missing file\n")
        index = parse_index(lore, load_pages(lore))
        self.assertEqual(index["orphans"], ["A_Page"])
        self.assertEqual(index["ghost_entries"][0]["target"], "wiki/Gone.md")

    def test_deprecated_section_is_flagged_and_misplacement_reported(self):
        pages = {"Old.md": page_file("Old", extra="status: deprecated\n")}
        lore = self._lore("## RF\n\n- [Old](wiki/Old.md) — hook\n\n## Deprecated\n", pages)
        index = parse_index(lore, load_pages(lore))
        self.assertTrue(index["groups"][1]["deprecated"])
        self.assertEqual(index["misplaced_deprecated"], ["Old"])

    def test_entries_over_200_chars_are_listed(self):
        long_hook = "x" * 220
        lore = self._lore(f"## RF\n\n- [A Page](wiki/A_Page.md) — {long_hook}\n")
        index = parse_index(lore, load_pages(lore))
        self.assertEqual(index["over_cap"][0]["title"], "A Page")


class TestParseLog(unittest.TestCase):
    def _lore(self, log_text):
        lore = make_lore({"A_Page.md": page_file("A Page")})
        (lore / "log.md").write_text(log_text)
        return lore

    def test_entries_are_parsed_newest_first_with_detail(self):
        lore = self._lore("# Lore Log\n\n"
                          "## [2026-08-01] init | lore created\n\n"
                          "## [2026-08-20] ingest | spec.pdf\n"
                          "3 pages written. sha256:ab12cd34ef56\n")
        log = parse_log(lore)
        self.assertEqual([e["date"] for e in log["entries"]], ["2026-08-20", "2026-08-01"])
        newest = log["entries"][0]
        self.assertEqual((newest["verb"], newest["subject"], newest["sha"]),
                         ("ingest", "spec.pdf", "ab12cd34ef56"))

    def test_lint_counts_are_extracted_into_last_lint(self):
        lore = self._lore("## [2026-07-01] lint | 3 fixed, 5 reported\n")
        log = parse_log(lore)
        self.assertEqual((log["last_lint"]["fixed"], log["last_lint"]["reported"]), (3, 5))
        self.assertEqual(log["last_lint"]["date"], "2026-07-01")

    def test_unparseable_headings_are_kept_as_malformed(self):
        lore = self._lore("## 2026-08-20 ingest spec.pdf\n")
        log = parse_log(lore)
        self.assertEqual(log["entries"], [])
        self.assertEqual(log["malformed"][0]["text"], "## 2026-08-20 ingest spec.pdf")

    def test_no_lint_entry_leaves_last_lint_null(self):
        self.assertIsNone(parse_log(self._lore("## [2026-08-01] init | x\n"))["last_lint"])


class TestScanRaw(unittest.TestCase):
    def _lore_with(self, filename, content, log_text):
        lore = make_lore({"A_Page.md": page_file("A Page")})
        (lore / "raw" / filename).write_text(content)
        (lore / "log.md").write_text(log_text)
        return lore

    def test_file_with_no_ledger_entry_is_new(self):
        lore = self._lore_with("spec.pdf", "data", "# Lore Log\n")
        self.assertEqual(scan_raw(lore, parse_log(lore), load_pages(lore))[0]["state"], "NEW")

    def test_matching_hash_is_processed_and_mismatch_is_changed(self):
        lore = self._lore_with("spec.pdf", "data", "# Lore Log\n")
        digest = sha12(lore / "raw" / "spec.pdf")
        (lore / "log.md").write_text(f"## [2026-08-20] ingest | spec.pdf\nsha256:{digest}\n")
        self.assertEqual(scan_raw(lore, parse_log(lore), load_pages(lore))[0]["state"], "PROCESSED")
        (lore / "raw" / "spec.pdf").write_text("replaced")
        self.assertEqual(scan_raw(lore, parse_log(lore), load_pages(lore))[0]["state"], "CHANGED")

    def test_ingest_entry_without_a_hash_counts_as_changed(self):
        lore = self._lore_with("spec.pdf", "data", "## [2026-01-01] ingest | spec.pdf\n1 page\n")
        self.assertEqual(scan_raw(lore, parse_log(lore), load_pages(lore))[0]["state"], "CHANGED")

    def test_latest_entry_wins_and_skip_marks_skipped_with_reason(self):
        lore = self._lore_with("odd.bin", "data",
                               "## [2026-08-01] ingest | odd.bin\nsha256:deadbeefdead\n"
                               "## [2026-08-02] skip | odd.bin\nunsupported binary format\n")
        record = scan_raw(lore, parse_log(lore), load_pages(lore))[0]
        self.assertEqual(record["state"], "SKIPPED")
        self.assertEqual(record["skip_reason"], "unsupported binary format")

    def test_substring_filenames_never_match_another_files_entry(self):
        lore = self._lore_with("spec.pdf", "data", "# Lore Log\n")
        digest = sha12(lore / "raw" / "spec.pdf")
        (lore / "raw" / "v2_spec.pdf").write_text("data")
        (lore / "log.md").write_text(f"## [2026-08-20] ingest | v2_spec.pdf\nsha256:{digest}\n")
        states = {r["name"]: r["state"] for r in scan_raw(lore, parse_log(lore), load_pages(lore))}
        self.assertEqual(states, {"spec.pdf": "NEW", "v2_spec.pdf": "PROCESSED"})

    def test_derived_pages_come_from_the_reverse_sources_lookup(self):
        lore = self._lore_with("spec.pdf", "data", "# Lore Log\n")
        (lore / "wiki" / "A_Page.md").write_text(page_file(
            "A Page", extra="sources:\n  - id: spec\n    resource: raw/spec.pdf#p3\n"))
        self.assertEqual(scan_raw(lore, parse_log(lore), load_pages(lore))[0]["pages"], ["A_Page"])


if __name__ == "__main__":
    unittest.main()
