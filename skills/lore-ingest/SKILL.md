---
name: lore-ingest
description: Use when the user runs /lore:lore-ingest — find files in the lore's raw/ inbox that are not yet in log.md, distill each into wiki pages by content type, update index.md and log.md, and commit.
---

# /lore:lore-ingest

Follow the `lore` skill for all conventions. Lore path comes from `~/.claude/lore.json`; read `$LORE/CLAUDE.md` first — where it differs from these defaults, it wins.

Default flow is interactive: after each file, surface the key takeaways in the report so the user can steer emphasis before the next one. If the user asks for a batch run, process everything straight through and report once at the end.

## 1. Find new files

```bash
find "$LORE/raw" -type f -printf '%P\n'
```
(`find`, not `ls` — a dropped folder of documents and dotfiles must be seen too; paths are relative to `raw/`.)

A file counts as already-processed iff `log.md` contains an entry heading whose filename field is exactly that filename: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`. Match the whole field, anchored at both ends — never a substring: `spec.pdf` occurs inside the heading for `v2_spec.pdf`, so a substring test (`rg -F "spec.pdf"`) would classify a newly dropped `spec.pdf` as already processed and silently never ingest it. Everything else is NEW.

`rg -F` cannot anchor, so test each candidate with the filename regex-escaped:

```bash
python3 - "$LORE/log.md" "<filename>" <<'PY'
import re, sys
log = open(sys.argv[1], encoding='utf-8').read()
pat = r'^## \[[0-9-]{10}\] (?:ingest|skip) \| ' + re.escape(sys.argv[2]) + r'\s*$'
print("PROCESSED" if re.search(pat, log, re.M) else "NEW")
PY
```

**Re-ingest:** if the user names a specific file, process it regardless of the ledger and append a fresh `ingest` entry — that is how a page written under a limitation (e.g. a `card` written while openpyxl was absent) gets upgraded.

**Existing notes:** also treat any `$LORE/wiki/*.md` with no YAML frontmatter as new — add frontmatter, an `index.md` line, and an `ingest` log entry (§9 bootstrapping: notes copied in from a prior system).

If no new files: report "nothing to ingest" and stop (no commit).

## 2. Process each new file by type

Before creating ANY page: `rg -i` the candidate title in `$LORE/index.md` and over `wiki/` filenames — if a page on that topic exists, UPDATE it (merge new facts, bump `freshness`, add the new `source`) instead of creating a duplicate. When updating, never rewrite, reorder, or delete a `## My Take` section — those are human-owned; add your new material outside them.

- **PDF** — Read it directly (page ranges for large files). Write one `type: source` page summarizing the document, plus `type: concept` pages for major topics (typically one per chapter/subsystem; merge into existing concept pages when they exist). Verify any table/register values against the PDF page before writing them; cite `raw/<file>#p<n>` on every hard number.
- **Image (png/jpg/gif/webp/svg)** — Read it. Write/extend a page with a structured caption: image kind (schematic / scope shot / photo / diagram), visible labels, designators, settings, and what it shows. The caption is for retrieval only — note in the page: "re-read the image for analysis; do not trust this caption for connectivity."
- **Spreadsheet (xlsx/xls/csv/tsv)** — Write a `type: card` page: sheet names, column names, row count, ~5 sample rows, apparent purpose. Get these via python3 (csv module; openpyxl or duckdb for xlsx if available — if not available for xlsx, record what could be read and note the limitation on the card). Never paste large tables.
- **Markdown / txt / html** — Read directly; write/extend `source`/`concept` pages. For html, ignore boilerplate; distill content.
- **Anything else** — do not guess. Append a `skip` entry to `log.md` with the reason and list it in the final report.

Every page gets full frontmatter (`type`, `title`, `source`, `captured`, `freshness`, `trust: extracted`) and wikilinks to related existing pages. If a new source contradicts an existing page, add a `> ⚠ CONTRADICTION:` block to that page — do not pick a winner.

## 3. Update index.md and log.md

- Add one line per new page under the right `##` group (create the group if needed); respect the caps from the `lore` skill.
- Append one `ingest` entry per processed file:
  `## [YYYY-MM-DD] ingest | <filename>` + one line: pages created/updated.

## 4. Commit and report

```bash
cd "$LORE" && git add -A && git commit -m "ingest: <filenames>"
```

Report to the user: files processed, pages created/updated, skips (with reasons), contradictions flagged.
