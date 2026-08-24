"""Tests for lore_graph.py — run with: python3 -m unittest discover scripts"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lore_graph import build_html, main, parse_lore


def make_lore(pages: dict) -> Path:
    """Create a throwaway lore with wiki/ pages. pages: {filename: content}."""
    root = Path(tempfile.mkdtemp())
    (root / "wiki").mkdir()
    (root / "index.md").write_text("# index\n")
    for name, content in pages.items():
        (root / "wiki" / name).write_text(content)
    return root


def page(title: str, ptype: str = "concept", body: str = "") -> str:
    return f"---\ntype: {ptype}\ntitle: {title}\n---\n\n{body}\n"


class TestParseNodes(unittest.TestCase):
    def test_builds_one_node_per_wiki_page(self):
        lore = make_lore({
            "Link_Setup_Frame.md": page("Link Setup Frame"),
            "Power_Budget.md": page("Power Budget", "decision"),
        })
        graph = parse_lore(lore)
        names = {n["id"] for n in graph["nodes"]}
        self.assertEqual(names, {"Link_Setup_Frame", "Power_Budget"})

    def test_node_carries_title_and_type_from_frontmatter(self):
        lore = make_lore({"Power_Budget.md": page("Power Budget", "decision")})
        graph = parse_lore(lore)
        node = graph["nodes"][0]
        self.assertEqual(node["title"], "Power Budget")
        self.assertEqual(node["type"], "decision")

    def test_missing_frontmatter_falls_back_to_filename_and_unknown_type(self):
        lore = make_lore({"Odd_Page.md": "no frontmatter here\n"})
        graph = parse_lore(lore)
        node = graph["nodes"][0]
        self.assertEqual(node["title"], "Odd Page")
        self.assertEqual(node["type"], "unknown")


class TestParseEdges(unittest.TestCase):
    def test_wikilink_creates_edge_between_pages(self):
        lore = make_lore({
            "A.md": page("A", body="see [[B]]"),
            "B.md": page("B"),
        })
        graph = parse_lore(lore)
        self.assertEqual(graph["edges"], [{"source": "A", "target": "B"}])

    def test_alias_and_anchor_forms_resolve_to_page(self):
        lore = make_lore({
            "A.md": page("A", body="[[B|the b page]] and [[C#some-section]]"),
            "B.md": page("B"),
            "C.md": page("C"),
        })
        graph = parse_lore(lore)
        targets = {e["target"] for e in graph["edges"]}
        self.assertEqual(targets, {"B", "C"})

    def test_link_with_spaces_matches_underscore_filename(self):
        lore = make_lore({
            "A.md": page("A", body="[[Link Setup Frame]]"),
            "Link_Setup_Frame.md": page("Link Setup Frame"),
        })
        graph = parse_lore(lore)
        self.assertEqual(graph["edges"], [{"source": "A", "target": "Link_Setup_Frame"}])

    def test_repeated_links_dedupe_to_one_edge(self):
        lore = make_lore({
            "A.md": page("A", body="[[B]] then [[B]] again and [[B|alias]]"),
            "B.md": page("B"),
        })
        graph = parse_lore(lore)
        self.assertEqual(len(graph["edges"]), 1)


class TestGhostNodes(unittest.TestCase):
    def test_missing_target_becomes_ghost_node(self):
        lore = make_lore({"A.md": page("A", body="[[Nowhere]]")})
        graph = parse_lore(lore)
        ghost = next(n for n in graph["nodes"] if n["id"] == "Nowhere")
        self.assertTrue(ghost["ghost"])
        self.assertEqual(graph["edges"], [{"source": "A", "target": "Nowhere"}])

    def test_real_pages_are_not_ghosts(self):
        lore = make_lore({"A.md": page("A")})
        graph = parse_lore(lore)
        self.assertFalse(graph["nodes"][0]["ghost"])


class TestBuildHtml(unittest.TestCase):
    def test_embeds_graph_data_as_json(self):
        graph = {"nodes": [{"id": "A", "title": "A", "type": "concept", "ghost": False}],
                 "edges": []}
        html = build_html(graph, "my-lore")
        self.assertIn('"id": "A"', html)
        self.assertIn("my-lore", html)

    def test_output_is_self_contained(self):
        html = build_html({"nodes": [], "edges": []}, "x")
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)


class TestMain(unittest.TestCase):
    def test_writes_html_to_given_output_path(self):
        lore = make_lore({"A.md": page("A", body="[[B]]")})
        out = lore / "out" / "graph.html"
        out.parent.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            main([str(lore), "-o", str(out)])
        content = out.read_text()
        self.assertIn('"id": "A"', content)

    def test_rejects_path_without_wiki_dir(self):
        root = Path(tempfile.mkdtemp())
        with self.assertRaises(SystemExit):
            main([str(root), "-o", str(root / "g.html")])


if __name__ == "__main__":
    unittest.main()
