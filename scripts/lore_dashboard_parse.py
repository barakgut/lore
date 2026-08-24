#!/usr/bin/env python3
"""Read a lore off disk: pages, index, log, raw ledger, wikilink graph.

Standalone, human-only tooling — not part of the lore plugin contract.
Nothing here raises on malformed input: bad data becomes a fallback value
that the health checks report as an offender.
"""
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
