#!/usr/bin/env python3
"""PreToolUse guard: deny Edit/Write/NotebookEdit targeting files under a lore's raw/.

A lore self-describes: the directory containing raw/ must hold index.md, wiki/,
and CLAUDE.md. Any other raw/ directory is none of our business. On a match,
print a PreToolUse deny decision; otherwise print nothing (no opinion), so the
normal permission flow continues. Never exit non-zero: a guard that crashes
must not block unrelated edits.
"""
import json
import os
import sys


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


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    tool_input = data.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return
    target = os.path.expanduser(target)
    if not os.path.isabs(target):
        target = os.path.join(data.get("cwd") or os.getcwd(), target)
    target = os.path.realpath(target)
    root = lore_root_for(target)
    if root:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"{target} is inside {root}/raw/ — raw/ is immutable; "
                    "originals are ground truth. Write distilled content to "
                    "wiki/ instead."
                ),
            }
        }))


if __name__ == "__main__":
    main()
