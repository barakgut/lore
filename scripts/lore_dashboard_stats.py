#!/usr/bin/env python3
"""Snapshot statistics for a lore. No history, no trends — one point in time."""
from collections import Counter
from datetime import date

TOP_N = 10


def _rows(counter):
    """Count rows sorted by count desc, then key asc."""
    return [{"key": key, "count": count}
            for key, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


def _iso_week(day):
    try:
        year, week, _ = date.fromisoformat(day).isocalendar()
    except (TypeError, ValueError):
        return None
    return f"{year}-W{week:02d}"


def statistics(pages, index, log, raw, graph):
    by_type = Counter(p["type"] or "unknown" for p in pages)
    by_status = Counter(p["status"] for p in pages)
    by_generator = Counter(p["generated"]["by"] or "unknown" for p in pages)
    tags = Counter(tag for p in pages for tag in p["tags"])
    untagged = sorted(p["id"] for p in pages if not p["tags"])

    ext_counter, ext_bytes = Counter(), Counter()
    for record in raw:
        ext_counter[record["ext"] or "(none)"] += 1
        ext_bytes[record["ext"] or "(none)"] += record["size"]
    state_counter = Counter(record["state"] for record in raw)

    cited = [r for r in raw if r["pages"]]
    pages_per_raw = sorted(({"file": r["name"], "count": len(r["pages"])} for r in cited),
                           key=lambda row: (-row["count"], row["file"]))[:TOP_N]

    nodes, edges = graph["nodes"], graph["edges"]
    ghosts = sum(1 for n in nodes if n["ghost"])
    hubs = sorted(({"id": n["id"], "title": n["title"], "count": n["in"]}
                   for n in nodes if n["in"]),
                  key=lambda row: (-row["count"], row["id"]))[:TOP_N]

    weeks = Counter(week for week in (_iso_week(e["date"]) for e in log["entries"]
                                      if e["verb"] == "ingest") if week)

    return {
        "pages_by_type": _rows(by_type),
        "pages_by_status": _rows(by_status),
        "pages_by_generator": _rows(by_generator),
        "raw_by_ext": [{"key": row["key"], "count": row["count"], "bytes": ext_bytes[row["key"]]}
                       for row in _rows(ext_counter)],
        "raw_by_state": _rows(state_counter),
        "raw_total_bytes": sum(r["size"] for r in raw),
        "coverage": {
            "raw_with_pages": len(cited),
            "raw_without_pages": len(raw) - len(cited),
            "pages_per_raw": pages_per_raw,
            "uncited": sorted(r["name"] for r in raw if not r["pages"]),
        },
        "graph": {
            "nodes": len(nodes),
            "pages": len(pages),
            "ghosts": ghosts,
            "edges": len(edges),
            "avg_degree": round(2 * len(edges) / len(nodes), 1) if nodes else 0.0,
            "components": graph["components"],
            "hubs": hubs,
        },
        "tags": _rows(tags),
        "untagged": untagged,
        "log": {
            "by_verb": _rows(Counter(e["verb"] for e in log["entries"])),
            "ingests_per_week": [{"week": week, "count": weeks[week]} for week in sorted(weeks)],
            "answers": sum(1 for e in log["entries"] if e["verb"] == "answer"),
            "discards": sum(1 for e in log["entries"] if e["verb"] == "discard"),
            "entries": len(log["entries"]),
            "malformed": len(log["malformed"]),
        },
    }
