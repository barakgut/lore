#!/usr/bin/env python3
"""Render a lore as one self-contained HTML dashboard.

Standalone, human-only tool — not part of the lore plugin contract. The agent
never runs it and never reads its output.

Usage: python3 lore_dashboard.py <lore> [-o out.html]
"""
import argparse
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from lore_dashboard_health import health
from lore_dashboard_html import build_html
from lore_dashboard_parse import build_graph, load_pages, parse_index, parse_log, scan_raw
from lore_dashboard_stats import statistics

DEFAULT_OUTPUT = "dashboard.html"


def git_info(lore):
    """HEAD short sha and dirty flag — only when the lore is a repository root."""
    lore = Path(lore).resolve()
    info = {"repo": False, "head": None, "dirty": False}
    try:
        top = subprocess.run(["git", "-C", str(lore), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
        if top.returncode != 0 or Path(top.stdout.strip() or "/nonexistent").resolve() != lore:
            return info
        head = subprocess.run(["git", "-C", str(lore), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10)
        status = subprocess.run(["git", "-C", str(lore), "status", "--porcelain"],
                                capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return info
    info["repo"] = True
    info["head"] = head.stdout.strip() or None
    info["dirty"] = bool(status.stdout.strip())
    return info


def _join(base, name):
    """Join a relative prefix with a lore-relative name. '.' means 'right here'."""
    return name if base == "." else f"{base}/{name}"


def link_prefixes(lore, out_dir):
    """Relative path prefixes from the output directory back into the lore."""
    base = Path(os.path.relpath(str(Path(lore).resolve()),
                                str(Path(out_dir).resolve()))).as_posix()
    return {"lore": base, "wiki": _join(base, "wiki"), "raw": _join(base, "raw")}


def href_for(prefix, relative_path):
    """Percent-encoded href: `prefix` (from link_prefixes) joined with a path
    relative to whatever `prefix` is rooted at."""
    return quote(relative_path) if prefix == "." else f"{prefix}/{quote(relative_path)}"


def build_payload(lore, out_dir, today):
    lore = Path(lore).resolve()
    pages = load_pages(lore)
    index = parse_index(lore, pages)
    log = parse_log(lore)
    raw = scan_raw(lore, log, pages)
    graph = build_graph(pages)
    links = link_prefixes(lore, out_dir)
    for page in pages:
        page["href"] = href_for(links["lore"], page["file"])
        page["abs"] = str(lore / page["file"])
        for source in page["sources"]:
            resource, _, anchor = source["resource"].partition("#")
            resource = resource.strip()
            source["anchor"] = anchor
            source["href"] = href_for(links["lore"], resource) if resource else ""
            source["abs"] = str(lore / resource) if resource else ""
            source["exists"] = bool(resource) and (lore / resource).exists()
    for record in raw:
        record["href"] = href_for(links["raw"], record["name"])
        record["abs"] = str(lore / "raw" / record["name"])
    # health() must run before pages are stripped down for the payload: it
    # deliberately mutates log["last_lint"]["days"] as a documented side
    # effect, and _schema() reads page["fields"] (raw frontmatter) to check
    # for pre-0.3 legacy keys.
    scores = health(pages, index, log, raw, graph, today)
    for page in pages:                 # scratch keys the health checks needed; not payload
        page.pop("fields", None)
        page.pop("index_deprecated_section", None)
    return {
        "meta": {
            "lore_name": lore.name,
            "lore_path": str(lore),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "git": git_info(lore),
            "links": links,
            "counts": {"pages": len(pages),
                       "ghosts": sum(1 for n in graph["nodes"] if n["ghost"]),
                       "edges": len(graph["edges"]),
                       "raw": len(raw)},
        },
        "pages": pages,
        "graph": graph,
        "index": index,
        "log": log,
        "raw": raw,
        "health": scores,
        "stats": statistics(pages, index, log, raw, graph),
    }


def _append_line(path, line):
    """Append `line` to `path` unless it is already one of its lines."""
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if line in existing.split("\n"):
        return False
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    path.write_text(f"{existing}{prefix}{line}\n", encoding="utf-8")
    return True


def ensure_ignored(lore, out_path):
    """Keep the dashboard out of git and out of ripgrep. Returns files touched."""
    lore, out_path = Path(lore).resolve(), Path(out_path).resolve()
    if lore not in out_path.parents:
        return []
    line = out_path.name
    touched = []
    if _append_line(lore / ".ignore", line):
        touched.append(".ignore")
    if git_info(lore)["repo"] and _append_line(lore / ".gitignore", line):
        touched.append(".gitignore")
    return touched


def main(argv=None):
    if sys.version_info < (3, 10):
        print("error: python 3.10+ required", file=sys.stderr)
        sys.exit(1)
    parser = argparse.ArgumentParser(
        description="Render a lore as one self-contained HTML dashboard.")
    parser.add_argument("lore", help="path to the lore folder (needs wiki/ and index.md)")
    parser.add_argument("-o", "--output", default=None,
                        help="output HTML file (default: <lore>/dashboard.html)")
    args = parser.parse_args(argv)

    lore = Path(args.lore).expanduser().resolve()
    if not (lore / "wiki").is_dir() or not (lore / "index.md").is_file():
        print(f"error: {lore} is not a lore (needs wiki/ and index.md)", file=sys.stderr)
        sys.exit(2)

    out_path = Path(args.output).expanduser().resolve() if args.output else lore / DEFAULT_OUTPUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(lore, out_path.parent, date.today())
    out_path.write_text(build_html(payload), encoding="utf-8")
    ensure_ignored(lore, out_path)

    counts = payload["meta"]["counts"]
    print(f"{out_path}: {counts['pages']} pages, {counts['edges']} links, "
          f"health {payload['health']['score']}/100")
    return 0


if __name__ == "__main__":
    sys.exit(main())
