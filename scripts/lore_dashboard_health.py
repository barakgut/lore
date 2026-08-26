#!/usr/bin/env python3
"""Mechanical health score for a lore: six weighted dimensions, 0-100.

Only checks a program can decide are computed. The judgment-only lint checks
(active contradiction cross-check, footnote discipline judgment, missing
concept pages, missing cross-references, knowledge gaps, discard candidates)
are never scored — the dashboard shows the last lint entry's counts instead.
Index drift comes from lore_dashboard_parse, which imports scripts/lore_index.py
for it; when that import fails the check is reported as unavailable and scores
clean.
"""
import math
import re
from datetime import date

from lore_dashboard_parse import (
    INDEX_ENTRY_CAP,
    INDEX_LINE_TARGET,
    LEGACY_FIELDS,
    PAGE_STATUSES,
    PAGE_TYPES,
)

WEIGHTS = [
    ("integrity", "Integrity", 25),
    ("schema", "Schema", 20),
    ("connectivity", "Connectivity", 15),
    ("provenance", "Provenance", 15),
    ("inbox", "Inbox currency", 15),
    ("issues", "Open issues", 10),
]
PROVENANCE_EXEMPT_TYPES = ("decision",)
REQUIRED_FIELDS = ("title", "description", "tags")
LINT_GRACE_DAYS = 30
LINT_PENALTY_SPAN = 60
NORMALISE_RE = re.compile(r"[^a-z0-9]+")


def _ratio(count, denominator):
    if denominator <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - count / denominator))


def _check(key, label, offenders, denominator, score=None):
    return {"key": key, "label": label,
            "score": _ratio(len(offenders), denominator) if score is None else max(0.0, min(1.0, score)),
            "offenders": offenders}


def _page_offender(page, detail):
    return {"ref": page["id"], "kind": "page", "detail": detail}


def _days_between(older, newer):
    try:
        return (newer - date.fromisoformat(older)).days
    except (TypeError, ValueError):
        return 0


def _integrity(pages, index, graph):
    ids = {p["id"] for p in pages}
    total = len(pages)
    dead = []
    for page in pages:
        missing = [t for t in page["outlinks"] if t not in ids]
        if missing:
            dead.append(_page_offender(page, "dead wikilinks: " + ", ".join(sorted(missing))))
    buckets = {}
    for page in pages:
        buckets.setdefault(NORMALISE_RE.sub("", page["title"].lower()), []).append(page)
    duplicates = [_page_offender(p, f"title collides with {len(group) - 1} other page(s)")
                  for group in buckets.values() if len(group) > 1 for p in group]
    drift = index.get("drift")
    drift_label = "Index drift" if drift is not None else "Index drift (lore_index.py unavailable)"
    drift_offenders = [{"ref": rel, "kind": "index", "detail": "differs from a fresh lore_index.py render"}
                       for rel in (drift or [])]
    return [
        _check("orphans", "Orphan pages",
               [{"ref": i, "kind": "page", "detail": "no line in index.md"} for i in index["orphans"]],
               total),
        _check("ghost_entries", "Ghost index entries",
               [{"ref": e["title"], "kind": "index", "detail": f"points at missing {e['target']}"}
                for e in index["ghost_entries"]],
               max(index["entry_count"], 1)),
        _check("dead_wikilinks", "Dead wikilinks", dead, total),
        _check("duplicate_titles", "Duplicate titles", duplicates, total),
        _check("deprecated_placement", "Deprecated pages misplaced in the index",
               [{"ref": i, "kind": "page", "detail": "index line is outside ## Deprecated"}
                for i in index["misplaced_deprecated"]],
               total),
        _check("index_drift", drift_label, drift_offenders, max(len(drift_offenders), 1)),
    ]


def _schema(pages):
    total = len(pages)
    required, legacy, source_entries, footnotes, statuses = [], [], [], [], []
    for page in pages:
        problems = []
        if not page["fm_ok"]:
            problems.append("no valid frontmatter block")
        if page["type"] not in PAGE_TYPES:
            problems.append(f"type: {page['type'] or 'missing'!s}")
        problems += [f"{field} missing" for field in REQUIRED_FIELDS
                     if not page.get(field) or (field == "tags" and not page["tags"])]
        if not page["generated"]["by"]:
            problems.append("generated.by missing")
        if not page["generated"]["at"]:
            problems.append("generated.at missing")
        if problems:
            required.append(_page_offender(page, "; ".join(problems)))
        found_legacy = [f for f in LEGACY_FIELDS if f in page["fields"]]
        if found_legacy:
            legacy.append(_page_offender(page, "pre-0.3 fields: " + ", ".join(found_legacy)))
        if any(not source["resource"] for source in page["sources"]):
            source_entries.append(_page_offender(page, "sources[] entry without a resource"))
        source_ids = {source["id"] for source in page["sources"] if source["id"]}
        unmatched = [f for f in page["footnote_ids"] if f not in source_ids]
        if unmatched:
            footnotes.append(_page_offender(page, "footnotes with no sources[].id: "
                                            + ", ".join(sorted(set(unmatched)))))
        if page["status"] not in PAGE_STATUSES:
            statuses.append(_page_offender(page, f"invalid status: {page['status']}"))
    return [
        _check("required_fields", "Frontmatter fields", required, total),
        _check("legacy_fields", "Unsupported pre-0.3 fields", legacy, total),
        _check("sources_entries", "sources[] entries", source_entries, total),
        _check("footnote_ids", "Footnotes resolve to a source id", footnotes, total),
        _check("status_value", "status value", statuses, total),
    ]


def _connectivity(pages, graph):
    total = len(pages)
    isolated = [{"ref": i, "kind": "page", "detail": "no inbound or outbound wikilinks"}
                for i in graph["isolated"]]
    no_inbound = [_page_offender(p, "no page links here") for p in pages if not p["inlinks"]]
    extra_components = max(0, graph["components"] - 1)
    allowance = max(1, math.ceil(total / 10)) if total else 1
    return [
        _check("isolated", "Isolated pages", isolated, total),
        _check("no_inbound", "Pages with no inbound link", no_inbound, total),
        _check("components", "Disconnected graph components",
               ([{"ref": "wiki/", "kind": "lore",
                  "detail": f"{graph['components']} disconnected components"}]
                if extra_components else []),
               0, score=1.0 - extra_components / allowance),
    ]


def _provenance(pages):
    total = len(pages)
    no_sources, missing_footnotes = [], []
    for page in pages:
        if not page["sources"]:
            exempt = (page["type"] in PROVENANCE_EXEMPT_TYPES
                      or (page["type"] == "answer" and page["generated"]["by"].startswith("human:")))
            if not exempt:
                no_sources.append(_page_offender(page, "no sources[]"))
        elif len(page["sources"]) >= 2 and not page["footnote_ids"]:
            missing_footnotes.append(
                _page_offender(page, f"{len(page['sources'])} sources, no [^id] footnotes"))
    return [
        _check("no_sources", "Pages without provenance", no_sources, total),
        _check("missing_footnotes", "Multi-source pages without footnotes", missing_footnotes, total),
    ]


def _inbox(raw):
    total = len(raw)
    stale = [{"ref": r["name"], "kind": "raw", "detail": r["state"].lower()}
             for r in raw if r["state"] in ("NEW", "CHANGED")]
    skipped = [{"ref": r["name"], "kind": "raw", "detail": r["skip_reason"] or "skipped"}
               for r in raw if r["state"] == "SKIPPED"]
    return [
        _check("new_or_changed", "Un-ingested or changed raw files", stale, total),
        _check("skipped", "Skipped raw files", skipped, total),
    ]


def _issues(pages, index, log, today):
    total = len(pages)
    contradictions = [_page_offender(p, f"{p['contradictions']} contradiction marker(s)")
                      for p in pages if p["contradictions"]]
    drafts = [_page_offender(p, "status: draft") for p in pages if p["status"] == "draft"]
    ungrouped = [_page_offender(p, "no group: in frontmatter")
                 for p in pages if p["status"] != "deprecated" and not p.get("group")]
    over_cap = [{"ref": e["title"], "kind": "index", "detail": f"{e['chars']} chars (cap <{INDEX_ENTRY_CAP})"}
                for e in index["over_cap"]]
    oversize = index["line_count"] > INDEX_LINE_TARGET
    if log["last_lint"]:
        days = _days_between(log["last_lint"]["date"], today)
        log["last_lint"]["days"] = days
    elif log["entries"]:
        days = _days_between(log["entries"][-1]["date"], today)
    else:
        days = 0
    lint_offenders = ([{"ref": "log.md", "kind": "lore", "detail": f"last lint {days} days ago"}]
                      if days > LINT_GRACE_DAYS else [])
    return [
        _check("contradictions", "Unresolved contradictions", contradictions, total),
        _check("drafts", "Draft pages", drafts, total),
        _check("ungrouped_pages", "Pages without a group", ungrouped, total),
        _check("index_entry_cap", "Index entries over the char cap", over_cap,
               max(index["entry_count"], 1)),
        _check("index_size", "Index size",
               ([{"ref": "index.md", "kind": "lore",
                  "detail": f"{index['line_count']} lines (target {INDEX_LINE_TARGET})"}]
                if oversize else []),
               0,
               score=1.0 if not oversize
               else 1.0 - (index["line_count"] - INDEX_LINE_TARGET) / INDEX_LINE_TARGET),
        _check("lint_age", "Time since the last lint", lint_offenders, 0,
               score=1.0 if days <= LINT_GRACE_DAYS
               else 1.0 - (days - LINT_GRACE_DAYS) / LINT_PENALTY_SPAN),
    ]


def health(pages, index, log, raw, graph, today):
    """The payload's health object: 0-100 score plus per-check offender lists."""
    checks_by_key = {
        "integrity": _integrity(pages, index, graph),
        "schema": _schema(pages),
        "connectivity": _connectivity(pages, graph),
        "provenance": _provenance(pages),
        "inbox": _inbox(raw),
        "issues": _issues(pages, index, log, today),
    }
    dimensions = []
    for key, label, weight in WEIGHTS:
        checks = checks_by_key[key]
        score = sum(c["score"] for c in checks) / len(checks) if checks else 1.0
        dimensions.append({"key": key, "label": label, "weight": weight,
                           "score": round(score, 4), "checks": checks})
    total_weight = sum(w for _, _, w in WEIGHTS)
    overall = sum(d["weight"] * d["score"] for d in dimensions) / total_weight
    return {"score": round(overall * 100), "dimensions": dimensions,
            "last_lint": log["last_lint"]}
