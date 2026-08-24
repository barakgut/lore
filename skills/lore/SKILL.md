---
name: lore
description: Use when answering any domain or knowledge question in a project linked to the lore (its CLAUDE.md contains a "lore:start" pointer block), and as the shared contract for all lore-* skills. Defines the lore folder layout, page schema, retrieval ladder, and citation rules.
---

# The Lore — Core Contract

## Finding the lore

Resolve `$LORE` with these rungs, first match wins. Never guess, never scan the disk, never fall back to `~/lore`. Whatever path a rung yields, expand `~` and resolve a relative path against cwd **before** testing it, so `$LORE` is always an absolute, symlink-resolved path.

1. **A path in the user's message** — e.g. `/lore:lore-ingest ~/wikis/hardware`.
2. **cwd is a lore** — `[ -f ./index.md ] && [ -d ./raw ] && [ -d ./wiki ]`. Use cwd.
3. **The project's link block** — the `<!-- lore:start -->` block in the project's `CLAUDE.md` names a path. It is usually already in context; otherwise read `./CLAUDE.md`.
4. **Nothing matched** — STOP. Tell the user, verbatim:

   > No lore found. `cd` into a lore, pass its path (`/lore:lore-ingest <path>`), or run `/lore:lore-link <path>` in this project.

Rung 2 needs all three of `index.md`, `raw/`, and `wiki/` — it fires on whatever directory the user happens to be in, and a lone `index.md` is a common filename. Rungs 1 and 3 need only `index.md`, because the path was named on purpose and the stricter test would reject a lore whose `raw/` the user has temporarily emptied.

If a rung matches but the path has no `index.md`, STOP and name the bad path — **never fall through** to the next rung. A stale `lore:start` block must be reported (suggest re-running `/lore:lore-link <path>`), not silently bypassed.

Rungs 2 and 3 cannot both match: a lore's own `CLAUDE.md` is its schema and never carries a `lore:start` marker.

Then read `<lore>/CLAUDE.md` — the lore's schema. The rules below are the defaults every new lore is seeded with; where the lore's CLAUDE.md differs (the user evolves it over time), the lore's CLAUDE.md wins.

## Folder contract

```
<lore>/
  CLAUDE.md         # the schema: full rules — authoritative when it differs from this skill
  index.md          # catalog: one line per wiki page — the primary retrieval tool
  log.md            # append-only history; also the processed-file ledger
  raw/              # inbox + originals. IMMUTABLE: never edit or delete anything here (a plugin hook denies Edit/Write into raw/)
  wiki/             # agent-maintained pages
```

## Page schema

Every `wiki/*.md` file starts with YAML frontmatter. This is the only supported
schema — pages carrying pre-0.3 fields (`captured`, `freshness`, `trust`,
singular `source:`) are unsupported; lint reports them, nothing migrates them.

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

- `concept` — a topic distilled across sources. `source` — summary of one raw file.
  `answer` — a promoted Q&A result. `decision` — a recorded choice and why.
  `card` — spreadsheet metadata card.
- `sources` may be empty or absent on hand-written pages, on `type: decision`
  pages with no raw origin, and on `answer` pages synthesized purely from
  other wiki pages; those cite `wiki/<page>` inline and carry
  `generated.by: human:<git user.name>` when a person wrote them.
- `generated` records who wrote the content: `lore/<model-id>` when the agent
  wrote it, `human:<git user.name>` when the user did. Never an email address.
- **Per-claim footnotes:** a page with one `sources` entry uses none — claims are
  implicitly from that source (inline `#p<n>` anchors where precision matters).
  A page with 2+ entries ends every nontrivial claim with `[^<id>]`, keyed to a
  `sources[].id`. No footnote-definition block — ids resolve against the
  frontmatter. This attribution is what lets a changed raw file update
  surgically instead of by whole-page re-judgment.
- Wikilinks `[[Page_Title]]` between pages are the knowledge-graph edges. Filename = title with underscores (`wiki/Link_Setup_Frame.md`).

## Retrieval ladder (cheapest first — stop when the answer is grounded)

1. Read `<lore>/index.md`; pick candidate pages. Skip the `## Deprecated`
   section unless the question is explicitly about superseded/historical state.
2. `rg -i '<term>' <lore>/wiki/` for exact terms, part numbers, register names.
3. Read the whole matched page(s); follow wikilinks as needed.
4. Open the raw original (PDF page, image, spreadsheet) when wiki text is
   insufficient or precision matters — derived text is an index, raw is truth.

Never load the whole wiki into context. The index is the map.

## Answering rules

- Cite every claim: `raw/<file>#p<n>`, sheet/cell, or `wiki/<page>`. On
  multi-source pages the page's `[^id]` footnotes carry the attribution — reuse
  them.
- **Answer promotion:** if the answer took real synthesis (multiple pages/sources), file it as a `type: answer` page, add an index line, append a `log.md` entry, and commit — so it is never re-derived. Where the raw origins of the pages it was derived from are known, list them in the answer's `sources[]` too, so a later raw change reaches the answer through the reverse index.
- **Contradictions:** never silently resolve. Record inline:
  `> ⚠ CONTRADICTION: <claim A> [[Source_A]]; <claim B> [[Source_B]]`
- **`## My Take` sections are human-owned.** Never rewrite, reorder, or delete them.
- Numeric questions about spreadsheets: query the raw file on demand (python3/duckdb if available); never paste large tables into wiki pages.

## Discard flow

- **"discard page X"** (soft — the default): set `status: deprecated` in the
  page's frontmatter, move its index line to the `## Deprecated` section at the
  bottom of `index.md` (create the section on first use), append
  `## [YYYY-MM-DD] discard | <page>` to `log.md`, commit `discard: <page>`.
  The page stays on disk and greppable.
- **"delete page X permanently"** (hard — only on an explicit ask): delete
  `wiki/X.md`, remove its index line, append
  `## [YYYY-MM-DD] discard | <page> (permanent)`, commit. Inbound wikilinks are
  left in place — the next lint flags them. Git history is the undo. Meant for
  true junk: mis-ingests, duplicates.

## index.md rules

- Format per line: `- [Title](wiki/Page.md) — one-line hook`. The hook is the
  page's `description`, tightened only as needed to meet the hard cap of <200
  chars per entry.
- Grouped under `##` topic headings. Target ~200 lines total; past that, never drop entries to fit — every page must stay reachable from the index. Report it and propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.
- Deprecated pages (`status: deprecated`) keep their line, moved to a
  `## Deprecated` section at the bottom of the index.

## log.md rules

Append-only. Entry format:

```
## [YYYY-MM-DD] <ingest|lint|skip|init|answer|discard> | <subject>
One or two lines of detail.
```

An `ingest` entry's detail line records the raw file's content hash as
`sha256:<first 12 hex chars>`. The log is append-only, so the **latest** entry
for a filename is the last matching heading; ingest compares its recorded hash
against the current file to tell PROCESSED from CHANGED.

A `raw/` file **has a ledger entry** iff `log.md` contains an entry heading whose filename field is exactly that filename: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`. Match the whole field, anchored at both ends — never a substring: `spec.pdf` occurs inside the heading for `v2_spec.pdf`, so a substring test (`rg -F "spec.pdf"`) would classify a newly dropped `spec.pdf` as already processed and silently never ingest it.

## Git

Every mutation of the lore (init, ingest, lint fix, answer promotion, discard) ends with `git add -A && git commit` inside the lore repo, message prefixed `init:`, `ingest:`, `lint:`, `answer:`, or `discard:`.

A lore created with `/lore:lore-init --no-git` is not a repository. Before committing, test that the lore is a repository **root** — its own repository, not merely a folder somewhere inside one:

```bash
[ "$(git -C "$LORE" rev-parse --show-toplevel 2>/dev/null)" = "$LORE" ]
```

The comparison only holds when `$LORE` is an absolute, symlink-resolved path — the form the ladder above produces, and the form `rev-parse --show-toplevel` prints; a relative or `~`-prefixed `$LORE` would mismatch a perfectly good repo.

The test is deliberately this narrow. `rev-parse` searches *upward*, so a lore nested inside another git repository would answer "yes" to any wider test — and `git add -A` then stages from that outer repository's root regardless of `-C`, sweeping the user's unrelated project files into a lore commit. A nested lore is therefore correctly treated as not-a-repo, which is exactly the case `--no-git` exists for.

If the test fails: do the work, **skip the commit**, and state in the report that changes were written without a commit. Never error, and never offer to run `git init` — the user opted out deliberately.
