# Lore — Schema

This folder is a lore — a second brain, Long-term Organized Reference — maintained by Claude Code (`lore` plugin).
This file is the schema: the full rules for how the lore is structured and
maintained. It is auto-loaded whenever Claude Code runs inside this folder, and
the plugin's skills read it from linked projects. Evolve it freely with the
agent as conventions settle — where this file differs from the plugin's
built-in defaults, this file wins.

## Layout

- `raw/` — inbox + originals: drop any file here (PDF, image, xlsx/csv, md, txt, saved HTML). IMMUTABLE: the agent never edits or deletes anything here (the plugin's PreToolUse hook denies file edits under raw/). Originals are ground truth and always win over derived wiki text. Replacing a file with a newer version is fine — the next ingest detects it by content hash and updates the affected pages.
- `wiki/` — agent-maintained distilled pages; the lore itself.
- `index.md` — catalog: one line per page (`- [Title](wiki/Page.md) — hook`), grouped under `##` topic headings; the hook is the page's `description`. Read first on every query. Hard cap <200 chars per entry: tighten the hook to fit. Target ~200 lines total; past that, never drop entries to fit — every page must stay reachable from the index. Report it and propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`. Deprecated pages keep their line under a `## Deprecated` section at the bottom.
- `log.md` — append-only history; also the processed-file ledger. A `raw/` file counts as already-processed iff `log.md` contains an entry heading whose filename field is exactly that filename: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`. Match the whole field, anchored at both ends — never a substring: `spec.pdf` occurs inside the heading for `v2_spec.pdf`, so a substring test (`rg -F "spec.pdf"`) would classify a newly dropped `spec.pdf` as already processed and silently never ingest it. The latest `ingest` entry's detail line records the file's `sha256:<first 12 hex>` content hash; a mismatch with the current file means CHANGED — the next ingest updates the affected pages.
- `CLAUDE.md` — this schema.

## Wiki page schema

Every `wiki/*.md` starts with YAML frontmatter:

```yaml
---
type: concept | source | answer | decision | card    # mandatory, exactly one
title: Human Readable Title
description: One-line summary — reused verbatim as the page's index-line hook
tags: [short, lowercase, topics]
sources:                          # every raw origin of this page
  - id: spec                      # short slug; mandatory when the body cites [^id]
    resource: raw/spec.pdf#p12    # path, with page/sheet anchor when applicable
    title: Optional Source Title  # optional human-readable name
generated:
  by: lore/<model-id>             # or human:<git user.name> — never an email
  at: YYYY-MM-DD
status: draft | stable | deprecated    # optional; absent means stable
---
```

- `concept` — topic distilled across sources. `source` — summary of one raw file. `answer` — promoted Q&A result. `decision` — recorded choice and why. `card` — spreadsheet metadata card.
- Per-claim footnotes: a page with one `sources` entry uses none — claims are implicitly from it (inline `#p<n>` anchors where precision matters). A page with 2+ entries ends every nontrivial claim with `[^<id>]` keyed to a `sources[].id`; no footnote-definition block — ids resolve against the frontmatter.
- Wikilinks `[[Page_Title]]` between pages are the knowledge-graph edges. Filename = title with underscores.

## log.md entry format

`## [YYYY-MM-DD] <ingest|lint|skip|init|answer|discard> | <subject>` + one or two lines of detail. `ingest` detail lines carry `sha256:<first 12 hex>` of the raw file.

## Query (retrieval ladder — cheapest first, stop when grounded)

1. Read `index.md`; pick candidate pages. Skip `## Deprecated` unless the question is explicitly about superseded state.
2. `rg -i '<term>' wiki/` for exact terms, part numbers, register names.
3. Read the whole matched page(s); follow wikilinks as needed.
4. Open the raw original when wiki text is insufficient or precision matters.

Never load the whole wiki into context. The index is the map.

## Answering rules

- Cite every claim: `raw/<file>#p<n>`, sheet/cell, or `wiki/<page>`; on multi-source pages the `[^id]` footnotes carry the attribution.
- Promote non-trivial answers to `type: answer` pages (+ index line + `answer` log entry + commit) so they are never re-derived.
- Contradictions are never silently resolved: `> ⚠ CONTRADICTION: <A> [[Source_A]]; <B> [[Source_B]]`.
- `## My Take` sections are human-owned: never rewrite, reorder, or delete them.
- Numeric questions about spreadsheets: query the raw file on demand (python3/duckdb if available); never paste large tables into wiki pages.

## Discard flow

- "discard page X" (soft — default): set `status: deprecated`, move the index line to `## Deprecated`, append a `discard` log entry, commit `discard: <page>`.
- "delete page X permanently" (hard — explicit ask only): remove the file and its index line, append a `discard | <page> (permanent)` log entry, commit. Inbound wikilinks are flagged by the next lint. Git history is the undo.

## Git

Every mutation (init, ingest, lint fix, answer promotion, discard) ends with a commit here, message prefixed `init:`, `ingest:`, `lint:`, `answer:`, or `discard:`.

If this lore was created with `--no-git` it is not a repository: do the work, skip the commit, and say so in the report. Never run `git init` on it.

## Operations

`/lore:lore-ingest` — process new or changed `raw/` files into the wiki. `/lore:lore-lint` — health check. `/lore:lore-link` — point a project at this lore.
