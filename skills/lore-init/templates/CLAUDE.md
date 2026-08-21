# Lore — Schema

This folder is a lore — a second brain, Long-term Organized Reference — maintained by Claude Code (`lore` plugin).
This file is the schema: the full rules for how the lore is structured and
maintained. It is auto-loaded whenever Claude Code runs inside this folder, and
the plugin's skills read it from linked projects. Evolve it freely with the
agent as conventions settle — where this file differs from the plugin's
built-in defaults, this file wins.

## Layout

- `raw/` — inbox + originals: drop any file here (PDF, image, xlsx/csv, md, txt, saved HTML). IMMUTABLE: never edit or delete anything here. Originals are ground truth and always win over derived wiki text.
- `wiki/` — agent-maintained distilled pages; the lore itself.
- `index.md` — catalog: one line per page (`- [Title](wiki/Page.md) — hook`), grouped under `##` topic headings. Read first on every query. Hard cap <200 chars per entry: tighten the hook to fit. Target ~200 lines total; past that, never drop entries to fit — every page must stay reachable from the index. Report it and propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.
- `log.md` — append-only history; also the processed-file ledger. A `raw/` file counts as already-processed iff `log.md` contains an entry heading whose filename field is exactly that filename: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`. Match the whole field, anchored at both ends — never a substring: `spec.pdf` occurs inside the heading for `v2_spec.pdf`, so a substring test (`rg -F "spec.pdf"`) would classify a newly dropped `spec.pdf` as already processed and silently never ingest it.
- `CLAUDE.md` — this schema.

## Wiki page schema

Every `wiki/*.md` starts with YAML frontmatter:

```yaml
---
type: concept | source | answer | decision | card    # mandatory, exactly one
title: Human Readable Title
source: raw/<file>#p<n>        # origin, with page/sheet anchor when applicable
captured: YYYY-MM-DD           # date ingested
freshness: YYYY-MM-DD          # date last verified against source
trust: extracted | inferred | human
---
```

- `concept` — topic distilled across sources. `source` — summary of one raw file. `answer` — promoted Q&A result. `decision` — recorded choice and why. `card` — spreadsheet metadata card.
- Wikilinks `[[Page_Title]]` between pages are the knowledge-graph edges. Filename = title with underscores.

## log.md entry format

`## [YYYY-MM-DD] <ingest|lint|skip|init|answer> | <subject>` + one or two lines of detail.

## Query (retrieval ladder — cheapest first, stop when grounded)

1. Read `index.md`; pick candidate pages.
2. `rg -i '<term>' wiki/` for exact terms, part numbers, register names.
3. Read the whole matched page(s); follow wikilinks as needed.
4. Open the raw original when wiki text is insufficient or precision matters.

Never load the whole wiki into context. The index is the map.

## Answering rules

- Cite every claim: `raw/<file>#p<n>`, sheet/cell, or `wiki/<page>`.
- Promote non-trivial answers to `type: answer` pages (+ index line + `answer` log entry + commit) so they are never re-derived.
- Contradictions are never silently resolved: `> ⚠ CONTRADICTION: <A> [[Source_A]]; <B> [[Source_B]]`.
- `## My Take` sections are human-owned: never rewrite, reorder, or delete them.
- Numeric questions about spreadsheets: query the raw file on demand (python3/duckdb if available); never paste large tables into wiki pages.

## Git

Every mutation (init, ingest, lint fix, answer promotion) ends with a commit here, message prefixed `init:`, `ingest:`, `lint:`, or `answer:`.

## Operations

`/lore:lore-ingest` — process new `raw/` files into the wiki. `/lore:lore-lint` — health check. `/lore:lore-link` — point a project at this lore.
