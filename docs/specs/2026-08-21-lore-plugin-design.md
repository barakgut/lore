# lore — Claude Code Plugin Design

Date: 2026-08-21
Status: approved design, pending user review of this spec

## 1. Summary

`lore` (Long-term Organized Reference) is a publishable Claude Code plugin that turns a single folder on disk into a persistent, human-readable knowledge base ("the lore") maintained by Claude Code through skills. The user drops any local file into an inbox folder; Claude ingests it into an interlinked markdown wiki with a catalog index. Any project on the machine can be linked to the lore with one command, after which Claude consults the lore when answering domain questions in that project.

The design follows the 2026 consensus for agent knowledge bases: markdown files in git as the source of truth, an agent-maintained index as the primary retrieval mechanism, grep-based retrieval instead of RAG infrastructure, and scheduled lint/consolidation to prevent rot. The wiki format follows the Open Knowledge Format (OKF) conventions: filepath as identity, markdown links as graph edges, minimal YAML frontmatter with `type` as the only mandatory field. Per the source idea file's three-layer model (raw sources / wiki / schema), the schema layer is the lore's own `CLAUDE.md` — the full rules, auto-loaded whenever Claude Code runs inside the lore folder, read by the skills from linked projects, and co-evolved by the user and the agent over time.

## 2. Goals

- Ship as an installable, publishable Claude Code plugin (marketplace-compatible repo).
- One global lore folder created on install/init; all projects share it.
- Universal inbox: the user drops any local file into `raw/` (PDF, image, xlsx, md, txt, saved HTML); ingestion handles it by type. Unknown types are logged and skipped, never silently dropped.
- Fully human-readable at every layer: a person with no tooling can read and navigate the lore.
- Token-frugal and fast: index-first retrieval, pull-not-push context, whole-page reads over chunking.
- Zero external dependencies: works with a stock Claude Code install. No APIs, no local models, no databases, no fetch tools.
- Every agent write is a reviewable git diff.

## 3. Non-goals

- No URL, web page, or YouTube fetching. The user saves web content to a file and drops the file in `raw/`.
- No requirements-traceability subsystem.
- No vector database, embedding index, or graph database.
- No per-project knowledge tier; projects link to the one lore.
- No automatic background jobs; lint is user-triggered.

## 4. Architecture

### 4.1 The lore folder

Created by `/lore-init` (default `~/lore`, user may pass another path). It is its own git repository.

```
~/lore/
  CLAUDE.md         # THE SCHEMA: full rules for structure, conventions, and workflows;
                    # auto-loaded when Claude Code runs inside the lore folder
  index.md          # catalog: one line per wiki page; the primary retrieval tool
  log.md            # append-only history of ingests, answers, and lints; doubles as the
                    # processed-file ledger (a raw/ file is "new" if absent from log.md)
  raw/              # inbox: originals, immutable after ingest; ground truth
  wiki/             # agent-maintained pages; the lore itself
```

Layer model (matching the idea file's raw sources / wiki / schema):

| Layer | Path | Rule |
|---|---|---|
| Truth | `raw/` | Immutable. The agent reads, never edits. Original file always wins over any derived text. |
| Curated | `wiki/` + `index.md` + `log.md` | Agent-maintained under git review. Accumulates; never regenerated wholesale. |
| Schema | `<lore>/CLAUDE.md` | The full rules (layout, page schema, index/log formats, retrieval ladder, answering/ingest/lint workflows). Seeded from a plugin template; the user and agent co-evolve it. Authoritative: where it differs from the skills' built-in defaults, the lore's `CLAUDE.md` wins. |
| Config | `~/.claude/lore.json` | `{"path": "/home/user/lore"}` — how skills in any project find the lore. |

### 4.2 Wiki page schema (OKF-shaped)

```yaml
---
type: concept | source | answer | decision | card    # mandatory
title: Some Concept
source: raw/some_datasheet.pdf#p12                   # file (with page/sheet anchor when applicable)
captured: 2026-08-21                                 # date ingested
freshness: 2026-08-21                                # date last verified against source
trust: extracted | inferred | human
tags: []                                             # optional
---
```

- Body: markdown. Wikilinks `[[Page_Title]]` between pages are the knowledge graph edges.
- Page types: `concept` (a topic distilled across sources), `source` (summary of one raw file), `answer` (a promoted Q&A result), `decision` (a recorded choice and why), `card` (spreadsheet metadata card).
- Contradictions are flagged, never silently resolved:
  `> ⚠ CONTRADICTION: rev C says 4.8 kHz deviation [[Source_A]]; rev D says 5.0 kHz [[Source_B]]`
- Sections headed `## My Take` are human-owned; the agent never rewrites them.

### 4.3 index.md

- One line per wiki page: `- [Title](wiki/Page.md) — one-line hook`.
- Grouped under topic headings the agent maintains.
- Hard caps: ~200 lines total, <200 characters per entry. The index is read on nearly every query; its size is the per-query token floor.

### 4.4 log.md

Append-only, greppable:

```
## [2026-08-21] ingest | some_datasheet.pdf
Created 7 pages, updated index (protocol section). trust: extracted.
```

Entries: `ingest`, `lint`, `skip` (unknown file type), `init`, `answer` (promoted query result). Ingestion decides whether a `raw/` file is new by grepping `log.md` for its filename.

## 5. Ingestion by content type

All performed natively by Claude Code. The derived wiki text is a retrieval index; the raw file remains ground truth and the agent re-opens it when precision matters.

| Input | Pipeline |
|---|---|
| PDF (datasheets, specs) | Read pages directly. Write `source` page + `concept` pages. Tables and register maps verified against the PDF page and cited `#p<n>`. |
| Image (schematics, scope shots, photos) | Write structured caption into a wiki page: image kind, visible designators/nets/settings, what it shows. Caption is for retrieval only — the agent re-reads the image for any analysis and never trusts a caption for connectivity claims. |
| Excel/CSV | Write a `card` page: sheet names, column schemas, row counts, ~5 sample rows, purpose. Numeric questions are answered by querying the file on demand (python/duckdb if available on the machine; otherwise best-effort reading). Large tables are never serialized into the wiki. |
| Markdown / txt / saved HTML | Read directly; distill into `source`/`concept` pages; original stays in `raw/`. |
| Unknown type | `skip` entry in log.md with reason; user informed in the ingest report. |

Ingest procedure (`/lore-ingest`):

1. Diff `raw/` against `log.md` → list of new files.
2. Per file: detect type, run pipeline above.
3. Before creating any page, grep `index.md` and `wiki/` titles for an existing page on the topic — update it rather than duplicate ("exists-already" check).
4. Update `index.md` (add/adjust entries, keep caps) and append to `log.md`.
5. `git commit` in the lore repo with a summary message.
6. Report to the user: pages created/updated, skips, contradictions found.

Two supervision styles, per the idea file: the default interactive flow processes one file at a time and surfaces key takeaways in the report so the user can steer emphasis before the next file; batch ingest (many files, less supervision) is the same procedure run straight through. Both are the same skill — the user just says which they want.

## 6. Query (retrieval ladder)

Query is the second of the three core operations (ingest / query / lint). It runs implicitly whenever a domain question is asked in the lore folder or a linked project. Cheapest step first; stop as soon as the answer is grounded.

1. `index.md` — locate candidate pages.
2. `rg` (ripgrep) over `wiki/` — exact terms, part numbers, register names.
3. Open the whole matched page(s); follow wikilinks as needed.
4. Open the raw original (PDF page, image, spreadsheet) when the wiki text is insufficient or precision matters.

Rules:

- Every answer cites its source (`file#page`, sheet/cell, or wiki page).
- Answers take whatever form fits the question — prose, a comparison table, or a full markdown page.
- Answer promotion: when a non-trivial answer required real synthesis, file it as a `type: answer` page, add an index entry, and append an `answer` log entry — explorations compound instead of being re-derived.
- Pull, not push: never load the whole wiki into context; the index is the map.

## 7. Plugin packaging

```
lore/                       # standalone publishable git repo
  .claude-plugin/
    plugin.json                     # name: lore, version, description
    marketplace.json                # enables: claude plugin marketplace add <owner>/lore
  skills/
    lore/SKILL.md                  # core: conventions, retrieval ladder; auto-triggers on
                                    # knowledge questions in linked projects
    lore-init/SKILL.md             # /lore-init [path]
    lore-init/templates/CLAUDE.md  # the full-rules schema copied into every new lore
    lore-ingest/SKILL.md           # /lore-ingest
    lore-lint/SKILL.md             # /lore-lint
    lore-link/SKILL.md             # /lore-link
  README.md                         # install + usage + the folder contract
```

### 7.1 Skill contracts

- **lore** (core, not slash-invoked): reads `~/.claude/lore.json` for the lore path, then reads `<lore>/CLAUDE.md` — the lore's schema. The skill carries the default rules (retrieval ladder, page schema, citation and contradiction rules) that seed every new lore, but where the lore's `CLAUDE.md` differs, the lore's file wins — that is how the schema co-evolves with the user. Other skills defer to it for conventions. Triggers when a question touches lore content in a linked project.
- **/lore-init [path]**: creates the folder scaffold (`CLAUDE.md` from the plugin's full-rules template, `index.md`, `log.md`, `raw/`, `wiki/`), `git init` + first commit, writes `~/.claude/lore.json`. Refuses to overwrite an existing non-empty lore; re-running on an existing lore just re-points the config.
- **/lore-ingest**: procedure in §5. Idempotent — re-running with no new files is a no-op.
- **/lore-lint**: checks orphan pages (no index entry), dead wikilinks, index↔pages drift, duplicate titles, `freshness` older than 90 days (flag only), unresolved contradiction blocks, missing concept pages (a topic discussed across 2+ pages with no page of its own), missing cross-references (related pages with no wikilink between them), and knowledge gaps (questions the wiki raises but cannot answer; suggested next sources/questions to investigate). Fixes mechanical issues (index drift, dead links, obvious missing cross-links) directly; reports contradictions, staleness, missing pages, and gaps to the user — never auto-resolves them. Commits fixes. Recommended cadence: after every ~5 ingests or monthly.
- **/lore-link**: run inside any project; appends a short pointer block (~5 lines) to that project's `CLAUDE.md`: lore path + instruction to consult the lore via the core skill before answering domain questions. Idempotent.

### 7.2 Install and use flow

```
claude plugin marketplace add <owner>/lore
claude plugin install lore
/lore-init                    # once
# drop files into ~/lore/raw/
/lore-ingest
cd ~/Project/<any-project>
/lore-link                    # once per project
# ask domain questions normally; run /lore-lint periodically
```

## 8. Maintenance

- Git commit after every ingest and lint; the lore's history is its audit trail.
- Lint is user-triggered (no cron, no hooks). If the user later wants automation, `/loop` or a scheduled agent can call `/lore-lint` unchanged.
- Human corrections win: agents respect `## My Take` sections and prior human edits (corrections are not regenerated away, because pages are edited incrementally, never rebuilt).
- The schema is maintainable too: as conventions settle, the user and agent evolve `<lore>/CLAUDE.md` together; skills follow the lore's copy, so no plugin update is needed.

## 9. Bootstrapping an existing corpus

For a user who already has documents and notes before installing the plugin:

1. Build/install the plugin; `/lore-init [path]`.
2. Move existing source files into `<lore>/raw/`.
3. Existing distilled notes (from any prior system) may be copied into `<lore>/wiki/` as first drafts; `/lore-ingest` then adds frontmatter, builds `index.md` entries, and records initial `log.md` entries. One-time copy; the pages are owned by the lore from then on.
4. `/lore-link` in each project that should use the lore.

## 10. Acceptance criteria

- Fresh-machine test: marketplace add → install → `/lore-init` (scaffold includes the full-rules `CLAUDE.md`) → drop one PDF + one image + one xlsx → `/lore-ingest` produces valid pages, index entries, log entries, and a git commit; unknown file type produces a `skip` log entry and a user-visible note.
- 10 real questions over the seeded corpus answered from a linked project with correct content and citations; token cost per answer recorded and reviewed.
- Duplicate-drop test: re-ingesting the same file is a no-op.
- Planted contradiction across two sources → `/lore-lint` reports it and does not auto-resolve.
- A human can navigate raw → index → wiki page → source citation with no tools beyond a text editor.

## 11. Risks and mitigations

- **Index rot** → lint cadence + hard index caps; index drift is a mechanical lint fix.
- **Duplicate pages** → exists-already check at ingest (§5 step 3); duplicate-title check at lint.
- **Mangled tables/register maps in derived text** → raw file is ground truth; citations carry page anchors; agent re-opens the PDF when precision matters.
- **Lore grows past grep** → markdown-as-truth means a local search index (e.g. qmd) can be bolted on later with zero migration; out of scope now.
- **Config file lost** → `/lore-init <path>` on the existing folder re-points config non-destructively.
