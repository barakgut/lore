#!/usr/bin/env python3
"""PreToolUse guard: raw/ is immutable, and dashboard.html is human-only.

A lore self-describes: the directory containing raw/ (or dashboard.html) must
hold index.md, wiki/, and CLAUDE.md. Any other raw/ directory or dashboard.html
is none of our business. Three rules:

1. Edit/Write/MultiEdit/NotebookEdit targeting a path under a self-describing
   lore's raw/ are denied — originals are ground truth, distill into wiki/.
2. Any matched tool, Read included, targeting a self-describing lore's
   <lore>/dashboard.html is denied — it's a generated, human-only view;
   read index.md, wiki/, and log.md instead.
3. Edit/Write/MultiEdit/NotebookEdit targeting <lore>/index.md or a file
   directly under <lore>/index/ are denied — the index is generated from
   wiki/ frontmatter by scripts/lore_index.py; set group:/description: in
   the page and re-run the script. For this rule a lore is a directory
   holding wiki/, CLAUDE.md, and raw/ — index.md itself is not required,
   because the denied write may be the one that would create it.

On a match, print a PreToolUse deny decision; otherwise print nothing (no
opinion), so the normal permission flow continues. Never exit non-zero: a
guard that crashes must not block unrelated tool calls.

Not a hard security boundary: realpath() resolves symlinks before any of the
three basename checks run, so a symlinked raw/ directory, or a symlink named
dashboard.html pointing elsewhere, escapes detection; this is defense-in-depth
over the skills' own instructions, and Bash is unhooked by design regardless.
"""
import json
import os
import sys

DASHBOARD = "dashboard.html"
WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
INDEX_FILE = "index.md"
INDEX_DIR = "index"


def lore_root_for(path):
    """Return the lore root if path sits under <lore>/raw/, else None."""
    p = os.path.dirname(path)
    while True:
        if os.path.basename(p) == "raw":
            root = os.path.dirname(p)
            if (
                os.path.isfile(os.path.join(root, "index.md"))
                and os.path.isdir(os.path.join(root, "wiki"))
                and os.path.isfile(os.path.join(root, "CLAUDE.md"))
            ):
                return root
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


def lore_root_of(path):
    """Return the lore root if `path` sits directly inside one, else None."""
    root = os.path.dirname(path)
    if (
        os.path.isfile(os.path.join(root, "index.md"))
        and os.path.isdir(os.path.join(root, "wiki"))
        and os.path.isfile(os.path.join(root, "CLAUDE.md"))
    ):
        return root
    return None


def lore_root_for_index(path):
    """Return the lore root if `path` is <lore>/index.md or a file directly
    under <lore>/index/, else None.

    The "directly under index/" reading is tried first. This matters for two
    collisions between the fixed "index" group-subdirectory name and the
    reserved "index.md" filename: a lore root literally named "index", and a
    group file that resolves to index/index.md (a page with `group: index`).
    Each reading is only accepted once the candidate root itself looks like
    a lore, so whichever reading actually holds is the one used.
    """
    def is_lore(root):
        return (
            os.path.isdir(os.path.join(root, "wiki"))
            and os.path.isfile(os.path.join(root, "CLAUDE.md"))
            and os.path.isdir(os.path.join(root, "raw"))
        )

    parent = os.path.dirname(path)
    if os.path.basename(parent) == INDEX_DIR:
        root = os.path.dirname(parent)
        if is_lore(root):
            return root
    if os.path.basename(path) == INDEX_FILE:
        root = parent
        if is_lore(root):
            return root
    return None


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            return
        tool_input = data.get("tool_input")
        if not isinstance(tool_input, dict):
            return
        target = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not target:
            return
        target = os.path.expanduser(target)
        if not os.path.isabs(target):
            target = os.path.join(data.get("cwd") or os.getcwd(), target)
        target = os.path.realpath(target)

        tool = data.get("tool_name") or ""
        if os.path.basename(target) == DASHBOARD:
            root = lore_root_of(target)
            if root:
                deny(f"{target} is {root}'s dashboard.html — a human-only view, "
                     "regenerated with scripts/lore_dashboard.py. Read index.md, "
                     "wiki/ and log.md instead.")
                return
        if tool in WRITE_TOOLS:
            root = lore_root_for_index(target)
            if root:
                deny(f"{target} is {root}'s generated index — never hand-edited. "
                     "Set group:/description: in the page's frontmatter and run "
                     "scripts/lore_index.py instead.")
                return
            root = lore_root_for(target)
            if root:
                deny(f"{target} is inside {root}/raw/ — raw/ is immutable; "
                     "originals are ground truth. Write distilled content to "
                     "wiki/ instead.")
    except Exception:
        return


if __name__ == "__main__":
    main()
