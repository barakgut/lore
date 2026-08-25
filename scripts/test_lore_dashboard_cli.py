"""Tests for lore_dashboard.py — run with: python3 -m unittest discover scripts"""
import contextlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from lore_dashboard import build_payload, ensure_ignored, git_info, link_prefixes, main
from lore_dashboard_parse import load_pages, parse_index
from test_lore_dashboard_health import build_lore, page_file

TODAY = date(2026, 8, 24)


def payload_from(html_text):
    match = re.search(r'<script id="lore-data" type="application/json">(.*?)</script>',
                      html_text, re.DOTALL)
    return json.loads(match.group(1))


def run_main(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(argv)
    return code, out.getvalue()


class TestLinkPrefixes(unittest.TestCase):
    def test_default_location_links_are_local(self):
        lore = build_lore({"A.md": page_file("A")})
        self.assertEqual(link_prefixes(lore, lore),
                         {"lore": ".", "wiki": "wiki", "raw": "raw"})

    def test_output_elsewhere_gets_a_relative_path_back_to_the_lore(self):
        lore = build_lore({"A.md": page_file("A")})
        # A sibling of `lore` under the same temp root, so the relationship
        # is one level up — but via a fresh mkdtemp() each run (not a fixed
        # name like `lore.parent / "out"`), so re-running the suite in the
        # same environment never collides with a leftover directory.
        out_dir = Path(tempfile.mkdtemp())
        self.assertEqual(link_prefixes(lore, out_dir)["wiki"], f"../{lore.name}/wiki")

    def test_output_at_filesystem_root_does_not_crash(self):
        lore = build_lore({"A.md": page_file("A")})
        prefixes = link_prefixes(lore, Path("/"))
        self.assertTrue(prefixes["lore"])
        self.assertFalse(prefixes["lore"].startswith("/"))

    def test_lore_reached_through_a_symlink_resolves_to_the_real_path(self):
        lore = build_lore({"A.md": page_file("A")})
        # A fresh, unique path for the symlink itself (mkdtemp then remove
        # the directory it made, so symlink_to can claim that exact name) —
        # a fixed name would collide with a leftover from a prior run.
        link = Path(tempfile.mkdtemp())
        link.rmdir()
        link.symlink_to(lore)
        self.assertEqual(link_prefixes(link, link), {"lore": ".", "wiki": "wiki", "raw": "raw"})


class TestHrefFor(unittest.TestCase):
    def test_hash_and_percent_characters_are_percent_encoded(self):
        from lore_dashboard import href_for
        self.assertEqual(href_for("raw", "spec#1.pdf"), "raw/spec%231.pdf")
        self.assertEqual(href_for("raw", "100%done.pdf"), "raw/100%25done.pdf")

    def test_a_leading_double_slash_never_produces_a_protocol_relative_href(self):
        # quote() leaves "//" alone (its default safe set is "/"), so with the
        # "." prefix — the default, dashboard written inside the lore — a
        # frontmatter `resource: "//host/x.pdf"` used to reach the DOM as a
        # live protocol-relative link to that host. It must stay a path.
        from lore_dashboard import href_for
        self.assertEqual(href_for(".", "//evil.example.com/p.pdf"),
                         ".///evil.example.com/p.pdf")
        self.assertFalse(href_for(".", "//evil.example.com/p.pdf").startswith("//"))
        # A single leading slash is an ordinary absolute path, untouched.
        self.assertEqual(href_for(".", "/notes/spec.pdf"), "/notes/spec.pdf")

    def test_a_protocol_relative_resource_reaches_the_payload_as_a_path(self):
        lore = build_lore({"A.md": "---\ntype: concept\ntitle: A\ndescription: d\ntags: [x]\n"
                                   "sources:\n  - id: s\n    resource: \"//evil.example.com/p.pdf\"\n"
                                   "---\n\nbody\n"})
        source = build_payload(lore, lore, TODAY)["pages"][0]["sources"][0]
        self.assertFalse(source["href"].startswith("//"), source["href"])


class TestBuildPayload(unittest.TestCase):
    def test_pages_carry_relative_hrefs_and_absolute_paths(self):
        lore = build_lore({"A_Page.md": page_file("A Page")})
        page = build_payload(lore, lore, TODAY)["pages"][0]
        self.assertEqual(page["href"], "wiki/A_Page.md")
        self.assertEqual(page["abs"], str(lore / "wiki" / "A_Page.md"))

    def test_source_resources_resolve_to_hrefs_with_anchors_split_off(self):
        lore = build_lore({"A.md": page_file("A")}, raw_files={"spec.pdf": "data"})
        source = build_payload(lore, lore, TODAY)["pages"][0]["sources"][0]
        self.assertEqual(source["href"], "raw/spec.pdf")
        self.assertEqual(source["anchor"], "")
        self.assertTrue(source["exists"])

    def test_paths_with_spaces_are_percent_encoded(self):
        lore = build_lore({"A.md": page_file("A")}, raw_files={"my notes.txt": "data"})
        self.assertEqual(build_payload(lore, lore, TODAY)["raw"][0]["href"], "raw/my%20notes.txt")

    def test_meta_counts_match_the_parsed_lore(self):
        lore = build_lore({"A.md": page_file("A", body="[[B]] [[Nowhere]]"), "B.md": page_file("B")})
        meta = build_payload(lore, lore, TODAY)["meta"]
        self.assertEqual(meta["counts"], {"pages": 2, "ghosts": 1, "edges": 2, "raw": 0})
        self.assertEqual(meta["lore_name"], lore.name)

    def test_health_and_stats_are_included(self):
        payload = build_payload(build_lore({"A.md": page_file("A")}), Path("."), TODAY)
        self.assertIsInstance(payload["health"]["score"], int)
        self.assertIn("pages_by_type", payload["stats"])

    def test_pages_do_not_leak_the_internal_scratch_keys(self):
        # Controller decision: `fields` (raw frontmatter) and
        # `index_deprecated_section` (stamped on by parse_index, and only for
        # a page that actually has a line in index.md) are scratch keys the
        # health checks need; neither may reach the serialised payload.
        # Both are asserted present on the freshly parsed record first, so
        # the assertions below can only pass because build_payload strips
        # them — not because the fixture never grew them.
        lore = build_lore({"A.md": page_file("A")})
        parsed = load_pages(lore)
        parse_index(lore, parsed)
        self.assertIn("fields", parsed[0])
        self.assertIn("index_deprecated_section", parsed[0])
        page = build_payload(lore, lore, TODAY)["pages"][0]
        self.assertNotIn("fields", page)
        self.assertNotIn("index_deprecated_section", page)

    def test_a_container_typed_frontmatter_scalar_is_reported_not_crashed(self):
        # End-to-end mirror of parse's container-where-a-scalar-belongs case:
        # one hand-written page whose `title:`/`description:` are indented
        # blocks (dict / list) and one whose `status:` is a block list. Before
        # the coercion these reached health() and statistics() as containers
        # and took the whole build down — AttributeError: 'dict' object has no
        # attribute 'lower' from page["title"].lower(), and TypeError:
        # unhashable type: 'list' from Counter(p["status"] for p in pages).
        # One bad page must degrade to a reported offender, never a traceback.
        lore = build_lore({
            "Dict_Title.md": "---\ntype: concept\ntitle:\n  nested: value\n"
                             "description:\n  - a\n  - b\ntags: [x]\n---\n\nbody\n",
            "List_Status.md": "---\ntype: concept\ntitle: List Status\n"
                              "status:\n  - draft\n  - stable\ndescription: d\ntags: [x]\n"
                              "---\n\nbody\n",
        })
        code, _ = run_main([str(lore)])
        self.assertEqual(code, 0)
        payload = payload_from((lore / "dashboard.html").read_text())
        pages = {p["id"]: p for p in payload["pages"]}
        self.assertEqual(pages["Dict_Title"]["title"], "Dict Title")   # stem fallback survives
        self.assertEqual(pages["Dict_Title"]["description"], "")
        self.assertEqual(pages["List_Status"]["status"], "stable")
        # Both pages surface in the health report instead of killing the run.
        # A coerced-empty title/status is indistinguishable from an absent one
        # and takes the same silent fallback, so what is actually reported is
        # the rest of each page's schema — including, for Dict_Title, the
        # description the coercion emptied.
        offenders = {}
        for dimension in payload["health"]["dimensions"]:
            for check in dimension["checks"]:
                for offender in check["offenders"]:
                    offenders.setdefault(offender["ref"], []).append(offender["detail"])
        self.assertIn("Dict_Title", offenders)
        self.assertIn("List_Status", offenders)
        self.assertTrue(any("description missing" in d for d in offenders["Dict_Title"]),
                        offenders["Dict_Title"])

    def test_last_lint_days_is_filled_in_by_health_before_serialisation(self):
        # parse_log() alone leaves last_lint["days"] as None; build_payload
        # must call health() before the payload is returned so the Log tab
        # sees a real age, not null.
        lore = build_lore({"A.md": page_file("A")},
                          log_text="## [2026-07-01] lint | 3 fixed, 5 reported\n")
        payload = build_payload(lore, lore, TODAY)
        self.assertEqual(payload["log"]["last_lint"]["days"], 54)
        self.assertEqual(payload["health"]["last_lint"]["days"], 54)


class TestGitInfo(unittest.TestCase):
    def test_non_repository_is_reported_as_such(self):
        info = git_info(build_lore({"A.md": page_file("A")}))
        self.assertEqual(info["repo"], False)
        self.assertIsNone(info["head"])

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_repository_root_reports_head_and_dirty_flag(self):
        lore = build_lore({"A.md": page_file("A")})
        subprocess.run(["git", "init", "-q"], cwd=lore, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=lore, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=lore, check=True)
        subprocess.run(["git", "add", "-A"], cwd=lore, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=lore, check=True)
        info = git_info(lore)
        self.assertTrue(info["repo"])
        self.assertRegex(info["head"], r"^[0-9a-f]{7,}$")
        self.assertFalse(info["dirty"])
        (lore / "wiki" / "B.md").write_text(page_file("B"))
        self.assertTrue(git_info(lore)["dirty"])

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_a_lore_nested_inside_a_repository_is_not_the_repository_root(self):
        # git_info().repo is True only when `lore` itself is the repo root,
        # not merely "inside a repository somewhere below the root".
        parent = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q"], cwd=parent, check=True)
        lore = build_lore({"A.md": page_file("A")})
        nested = parent / "nested-lore"
        shutil.move(str(lore), str(nested))
        info = git_info(nested)
        self.assertFalse(info["repo"])
        self.assertIsNone(info["head"])


class TestEnsureIgnored(unittest.TestCase):
    def test_ignore_file_is_seeded_once(self):
        lore = build_lore({"A.md": page_file("A")})
        ensure_ignored(lore, lore / "dashboard.html")
        ensure_ignored(lore, lore / "dashboard.html")
        self.assertEqual((lore / ".ignore").read_text().count("dashboard.html"), 1)

    def test_gitignore_is_only_seeded_for_a_repository_root(self):
        lore = build_lore({"A.md": page_file("A")})
        ensure_ignored(lore, lore / "dashboard.html")
        self.assertFalse((lore / ".gitignore").exists())

    def test_output_outside_the_lore_seeds_nothing(self):
        lore = build_lore({"A.md": page_file("A")})
        outside = Path(tempfile.mkdtemp()) / "dash.html"
        self.assertEqual(ensure_ignored(lore, outside), [])
        self.assertFalse((lore / ".ignore").exists())

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_gitignore_is_seeded_for_a_repository_root_and_only_once(self):
        lore = build_lore({"A.md": page_file("A")})
        subprocess.run(["git", "init", "-q"], cwd=lore, check=True)
        touched_first = ensure_ignored(lore, lore / "dashboard.html")
        touched_second = ensure_ignored(lore, lore / "dashboard.html")
        self.assertEqual(sorted(touched_first), [".gitignore", ".ignore"])
        self.assertEqual(touched_second, [])
        self.assertEqual((lore / ".gitignore").read_text().count("dashboard.html"), 1)

    def test_only_the_basename_is_recorded_even_for_a_nested_output_path(self):
        # Stated contract: append `<basename>`, not the full lore-relative
        # path — a bare gitignore/ignore pattern with no slash matches the
        # name anywhere in the tree, which is what "ignore my generated
        # dashboards" means even if -o points somewhere nested.
        lore = build_lore({"A.md": page_file("A")})
        nested = lore / "exports" / "dashboard.html"
        nested.parent.mkdir()
        ensure_ignored(lore, nested)
        ignore_text = (lore / ".ignore").read_text()
        self.assertIn("dashboard.html", ignore_text.split("\n"))
        self.assertNotIn("exports/dashboard.html", ignore_text)


class TestMain(unittest.TestCase):
    def test_default_output_is_dashboard_html_in_the_lore(self):
        lore = build_lore({"A.md": page_file("A")})
        code, out = run_main([str(lore)])
        self.assertEqual(code, 0)
        self.assertTrue((lore / "dashboard.html").is_file())
        self.assertIn("1 pages", out)
        self.assertIn("health", out)

    def test_success_prints_exactly_one_line(self):
        # Even though this run also seeds .ignore (and possibly .gitignore),
        # the CLI contract is exactly one line of output on success.
        lore = build_lore({"A.md": page_file("A")})
        _, out = run_main([str(lore)])
        self.assertEqual(len(out.rstrip("\n").split("\n")), 1)

    def test_output_option_overrides_the_location(self):
        lore = build_lore({"A.md": page_file("A", body="[[B]]"), "B.md": page_file("B")})
        target = Path(tempfile.mkdtemp()) / "sub" / "dash.html"
        code, _ = run_main([str(lore), "-o", str(target)])
        self.assertEqual(code, 0)
        payload = payload_from(target.read_text())
        self.assertEqual(payload["meta"]["links"]["wiki"], f"../../{lore.name}/wiki")

    def test_a_folder_that_is_not_a_lore_exits_non_zero(self):
        root = Path(tempfile.mkdtemp())
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stderr(io.StringIO()):
                main([str(root)])
        self.assertNotEqual(caught.exception.code, 0)

    def test_a_folder_that_is_not_a_lore_exits_with_code_2_and_a_message_on_stderr(self):
        # Stated CLI contract: exit code 2, specifically — not just "non-zero".
        # (sys.exit(a_string) always yields exit code 1, so a naive
        # `sys.exit(f"error: ...")` here would silently violate this.)
        root = Path(tempfile.mkdtemp())
        err = io.StringIO()
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stderr(err):
                main([str(root)])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("is not a lore", err.getvalue())
        self.assertIn("needs wiki/ and index.md", err.getvalue())

    def test_an_output_path_whose_parent_cannot_be_created_exits_with_a_message(self):
        # A regular file standing where -o's parent directory has to be:
        # mkdir raises NotADirectoryError, which used to reach the terminal
        # as a bare traceback while every other failure printed "error: …".
        # Chosen over a chmod-000 directory because it fails the same way
        # whatever the user's privileges are.
        lore = build_lore({"A.md": page_file("A")})
        blocker = Path(tempfile.mkdtemp()) / "not-a-dir"
        blocker.write_text("i am a file")
        err = io.StringIO()
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stderr(err):
                main([str(lore), "-o", str(blocker / "sub" / "dash.html")])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("error: cannot create", err.getvalue())

    def test_an_unwritable_output_path_exits_with_a_message(self):
        # -o pointing at an existing directory: the parent is fine, the write
        # itself is what fails (IsADirectoryError).
        lore = build_lore({"A.md": page_file("A")})
        target = Path(tempfile.mkdtemp())
        err = io.StringIO()
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stderr(err):
                main([str(lore), "-o", str(target)])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("error: cannot write", err.getvalue())

    def test_too_old_python_exits_with_code_1_and_a_message_on_stderr(self):
        lore = build_lore({"A.md": page_file("A")})
        err = io.StringIO()
        with patch("lore_dashboard.sys.version_info", (3, 9, 0, "final", 0)):
            with self.assertRaises(SystemExit) as caught:
                with contextlib.redirect_stderr(err):
                    main([str(lore)])
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("python 3.10+ required", err.getvalue())

    def test_the_written_page_is_self_contained_and_carries_the_payload(self):
        # Same invariant as TestBuildHtml.test_output_is_self_contained, and
        # the same caveat: it is about assets (no CDN, no web font, no remote
        # resource), not about payload text. This fixture's lore deliberately
        # contains no https:// link of its own — a lore that did would put
        # one in the page legitimately, and the fix would be to narrow this
        # check, never to strip the user's URLs.
        lore = build_lore({"A.md": page_file("A")})
        run_main([str(lore)])
        page = (lore / "dashboard.html").read_text()
        self.assertNotIn("https://", page)
        self.assertEqual(payload_from(page)["pages"][0]["id"], "A")

    def test_running_twice_does_not_duplicate_the_ignore_line(self):
        lore = build_lore({"A.md": page_file("A")})
        run_main([str(lore)])
        run_main([str(lore)])
        self.assertEqual((lore / ".ignore").read_text().count("dashboard.html"), 1)


if __name__ == "__main__":
    unittest.main()
