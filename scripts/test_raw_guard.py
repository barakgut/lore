"""Tests for hooks/guard_raw.py — run with: python3 -m unittest discover scripts"""
import json
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


if __name__ == "__main__":
    unittest.main()
