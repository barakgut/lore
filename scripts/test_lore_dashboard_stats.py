"""Tests for lore_dashboard_stats.py — run with: python3 -m unittest discover scripts"""
import unittest

from lore_dashboard_parse import build_graph, load_pages, parse_index, parse_log, scan_raw
from lore_dashboard_stats import statistics
from test_lore_dashboard_health import build_lore, page_file


def stats_for(lore):
    pages = load_pages(lore)
    index = parse_index(lore, pages)
    log = parse_log(lore)
    raw = scan_raw(lore, log, pages)
    return statistics(pages, index, log, raw, build_graph(pages))


def counts(rows):
    return {row["key"]: row["count"] for row in rows}


def source_page(title, resource):
    """A minimal concept page whose sole source resolves to raw/<resource>."""
    return (f"---\ntype: concept\ntitle: {title}\ndescription: d\ntags: [x]\n"
            f"sources:\n  - id: s\n    resource: raw/{resource}\n"
            f"generated:\n  by: lore/test\n  at: 2026-08-01\n---\n\nbody\n")


class TestPageStats(unittest.TestCase):
    def test_pages_grouped_by_type_status_and_generator(self):
        lore = build_lore({"A.md": page_file("A"),
                           "B.md": page_file("B", ptype="decision", extra="status: draft\n")})
        stats = stats_for(lore)
        self.assertEqual(counts(stats["pages_by_type"]), {"concept": 1, "decision": 1})
        self.assertEqual(counts(stats["pages_by_status"]), {"stable": 1, "draft": 1})
        self.assertEqual(counts(stats["pages_by_generator"]), {"lore/test": 2})

    def test_rows_sort_by_count_desc_then_key_asc(self):
        lore = build_lore({"A.md": page_file("A"), "B.md": page_file("B"),
                           "C.md": page_file("C", ptype="answer"),
                           "D.md": page_file("D", ptype="decision")})
        self.assertEqual([r["key"] for r in stats_for(lore)["pages_by_type"]],
                         ["concept", "answer", "decision"])

    def test_tags_are_counted_and_untagged_pages_listed(self):
        lore = build_lore({"A.md": page_file("A"),
                           "B.md": "---\ntype: concept\ntitle: B\ndescription: d\n"
                                   "generated:\n  by: lore/test\n  at: 2026-08-01\n---\n\nbody\n"})
        stats = stats_for(lore)
        self.assertEqual(counts(stats["tags"]), {"x": 1})
        self.assertEqual(stats["untagged"], ["B"])


class TestInboxAndCoverage(unittest.TestCase):
    def test_raw_grouped_by_extension_and_state_with_sizes(self):
        lore = build_lore({"A.md": page_file("A")}, raw_files={"spec.pdf": "data", "n.txt": "hi"})
        stats = stats_for(lore)
        self.assertEqual(counts(stats["raw_by_ext"]), {".pdf": 1, ".txt": 1})
        self.assertEqual(counts(stats["raw_by_state"]), {"NEW": 2})
        self.assertEqual(stats["raw_total_bytes"], 6)

    def test_raw_by_ext_sums_bytes_per_extension(self):
        # one.pdf is 5 bytes ("abcde"), two.pdf is 3 bytes ("xyz") -> the
        # .pdf group's "bytes" is their sum, 8 — hand-derived from the two
        # literal file contents, not from the implementation under test.
        lore = build_lore({"A.md": page_file("A")},
                          raw_files={"one.pdf": "abcde", "two.pdf": "xyz"})
        rows = {row["key"]: row for row in stats_for(lore)["raw_by_ext"]}
        self.assertEqual(rows[".pdf"]["bytes"], 8)
        self.assertEqual(rows[".pdf"]["count"], 2)

    def test_coverage_splits_cited_from_uncited_raw_files(self):
        lore = build_lore({"A.md": page_file("A")}, raw_files={"spec.pdf": "d", "lonely.csv": "d"})
        coverage = stats_for(lore)["coverage"]
        self.assertEqual((coverage["raw_with_pages"], coverage["raw_without_pages"]), (1, 1))
        self.assertEqual(coverage["uncited"], ["lonely.csv"])
        self.assertEqual(coverage["pages_per_raw"][0], {"file": "spec.pdf", "count": 1})

    def test_pages_per_raw_counts_multiple_citations(self):
        # Three separate pages each cite raw/shared.pdf -> the count for
        # shared.pdf is 3 (the number of citing pages), not 1.
        lore = build_lore({"A.md": source_page("A", "shared.pdf"),
                           "B.md": source_page("B", "shared.pdf"),
                           "C.md": source_page("C", "shared.pdf")},
                          raw_files={"shared.pdf": "d"})
        pages_per_raw = stats_for(lore)["coverage"]["pages_per_raw"]
        self.assertEqual(pages_per_raw, [{"file": "shared.pdf", "count": 3}])

    def test_pages_per_raw_caps_at_ten_with_deterministic_tie_break(self):
        # 12 distinct raw files, each cited by exactly one page -> all tied
        # at count 1. Cap keeps the 10 alphabetically-first filenames
        # (f01.pdf .. f10.pdf), dropping f11.pdf and f12.pdf.
        pages, raw_files = {}, {}
        for i in range(1, 13):
            name = f"f{i:02d}.pdf"
            raw_files[name] = "d"
            pages[f"P{i:02d}.md"] = source_page(f"P{i:02d}", name)
        lore = build_lore(pages, raw_files=raw_files)
        pages_per_raw = stats_for(lore)["coverage"]["pages_per_raw"]
        self.assertEqual([row["file"] for row in pages_per_raw],
                         [f"f{i:02d}.pdf" for i in range(1, 11)])
        self.assertTrue(all(row["count"] == 1 for row in pages_per_raw))


class TestGraphStats(unittest.TestCase):
    def test_node_edge_degree_and_hub_counts(self):
        lore = build_lore({"A.md": page_file("A", body="[[B]]"),
                           "C.md": page_file("C", body="[[B]] [[Nowhere]]"),
                           "B.md": page_file("B")})
        graph_stats = stats_for(lore)["graph"]
        self.assertEqual((graph_stats["pages"], graph_stats["ghosts"], graph_stats["edges"]),
                         (3, 1, 3))
        self.assertEqual(graph_stats["avg_degree"], 1.5)
        self.assertEqual(graph_stats["hubs"][0], {"id": "B", "title": "B", "count": 2})

    def test_hub_list_caps_at_top_ten_by_inbound_count(self):
        # Hub01..Hub11 exist; source pages S01..S11 each link to every
        # Hub_j with j <= i. So Hub_j's in-degree is the count of i in
        # 1..11 with i >= j, i.e. 11 - j + 1 = 12 - j:
        #   Hub01 -> 11, Hub02 -> 10, ..., Hub10 -> 2, Hub11 -> 1.
        # Hand-derived expectation: the top 10 by count survive
        # (Hub01..Hub10, counts 11 down to 2); Hub11 (count 1) is cut.
        pages = {f"Hub{j:02d}.md": page_file(f"Hub{j:02d}") for j in range(1, 12)}
        for i in range(1, 12):
            body = " ".join(f"[[Hub{j:02d}]]" for j in range(1, i + 1))
            pages[f"S{i:02d}.md"] = page_file(f"S{i:02d}", body=body)
        lore = build_lore(pages)
        hubs = stats_for(lore)["graph"]["hubs"]
        self.assertEqual([h["id"] for h in hubs], [f"Hub{j:02d}" for j in range(1, 11)])
        self.assertEqual([h["count"] for h in hubs], list(range(11, 1, -1)))

    def test_hub_tie_break_by_id_ascending(self):
        # HubA and HubB each get exactly one inbound link -> tied at count
        # 1; ties break by id ascending, so HubA precedes HubB even though
        # the linking page names HubB first.
        lore = build_lore({"HubB.md": page_file("HubB"), "HubA.md": page_file("HubA"),
                           "S.md": page_file("S", body="[[HubB]] [[HubA]]")})
        hubs = stats_for(lore)["graph"]["hubs"]
        self.assertEqual([h["id"] for h in hubs], ["HubA", "HubB"])

    def test_ghost_nodes_are_hub_candidates_and_carry_their_derived_title(self):
        # Ruling: ghost nodes are NOT excluded from hub candidacy — the
        # module iterates all of graph["nodes"] (real pages + ghosts)
        # unfiltered, matching the plan's own reference code. A ghost with
        # more inbound links than any real page is the most actionable
        # fact the graph holds (the page the lore most wants and does not
        # have), so it must surface as the top hub, complete with its
        # derived title.
        #
        # Missing_Page does not exist as a page. A, B, and C each link to
        # it, giving it in-degree 3; only C also links to A, giving A
        # in-degree 1. Per build_graph, a ghost's title is its id with "_"
        # replaced by " ": "Missing_Page" -> "Missing Page".
        lore = build_lore({"A.md": page_file("A", body="[[Missing_Page]]"),
                           "B.md": page_file("B", body="[[Missing_Page]]"),
                           "C.md": page_file("C", body="[[Missing_Page]] [[A]]")})
        hubs = stats_for(lore)["graph"]["hubs"]
        self.assertEqual(hubs, [{"id": "Missing_Page", "title": "Missing Page", "count": 3},
                                {"id": "A", "title": "A", "count": 1}])


class TestLogStats(unittest.TestCase):
    def test_verbs_answers_discards_and_iso_weeks(self):
        log_text = ("## [2026-08-03] ingest | a.pdf\nsha256:aaaaaaaaaaaa\n\n"
                    "## [2026-08-05] ingest | b.pdf\nsha256:bbbbbbbbbbbb\n\n"
                    "## [2026-08-17] answer | Why X\n\n"
                    "## [2026-08-18] discard | Old_Page\n")
        stats = stats_for(build_lore({"A.md": page_file("A")}, log_text=log_text))["log"]
        self.assertEqual(counts(stats["by_verb"]), {"ingest": 2, "answer": 1, "discard": 1})
        self.assertEqual((stats["answers"], stats["discards"]), (1, 1))
        self.assertEqual(stats["ingests_per_week"], [{"week": "2026-W32", "count": 2}])

    def test_malformed_lines_are_counted(self):
        stats = stats_for(build_lore({"A.md": page_file("A")},
                                     log_text="## nonsense heading\n"))["log"]
        self.assertEqual(stats["malformed"], 1)

    def test_ingest_near_new_year_buckets_by_iso_week_not_calendar_year(self):
        # date(2027, 1, 1).isocalendar() == (2026, 53, 5): 2027-01-01 falls
        # in ISO week 53 of 2026, not week 1 of 2027. A bucketing scheme
        # that used the plain calendar year would wrongly emit "2027-W01".
        log_text = "## [2027-01-01] ingest | a.pdf\nsha256:aaaaaaaaaaaa\n"
        stats = stats_for(build_lore({"A.md": page_file("A")}, log_text=log_text))["log"]
        self.assertEqual(stats["ingests_per_week"], [{"week": "2026-W53", "count": 1}])


class TestEmptyLore(unittest.TestCase):
    def test_empty_lore_never_raises_and_zeroes_out(self):
        lore = build_lore({}, index_text="# Lore Index\n")
        stats = stats_for(lore)
        self.assertEqual(stats["pages_by_type"], [])
        self.assertEqual(stats["graph"]["nodes"], 0)
        self.assertEqual(stats["graph"]["avg_degree"], 0.0)
        self.assertEqual(stats["log"]["ingests_per_week"], [])
        self.assertEqual(stats["coverage"], {"raw_with_pages": 0, "raw_without_pages": 0,
                                             "pages_per_raw": [], "uncited": []})


if __name__ == "__main__":
    unittest.main()
