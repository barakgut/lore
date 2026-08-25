"""Tests for hooks/guard_raw.py — run with: python3 -m unittest discover scripts"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "guard_raw.py"


def make_lore() -> Path:
    """A minimal self-describing lore: index.md + wiki/ + CLAUDE.md (+ raw/)."""
    root = Path(tempfile.mkdtemp())
    (root / "raw").mkdir()
    (root / "wiki").mkdir()
    (root / "index.md").write_text("# index\n")
    (root / "CLAUDE.md").write_text("# schema\n")
    return root


def run_hook(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK)], input=payload, capture_output=True, text=True
    )


def hook_input(tool_name: str, tool_input: dict, cwd: str = "/") -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd})


def decision(proc: subprocess.CompletedProcess):
    """The permissionDecision printed by the hook, or None for no opinion."""
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


class TestDeny(unittest.TestCase):
    def test_write_under_lore_raw_is_denied(self):
        lore = make_lore()
        proc = run_hook(hook_input("Write", {"file_path": str(lore / "raw" / "spec.md"), "content": "x"}))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(decision(proc), "deny")

    def test_edit_in_raw_subdirectory_is_denied(self):
        lore = make_lore()
        (lore / "raw" / "sub").mkdir()
        proc = run_hook(hook_input("Edit", {"file_path": str(lore / "raw" / "sub" / "doc.txt"), "old_string": "a", "new_string": "b"}))
        self.assertEqual(decision(proc), "deny")

    def test_relative_path_is_resolved_against_cwd(self):
        lore = make_lore()
        proc = run_hook(hook_input("Write", {"file_path": "raw/spec.md"}, cwd=str(lore)))
        self.assertEqual(decision(proc), "deny")

    def test_notebook_path_is_covered(self):
        lore = make_lore()
        proc = run_hook(hook_input("NotebookEdit", {"notebook_path": str(lore / "raw" / "nb.ipynb")}))
        self.assertEqual(decision(proc), "deny")

    def test_deny_reason_names_raw_and_the_lore(self):
        lore = make_lore()
        proc = run_hook(hook_input("Write", {"file_path": str(lore / "raw" / "spec.md")}))
        reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("raw/", reason)
        self.assertIn(str(lore), reason)


class TestAllow(unittest.TestCase):
    def test_wiki_write_in_same_lore_has_no_opinion(self):
        lore = make_lore()
        proc = run_hook(hook_input("Write", {"file_path": str(lore / "wiki" / "Page.md"), "content": "x"}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

    def test_raw_dir_outside_a_lore_has_no_opinion(self):
        root = Path(tempfile.mkdtemp())      # raw/ with no lore markers around it
        (root / "raw").mkdir()
        proc = run_hook(hook_input("Write", {"file_path": str(root / "raw" / "notes.md")}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

    def test_missing_file_path_has_no_opinion(self):
        proc = run_hook(hook_input("Write", {}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

    def test_malformed_stdin_never_blocks(self):
        proc = run_hook("this is not json")
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

    def test_structurally_odd_stdin_has_no_opinion(self):
        # Valid JSON, but the top-level payload is not an object.
        proc = run_hook(json.dumps([1, 2, 3]))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

        # tool_input is present but not a dict.
        proc2 = run_hook(json.dumps({"tool_name": "Write", "tool_input": "not-a-dict", "cwd": "/"}))
        self.assertEqual(proc2.returncode, 0)
        self.assertIsNone(decision(proc2))


class TestDashboardGuard(unittest.TestCase):
    def test_reading_the_dashboard_is_denied(self):
        lore = make_lore()
        (lore / "dashboard.html").write_text("<html></html>")
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "dashboard.html")}))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(decision(proc), "deny")

    def test_writing_the_dashboard_is_denied(self):
        lore = make_lore()
        proc = run_hook(hook_input("Write", {"file_path": str(lore / "dashboard.html")}))
        self.assertEqual(decision(proc), "deny")

    def test_the_deny_reason_says_it_is_human_only(self):
        lore = make_lore()
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "dashboard.html")}))
        reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("human-only", reason)
        self.assertIn("dashboard.html", reason)

    def test_reading_a_raw_original_is_still_allowed(self):
        lore = make_lore()
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "raw" / "spec.pdf")}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

    def test_reading_a_wiki_page_is_still_allowed(self):
        lore = make_lore()
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "wiki" / "Page.md")}))
        self.assertIsNone(decision(proc))

    def test_a_dashboard_html_outside_a_lore_has_no_opinion(self):
        root = Path(tempfile.mkdtemp())
        proc = run_hook(hook_input("Read", {"file_path": str(root / "dashboard.html")}))
        self.assertIsNone(decision(proc))

    def test_a_differently_named_export_inside_a_lore_has_no_opinion(self):
        lore = make_lore()
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "report.html")}))
        self.assertIsNone(decision(proc))


class TestDashboardGuardAdversarial(unittest.TestCase):
    """Attack the path matcher: relative segments, symlinks, subdirectories, casing."""

    def test_dotted_relative_dashboard_path_is_denied(self):
        lore = make_lore()
        (lore / "dashboard.html").write_text("<html></html>")
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "." / "dashboard.html")}))
        self.assertEqual(decision(proc), "deny")

    def test_dotdot_relative_dashboard_path_is_denied(self):
        lore = make_lore()
        (lore / "dashboard.html").write_text("<html></html>")
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "wiki" / ".." / "dashboard.html")}))
        self.assertEqual(decision(proc), "deny")

    def test_cwd_relative_dashboard_path_is_denied(self):
        lore = make_lore()
        (lore / "dashboard.html").write_text("<html></html>")
        proc = run_hook(hook_input("Read", {"file_path": "dashboard.html"}, cwd=str(lore)))
        self.assertEqual(decision(proc), "deny")

    def test_symlink_from_outside_pointing_into_the_lore_dashboard_is_denied(self):
        # A symlink whose target resolves inside the lore is caught: realpath()
        # follows it to the real dashboard.html before the basename check runs.
        lore = make_lore()
        (lore / "dashboard.html").write_text("<html></html>")
        outside = Path(tempfile.mkdtemp())
        link = outside / "link.html"
        link.symlink_to(lore / "dashboard.html")
        proc = run_hook(hook_input("Read", {"file_path": str(link)}))
        self.assertEqual(decision(proc), "deny")

    def test_symlink_named_dashboard_pointing_elsewhere_is_not_caught(self):
        # Known limitation, same shape as the raw/ one documented in the module
        # docstring: realpath() resolves the symlink *before* the basename
        # check runs, so a symlink literally named dashboard.html that points
        # at a different file evades the rule entirely.
        lore = make_lore()
        (lore / "wiki" / "real.html").write_text("<html>real</html>")
        (lore / "dashboard.html").symlink_to(lore / "wiki" / "real.html")
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "dashboard.html")}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

    def test_dashboard_html_in_a_subdirectory_is_not_denied(self):
        # The rule names <lore>/dashboard.html specifically — the generated,
        # top-level artifact. A same-named file elsewhere in the tree is a
        # different file and is left alone.
        lore = make_lore()
        (lore / "wiki" / "dashboard.html").write_text("<html></html>")
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "wiki" / "dashboard.html")}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

    def test_differently_cased_dashboard_name_is_not_denied(self):
        # Linux paths are case-sensitive; Dashboard.HTML is a distinct
        # filename from the one scripts/lore_dashboard.py actually writes.
        lore = make_lore()
        (lore / "Dashboard.HTML").write_text("<html></html>")
        proc = run_hook(hook_input("Read", {"file_path": str(lore / "Dashboard.HTML")}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

    def test_dashboard_html_in_a_non_self_describing_lore_has_no_opinion(self):
        root = Path(tempfile.mkdtemp())
        (root / "dashboard.html").write_text("<html></html>")
        proc = run_hook(hook_input("Read", {"file_path": str(root / "dashboard.html")}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))


class TestHookFailureModes(unittest.TestCase):
    """The guard runs before every matched tool call: it must never raise
    or exit non-zero, whatever garbage lands on stdin."""

    def test_tool_input_key_missing_entirely_has_no_opinion(self):
        proc = subprocess.run(
            ["python3", str(HOOK)],
            input=json.dumps({"tool_name": "Read", "cwd": "/"}),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        self.assertIsNone(decision(proc))

    def test_null_file_path_has_no_opinion(self):
        proc = run_hook(hook_input("Read", {"file_path": None}))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        self.assertIsNone(decision(proc))

    def test_null_notebook_path_has_no_opinion(self):
        proc = run_hook(hook_input("NotebookEdit", {"notebook_path": None}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(decision(proc))

    @unittest.skipIf(os.geteuid() == 0, "permission bits are not enforced for root")
    def test_unreadable_lore_directory_has_no_opinion(self):
        lore = make_lore()
        (lore / "dashboard.html").write_text("<html></html>")
        os.chmod(lore, 0o000)
        try:
            proc = run_hook(hook_input("Read", {"file_path": str(lore / "dashboard.html")}))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")
        finally:
            os.chmod(lore, 0o700)


if __name__ == "__main__":
    unittest.main()
