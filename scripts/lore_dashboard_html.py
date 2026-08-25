#!/usr/bin/env python3
"""Assemble the self-contained dashboard HTML from the payload plus assets."""
import html
import json
import re
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "dashboard_assets"
SHELL = "shell.html"
CSS_ASSETS = ["app.css"]
# Load order matters: core.js defines the helpers every later file calls,
# md.js and search.js must load before views.js (the page view calls
# renderMarkdown, the search view calls searchPages/highlight), and app.js
# runs last because it reads the finished view registry.
JS_ASSETS = ["core.js", "md.js", "search.js", "views.js", "app.js"]
PLACEHOLDER_RE = re.compile(r"__(TITLE|STYLE|SCRIPT|DATA)__")


def _read_asset(assets_dir, name):
    path = Path(assets_dir) / name
    if not path.is_file():
        raise FileNotFoundError(f"dashboard asset missing: {path}")
    return path.read_text(encoding="utf-8")


def encode_payload(payload):
    """Compact JSON safe to inline in a <script type="application/json"> block."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")


def build_html(payload, assets_dir=ASSETS_DIR):
    """The finished page. Every placeholder is substituted in a single pass."""
    values = {
        # TITLE is payload-derived (lore_name comes from a directory basename,
        # which is not restricted to HTML-safe characters) and lands inside
        # <title>__TITLE__</title>, so it must be HTML-escaped like DATA is
        # JSON/`<`-escaped. STYLE and SCRIPT are our own asset files, not
        # payload-derived — escaping them would corrupt the CSS/JS.
        "TITLE": html.escape(f"{payload['meta']['lore_name']} — lore dashboard"),
        "STYLE": "\n".join(_read_asset(assets_dir, name) for name in CSS_ASSETS),
        "SCRIPT": "\n".join(_read_asset(assets_dir, name) for name in JS_ASSETS),
        "DATA": encode_payload(payload),
    }
    shell = _read_asset(assets_dir, SHELL)
    return PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], shell)
