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
  raw/              # inbox + originals. IMMUTABLE: never edit or delete anything here
  wiki/             # agent-maintained pages
```

## Page schema

Every `wiki/*.md` file starts with YAML frontmatter:

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

- `concept` — a topic distilled across sources. `source` — summary of one raw file.
  `answer` — a promoted Q&A result. `decision` — a recorded choice and why.
  `card` — spreadsheet metadata card.
- Wikilinks `[[Page_Title]]` between pages are the knowledge-graph edges. Filename = title with underscores (`wiki/Link_Setup_Frame.md`).

## Retrieval ladder (cheapest first — stop when the answer is grounded)

1. Read `<lore>/index.md`; pick candidate pages.
2. `rg -i '<term>' <lore>/wiki/` for exact terms, part numbers, register names.
3. Read the whole matched page(s); follow wikilinks as needed.
4. Open the raw original (PDF page, image, spreadsheet) when wiki text is
   insufficient or precision matters — derived text is an index, raw is truth.

Never load the whole wiki into context. The index is the map.

## Answering rules

- Cite every claim: `raw/<file>#p<n>`, sheet/cell, or `wiki/<page>`.
- **Answer promotion:** if the answer took real synthesis (multiple pages/sources), file it as a `type: answer` page, add an index line, append a `log.md` entry, and commit — so it is never re-derived.
- **Contradictions:** never silently resolve. Record inline:
  `> ⚠ CONTRADICTION: <claim A> [[Source_A]]; <claim B> [[Source_B]]`
- **`## My Take` sections are human-owned.** Never rewrite, reorder, or delete them.
- Numeric questions about spreadsheets: query the raw file on demand (python3/duckdb if available); never paste large tables into wiki pages.

## index.md rules

- Format per line: `- [Title](wiki/Page.md) — one-line hook`. Hard cap <200 chars per entry: tighten the hook to fit.
- Grouped under `##` topic headings. Target ~200 lines total; past that, never drop entries to fit — every page must stay reachable from the index. Report it and propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.

## log.md rules

Append-only. Entry format:

```
## [YYYY-MM-DD] <ingest|lint|skip|init|answer> | <subject>
One or two lines of detail.
```

A `raw/` file counts as already-processed iff `log.md` contains an entry heading whose filename field is exactly that filename: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`. Match the whole field, anchored at both ends — never a substring: `spec.pdf` occurs inside the heading for `v2_spec.pdf`, so a substring test (`rg -F "spec.pdf"`) would classify a newly dropped `spec.pdf` as already processed and silently never ingest it.

## Git

Every mutation of the lore (init, ingest, lint fix, answer promotion) ends with `git add -A && git commit` inside the lore repo, message prefixed `init:`, `ingest:`, `lint:`, or `answer:`.

A lore created with `/lore:lore-init --no-git` is not a repository. Before committing, test that the lore is a repository **root** — its own repository, not merely a folder somewhere inside one:

```bash
[ "$(git -C "$LORE" rev-parse --show-toplevel 2>/dev/null)" = "$LORE" ]
```

The comparison only holds when `$LORE` is an absolute, symlink-resolved path — the form the ladder above produces, and the form `rev-parse --show-toplevel` prints; a relative or `~`-prefixed `$LORE` would mismatch a perfectly good repo.

The test is deliberately this narrow. `rev-parse` searches *upward*, so a lore nested inside another git repository would answer "yes" to any wider test — and `git add -A` then stages from that outer repository's root regardless of `-C`, sweeping the user's unrelated project files into a lore commit. A nested lore is therefore correctly treated as not-a-repo, which is exactly the case `--no-git` exists for.

If the test fails: do the work, **skip the commit**, and state in the report that changes were written without a commit. Never error, and never offer to run `git init` — the user opted out deliberately.
