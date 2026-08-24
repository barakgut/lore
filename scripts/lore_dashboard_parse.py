#!/usr/bin/env python3
"""Read a lore off disk: pages, index, log, raw ledger, wikilink graph.

Standalone, human-only tooling — not part of the lore plugin contract.
Nothing here raises on malformed input: bad data becomes a fallback value
that the health checks report as an offender.
"""
import hashlib
import re
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
FOOTNOTE_RE = re.compile(r"\[\^([^\]]+)\]")
CONTRADICTION_RE = re.compile(r"^>\s*⚠\s*CONTRADICTION", re.MULTILINE)
MY_TAKE_RE = re.compile(r"^##+\s*My Take\s*$", re.MULTILINE | re.IGNORECASE)

PAGE_TYPES = ("concept", "source", "answer", "decision", "card")
PAGE_STATUSES = ("draft", "stable", "deprecated")
LEGACY_FIELDS = ("source", "captured", "freshness", "trust", "verified", "stale_after")


def _scalar(value):
    """One frontmatter scalar: trailing comment dropped, quotes stripped."""
    value = value.strip()
    if value[:1] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end != -1 else value[1:]
    cut = value.find(" #")
    if cut != -1:
        value = value[:cut].rstrip()
    return value


def _inline_list(value):
    inner = value.strip()[1:-1].strip()
    return [_scalar(item) for item in inner.split(",") if item.strip()] if inner else []


def _read_block(lines, start):
    """Read the indented block at `lines[start:]`.

    Returns (value, next_index). The value is a list when the block's first
    content line starts with `-`, otherwise a dict of nested scalars.
    """
    items, mapping, current = [], {}, None
    i = start
    while i < len(lines):
        line = lines[i]
        if line.strip() and not line[0].isspace():
            break                                   # dedented back to top level
        i += 1
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-"):
            entry = stripped[1:].strip()
            if ":" in entry:
                key, _, value = entry.partition(":")
                current = {key.strip(): _scalar(value)}
                items.append(current)
            else:
                items.append(_scalar(entry))
                current = None
        elif ":" in stripped:
            key, _, value = stripped.partition(":")
            (current if current is not None else mapping)[key.strip()] = _scalar(value)
    return (items if items else mapping), i


def parse_yaml_block(fm_text):
    """Parse the fixed lore frontmatter schema. Not a general YAML parser."""
    data = {}
    lines = fm_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#") or line[0].isspace():
            continue
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key, rest = key.strip(), rest.strip()
        if rest.startswith("["):
            data[key] = _inline_list(rest)
        elif rest:
            data[key] = _scalar(rest)
        else:
            data[key], i = _read_block(lines, i)
    return data


def parse_frontmatter(text):
    """Return (fields, body, ok). ok is False when there is no --- block."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text, False
    try:
        return parse_yaml_block(match.group(1)), text[match.end():], True
    except Exception:                                # never let a page kill the run
        return {}, text[match.end():], False


def link_target_id(raw_target):
    """Wikilink target -> page id: drop alias/anchor, spaces become underscores."""
    target = raw_target.split("|")[0].split("#")[0].strip()
    return target.replace(" ", "_")


def _as_list(value):
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _sources(value):
    """Normalise sources[] to a list of dicts; a bare string keeps its resource."""
    out = []
    for entry in _as_list(value):
        if isinstance(entry, dict):
            out.append({"id": entry.get("id", ""),
                        "resource": entry.get("resource", ""),
                        "title": entry.get("title", "")})
        else:
            out.append({"id": "", "resource": str(entry), "title": ""})
    return out


def load_pages(lore):
    """One record per wiki/*.md, sorted by page id."""
    pages = []
    for path in sorted((Path(lore) / "wiki").glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        fields, body, ok = parse_frontmatter(text)
        outlinks, seen = [], set()
        for raw_target in WIKILINK_RE.findall(body):
            target = link_target_id(raw_target)
            if target and target not in seen:
                seen.add(target)
                outlinks.append(target)
        pages.append({
            "id": path.stem,
            "file": f"wiki/{path.name}",
            "title": fields.get("title") or path.stem.replace("_", " "),
            "type": fields.get("type", "") if isinstance(fields.get("type", ""), str) else "",
            "status": fields.get("status") or "stable",
            "description": fields.get("description", ""),
            "tags": [str(t) for t in _as_list(fields.get("tags"))],
            "sources": _sources(fields.get("sources")),
            "generated": {"by": _as_dict(fields.get("generated")).get("by", ""),
                          "at": _as_dict(fields.get("generated")).get("at", "")},
            "body": body,
            "outlinks": outlinks,
            "inlinks": [],
            "index_group": None,
            "index_hook": None,
            "footnote_ids": list(dict.fromkeys(FOOTNOTE_RE.findall(body))),
            "contradictions": len(CONTRADICTION_RE.findall(body)),
            "my_take": bool(MY_TAKE_RE.search(body)),
            "fm_ok": ok,
            "fields": fields,          # raw frontmatter, for the schema health checks
        })
    return pages


INDEX_ENTRY_RE = re.compile(r"^- \[(?P<title>[^\]]+)\]\((?P<target>[^)]+)\)\s*(?:—|--|-)?\s*(?P<hook>.*)$")
INDEX_HEADING_RE = re.compile(r"^##\s+(?P<heading>.+?)\s*$")
LOG_HEADING_RE = re.compile(
    r"^##\s+\[(?P<date>\d{4}-\d{2}-\d{2})\]\s+"
    r"(?P<verb>ingest|lint|skip|init|answer|discard)\s+\|\s+(?P<subject>.+?)\s*$")
SHA_RE = re.compile(r"sha256:([0-9a-f]{6,64})")
LINT_COUNTS_RE = re.compile(r"(\d+)\s+fixed,\s*(\d+)\s+reported")
INDEX_ENTRY_CAP = 200
INDEX_LINE_TARGET = 200


def parse_index(lore, pages):
    """Parse index.md into groups/entries; stamp group+hook onto page records."""
    text = _read_text(Path(lore) / "index.md")
    by_id = {p["id"]: p for p in pages}
    groups, current = [], None
    entry_count, listed = 0, set()
    ghost_entries, over_cap = [], []
    for line in text.split("\n"):
        heading = INDEX_HEADING_RE.match(line)
        if heading:
            current = {"heading": heading.group("heading"),
                       "deprecated": heading.group("heading").strip().lower() == "deprecated",
                       "entries": []}
            groups.append(current)
            continue
        match = INDEX_ENTRY_RE.match(line.rstrip())
        if not match:
            continue
        if current is None:
            current = {"heading": "", "deprecated": False, "entries": []}
            groups.append(current)
        target = match.group("target").strip()
        page_id = Path(target).stem
        entry = {"title": match.group("title").strip(), "target": target, "id": page_id,
                 "hook": match.group("hook").strip(), "chars": len(line.rstrip()),
                 "exists": page_id in by_id}
        current["entries"].append(entry)
        entry_count += 1
        if entry["exists"]:
            listed.add(page_id)
            page = by_id[page_id]
            if page["index_group"] is None:
                page["index_group"] = current["heading"]
                page["index_hook"] = entry["hook"]
                page["index_deprecated_section"] = current["deprecated"]
        else:
            ghost_entries.append({"title": entry["title"], "target": target})
        if entry["chars"] > INDEX_ENTRY_CAP:
            over_cap.append({"title": entry["title"], "chars": entry["chars"]})
    misplaced = [p["id"] for p in pages
                 if p["status"] == "deprecated" and p["id"] in listed
                 and not p.get("index_deprecated_section")]
    return {
        "line_count": len(text.split("\n")),
        "entry_count": entry_count,
        "groups": groups,
        "orphans": [p["id"] for p in pages if p["id"] not in listed],
        "ghost_entries": ghost_entries,
        "over_cap": over_cap,
        "misplaced_deprecated": misplaced,
    }


def _read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_log(lore):
    """Parse log.md into entries (newest first), malformed lines, and last_lint."""
    lines = _read_text(Path(lore) / "log.md").split("\n")
    entries, malformed = [], []
    for number, line in enumerate(lines, start=1):
        if not line.startswith("## "):
            continue
        match = LOG_HEADING_RE.match(line.rstrip())
        if not match:
            malformed.append({"line": number, "text": line.rstrip()})
            continue
        detail_lines = []
        for follow in lines[number:]:
            if follow.startswith("## ") or (not follow.strip() and detail_lines):
                break
            if follow.strip():
                detail_lines.append(follow.strip())
        detail = " ".join(detail_lines)
        sha = SHA_RE.search(detail)
        counts = LINT_COUNTS_RE.search(f"{match.group('subject')} {detail}")
        entries.append({
            "line": number,
            "date": match.group("date"),
            "verb": match.group("verb"),
            "subject": match.group("subject").strip(),
            "detail": detail,
            "sha": sha.group(1)[:12] if sha else None,
            "fixed": int(counts.group(1)) if counts else None,
            "reported": int(counts.group(2)) if counts else None,
        })
    entries.sort(key=lambda e: (e["date"], e["line"]), reverse=True)
    last_lint = next((e for e in entries if e["verb"] == "lint"), None)
    return {
        "entries": entries,
        "malformed": malformed,
        "last_lint": ({"date": last_lint["date"], "fixed": last_lint["fixed"],
                       "reported": last_lint["reported"], "days": None}
                      if last_lint else None),
    }


def sha12(path):
    """First 12 hex chars of the file's sha256 — the ledger's hash convention."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()[:12]


def scan_raw(lore, log, pages):
    """Every file under raw/ with its ledger state and derived pages."""
    lore = Path(lore)
    latest = {}                                     # basename -> newest ingest/skip entry
    by_line = sorted(log["entries"], key=lambda e: e["line"], reverse=True)
    for entry in by_line:                           # append position, not calendar date
        if entry["verb"] in ("ingest", "skip"):
            latest.setdefault(entry["subject"], entry)
    derived = {}
    for page in pages:
        for source in page["sources"]:
            resource = source.get("resource", "").split("#")[0].strip()
            if resource:
                derived.setdefault(Path(resource).name, []).append(page["id"])
    records = []
    raw_dir = lore / "raw"
    for path in sorted(p for p in raw_dir.rglob("*") if p.is_file()):
        name = path.relative_to(raw_dir).as_posix()
        entry = latest.get(path.name)
        digest = sha12(path)
        if entry is None:
            state, skip_reason = "NEW", None
        elif entry["verb"] == "skip":
            state, skip_reason = "SKIPPED", entry["detail"] or None
        elif entry["sha"] and entry["sha"] == digest:
            state, skip_reason = "PROCESSED", None
        else:
            state, skip_reason = "CHANGED", None
        records.append({
            "name": name,
            "ext": path.suffix.lower(),
            "size": path.stat().st_size,
            "sha": digest,
            "state": state,
            "latest_date": entry["date"] if entry else None,
            "skip_reason": skip_reason,
            "pages": sorted(dict.fromkeys(derived.get(path.name, []))),
        })
    order = {"NEW": 0, "CHANGED": 1, "SKIPPED": 2, "PROCESSED": 3}
    records.sort(key=lambda r: (order[r["state"]], r["name"]))
    return records
