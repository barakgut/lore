"""Tests for lore_dashboard_health.py — run with: python3 -m unittest discover scripts"""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from lore_dashboard_health import WEIGHTS, health
from lore_dashboard_parse import build_graph, load_pages, parse_index, parse_log, scan_raw

TODAY = date(2026, 8, 24)


def build_lore(pages: dict, index_text: str = None, log_text: str = "# Lore Log\n",
               raw_files: dict = None) -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "wiki").mkdir()
    (root / "raw").mkdir()
    for name, content in pages.items():
        (root / "wiki" / name).write_text(content)
    if index_text is None:
        lines = ["# Lore Index", "", "## Pages", ""]
        lines += [f"- [{Path(n).stem}](wiki/{n}) — hook" for n in pages]
        index_text = "\n".join(lines) + "\n"
    (root / "index.md").write_text(index_text)
    (root / "log.md").write_text(log_text)
    for name, content in (raw_files or {}).items():
        (root / "raw" / name).write_text(content)
    return root


def page_file(title, ptype="concept", body="", extra="") -> str:
    return (f"---\ntype: {ptype}\ntitle: {title}\ndescription: about {title}\ntags: [x]\n"
            f"sources:\n  - id: spec\n    resource: raw/spec.pdf\n"
            f"generated:\n  by: lore/test\n  at: 2026-08-01\n{extra}---\n\n{body}\n")


def score_for(lore: Path, today=TODAY):
    pages = load_pages(lore)
    index = parse_index(lore, pages)
    log = parse_log(lore)
    raw = scan_raw(lore, log, pages)
    graph = build_graph(pages)
    return health(pages, index, log, raw, graph, today)


def check(result, dimension_key, check_key):
    dimension = next(d for d in result["dimensions"] if d["key"] == dimension_key)
    return next(c for c in dimension["checks"] if c["key"] == check_key)


class TestShape(unittest.TestCase):
    def test_six_dimensions_in_order_with_the_agreed_weights(self):
        result = score_for(build_lore({"A.md": page_file("A", body="[[B]]"),
                                       "B.md": page_file("B", body="[[A]]")}))
        self.assertEqual([(d["key"], d["weight"]) for d in result["dimensions"]],
                         [(k, w) for k, _, w in WEIGHTS])
        self.assertEqual(sum(w for _, _, w in WEIGHTS), 100)

    def test_a_clean_lore_scores_100(self):
        lore = build_lore({"A.md": page_file("A", body="[[B]]"), "B.md": page_file("B", body="[[A]]")},
                          log_text="## [2026-08-20] lint | 0 fixed, 0 reported\n")
        self.assertEqual(score_for(lore)["score"], 100)

    def test_score_is_an_int_between_0_and_100(self):
        result = score_for(build_lore({"Odd.md": "no frontmatter\n"}))
        self.assertIsInstance(result["score"], int)
        self.assertTrue(0 <= result["score"] <= 100)

    def test_an_empty_lore_never_divides_by_zero(self):
        self.assertEqual(score_for(build_lore({}, index_text="# Lore Index\n"))["score"], 100)


class TestIntegrity(unittest.TestCase):
    def test_orphan_page_is_an_offender(self):
        lore = build_lore({"A.md": page_file("A")}, index_text="# Lore Index\n")
        offenders = check(score_for(lore), "integrity", "orphans")["offenders"]
        self.assertEqual([o["ref"] for o in offenders], ["A"])

    def test_dead_wikilink_offender_names_the_target(self):
        lore = build_lore({"A.md": page_file("A", body="[[Nowhere]]")})
        offender = check(score_for(lore), "integrity", "dead_wikilinks")["offenders"][0]
        self.assertEqual(offender["ref"], "A")
        self.assertIn("Nowhere", offender["detail"])

    def test_titles_differing_only_by_case_or_punctuation_are_duplicates(self):
        lore = build_lore({"A.md": page_file("Link Setup"), "B.md": page_file("link-setup!")})
        offenders = check(score_for(lore), "integrity", "duplicate_titles")["offenders"]
        self.assertEqual(sorted(o["ref"] for o in offenders), ["A", "B"])

    def test_ghost_index_entry_is_an_offender(self):
        lore = build_lore({"A.md": page_file("A")},
                          index_text="## Pages\n\n- [A](wiki/A.md) — hook\n- [Gone](wiki/Gone.md) — hook\n")
        self.assertEqual(len(check(score_for(lore), "integrity", "ghost_entries")["offenders"]), 1)

    def test_deprecated_page_indexed_outside_the_deprecated_section(self):
        lore = build_lore({"A.md": page_file("A", extra="status: deprecated\n")})
        self.assertEqual(check(score_for(lore), "integrity", "deprecated_placement")["score"], 0.0)


class TestSchema(unittest.TestCase):
    def test_missing_required_field_is_an_offender_naming_the_field(self):
        lore = build_lore({"A.md": "---\ntype: concept\ntitle: A\n---\n\nbody\n"})
        offender = check(score_for(lore), "schema", "required_fields")["offenders"][0]
        self.assertIn("description", offender["detail"])

    def test_invalid_type_and_status_are_offenders(self):
        lore = build_lore({"A.md": page_file("A", ptype="notatype", extra="status: weird\n")})
        result = score_for(lore)
        self.assertEqual(len(check(result, "schema", "required_fields")["offenders"]), 1)
        self.assertEqual(len(check(result, "schema", "status_value")["offenders"]), 1)

    def test_pre_0_3_fields_are_offenders(self):
        lore = build_lore({"A.md": page_file("A", extra="trust: high\ncaptured: 2025-01-01\n")})
        offender = check(score_for(lore), "schema", "legacy_fields")["offenders"][0]
        self.assertIn("trust", offender["detail"])

    def test_source_entry_without_resource_is_an_offender(self):
        lore = build_lore({"A.md": "---\ntype: concept\ntitle: A\ndescription: d\ntags: [x]\n"
                                   "sources:\n  - id: spec\n"
                                   "generated:\n  by: lore/test\n  at: 2026-08-01\n---\n\nbody\n"})
        self.assertEqual(len(check(score_for(lore), "schema", "sources_entries")["offenders"]), 1)

    def test_footnote_without_a_matching_source_id_is_an_offender(self):
        lore = build_lore({"A.md": page_file("A", body="claim[^nosuch]")})
        offender = check(score_for(lore), "schema", "footnote_ids")["offenders"][0]
        self.assertIn("nosuch", offender["detail"])


class TestConnectivity(unittest.TestCase):
    def test_isolated_and_no_inbound_pages(self):
        lore = build_lore({"A.md": page_file("A", body="[[B]]"), "B.md": page_file("B"),
                           "Loose.md": page_file("Loose")})
        result = score_for(lore)
        self.assertEqual([o["ref"] for o in check(result, "connectivity", "isolated")["offenders"]],
                         ["Loose"])
        self.assertEqual(sorted(o["ref"] for o in check(result, "connectivity", "no_inbound")["offenders"]),
                         ["A", "Loose"])

    def test_one_component_is_a_perfect_component_score(self):
        lore = build_lore({"A.md": page_file("A", body="[[B]]"), "B.md": page_file("B", body="[[A]]")})
        self.assertEqual(check(score_for(lore), "connectivity", "components")["score"], 1.0)

    def test_two_disconnected_clusters_score_the_components_formula_exactly(self):
        # Two clusters of 10 pages each, chained internally (10 nodes per
        # chain), never cross-linked -> graph["components"] == 2 for 20 pages.
        # Formula: 1 - (components - 1) / max(1, ceil(pages/10))
        #        = 1 - (2 - 1) / max(1, ceil(20/10)) = 1 - 1/2 = 0.5 (hand-derived).
        pages = {}
        for cluster in ("G1", "G2"):
            for i in range(1, 11):
                body = f"[[{cluster}_{i + 1}]]" if i < 10 else ""
                pages[f"{cluster}_{i}.md"] = page_file(f"{cluster}_{i}", body=body)
        lore = build_lore(pages)
        self.assertAlmostEqual(check(score_for(lore), "connectivity", "components")["score"], 0.5)


class TestProvenance(unittest.TestCase):
    def _no_sources(self, ptype, extra=""):
        body_page = ("---\n" + f"type: {ptype}\ntitle: A\ndescription: d\ntags: [x]\n"
                     f"generated:\n  by: lore/test\n  at: 2026-08-01\n{extra}---\n\nbody\n")
        return build_lore({"A.md": body_page})

    def test_page_without_sources_is_an_offender(self):
        self.assertEqual(len(check(score_for(self._no_sources("concept")), "provenance",
                                   "no_sources")["offenders"]), 1)

    def test_decision_pages_are_exempt(self):
        self.assertEqual(check(score_for(self._no_sources("decision")), "provenance",
                               "no_sources")["offenders"], [])

    def test_human_written_answer_pages_are_exempt(self):
        page = ("---\ntype: answer\ntitle: A\ndescription: d\ntags: [x]\n"
                "generated:\n  by: human:Barak Gutman\n  at: 2026-08-01\n---\n\nbody\n")
        lore = build_lore({"A.md": page})
        self.assertEqual(check(score_for(lore), "provenance", "no_sources")["offenders"], [])

    def test_multi_source_page_without_footnotes_is_an_offender(self):
        page = ("---\ntype: concept\ntitle: A\ndescription: d\ntags: [x]\n"
                "sources:\n  - id: a\n    resource: raw/a.pdf\n  - id: b\n    resource: raw/b.pdf\n"
                "generated:\n  by: lore/test\n  at: 2026-08-01\n---\n\nplain claim\n")
        lore = build_lore({"A.md": page})
        self.assertEqual(len(check(score_for(lore), "provenance", "missing_footnotes")["offenders"]), 1)


class TestInboxCurrency(unittest.TestCase):
    def test_new_and_changed_files_are_offenders(self):
        lore = build_lore({"A.md": page_file("A")}, raw_files={"spec.pdf": "data"})
        offenders = check(score_for(lore), "inbox", "new_or_changed")["offenders"]
        self.assertEqual([o["ref"] for o in offenders], ["spec.pdf"])
        self.assertEqual(offenders[0]["kind"], "raw")

    def test_skipped_files_are_a_separate_check(self):
        lore = build_lore({"A.md": page_file("A")},
                          log_text="## [2026-08-01] skip | odd.bin\nunsupported\n",
                          raw_files={"odd.bin": "data"})
        self.assertEqual(len(check(score_for(lore), "inbox", "skipped")["offenders"]), 1)

    def test_no_raw_files_means_a_perfect_inbox(self):
        lore = build_lore({"A.md": page_file("A")})
        dimension = next(d for d in score_for(lore)["dimensions"] if d["key"] == "inbox")
        self.assertEqual(dimension["score"], 1.0)


class TestOpenIssues(unittest.TestCase):
    def test_contradictions_and_drafts_are_offenders(self):
        lore = build_lore({"A.md": page_file("A", body="> ⚠ CONTRADICTION: x [[B]]; y [[C]]",
                                             extra="status: draft\n")})
        result = score_for(lore)
        self.assertEqual(len(check(result, "issues", "contradictions")["offenders"]), 1)
        self.assertEqual(len(check(result, "issues", "drafts")["offenders"]), 1)

    def test_lint_within_30_days_is_unpenalised(self):
        fresh = build_lore({"A.md": page_file("A")},
                           log_text="## [2026-08-20] lint | 0 fixed, 0 reported\n")
        self.assertEqual(check(score_for(fresh), "issues", "lint_age")["score"], 1.0)

    def test_lint_exactly_30_days_old_is_still_at_the_grace_boundary(self):
        # TODAY is 2026-08-24; 2026-07-25 is exactly 30 days earlier.
        # "1.0 when days <= 30" is inclusive of the boundary itself.
        boundary = build_lore({"A.md": page_file("A")},
                              log_text="## [2026-07-25] lint | 0 fixed, 0 reported\n")
        self.assertEqual(check(score_for(boundary), "issues", "lint_age")["score"], 1.0)

    def test_lint_60_days_old_scores_the_penalty_formula_exactly(self):
        # TODAY is 2026-08-24; 2026-06-25 is exactly 60 days earlier.
        # Formula: max(0, 1 - (days - 30) / 60) = 1 - (60 - 30) / 60
        #        = 1 - 0.5 = 0.5 (hand-derived).
        stale = build_lore({"A.md": page_file("A")},
                           log_text="## [2026-06-25] lint | 0 fixed, 0 reported\n")
        self.assertAlmostEqual(check(score_for(stale), "issues", "lint_age")["score"], 0.5)

    def test_last_lint_counts_are_surfaced_with_an_age_in_days(self):
        lore = build_lore({"A.md": page_file("A")},
                          log_text="## [2026-07-01] lint | 3 fixed, 5 reported\n")
        last = score_for(lore)["last_lint"]
        self.assertEqual((last["fixed"], last["reported"], last["days"]), (3, 5, 54))

    def test_no_lint_entry_ever_reports_null_last_lint(self):
        lore = build_lore({"A.md": page_file("A")}, log_text="## [2026-08-20] init | created\n")
        self.assertIsNone(score_for(lore)["last_lint"])

    def test_index_at_the_200_line_boundary_scores_a_perfect_1_0(self):
        # 3 header/entry lines + 197 filler lines = 200 lines, no trailing
        # newline, so line_count == len(lines) == 200 exactly: at the target,
        # not over it -> the "not oversize" branch scores 1.0 exactly.
        lines = ["## Pages", "", "- [A](wiki/A.md) — hook"] + [f"prose line {n}" for n in range(197)]
        lore = build_lore({"A.md": page_file("A")}, index_text="\n".join(lines))
        self.assertEqual(check(score_for(lore), "issues", "index_size")["score"], 1.0)

    def test_index_over_200_lines_scores_the_penalty_formula_exactly(self):
        # 3 header/entry lines + 297 filler lines = 300 lines, no trailing
        # newline, so line_count == len(lines) == 300 exactly.
        # Formula: max(0, 1 - (line_count - 200) / 200) = 1 - (300 - 200) / 200
        #        = 1 - 0.5 = 0.5 (hand-derived).
        lines = ["## Pages", "", "- [A](wiki/A.md) — hook"] + [f"prose line {n}" for n in range(297)]
        lore = build_lore({"A.md": page_file("A")}, index_text="\n".join(lines))
        self.assertAlmostEqual(check(score_for(lore), "issues", "index_size")["score"], 0.5)


if __name__ == "__main__":
    unittest.main()
