# lore Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and locally publish `lore` (Long-term Organized Reference), a zero-dependency Claude Code plugin whose skills create and maintain a markdown knowledge-base folder that any project can link to.

**Architecture:** A standalone plugin repo containing five skills (`lore` core contract, `/lore-init`, `/lore-ingest`, `/lore-lint`, `/lore-link`). The lore itself is a git-tracked folder (`raw/` inbox → agent-maintained `wiki/` + `index.md` + `log.md`). No databases, no external tools: skills are markdown instructions executed by Claude Code with Read/Write/Bash/ripgrep.

**Tech Stack:** Claude Code plugin format (`.claude-plugin/plugin.json`, `marketplace.json`, `skills/*/SKILL.md`), bash, git, ripgrep. Verification via bash assertions.

**Spec:** `docs/superpowers/specs/2026-08-21-lore-plugin-design.md` (in the `oidar` repo — this plan lives beside it; the plugin repo is created at `~/Project/lore`).

## Global Constraints

- Plugin name: `lore`; initial version `0.1.0`.
- Config file: `~/.claude/lore.json`, exact shape `{"path": "/abs/path/to/lore"}`.
- Lore layout: `CLAUDE.md`, `index.md`, `log.md`, `raw/`, `wiki/` — nothing else at top level.
- `<lore>/CLAUDE.md` is the schema — the full rules, seeded from the plugin template. It is authoritative: where it differs from a skill's built-in defaults, the lore's `CLAUDE.md` wins (the user co-evolves it with the agent).
- `raw/` is immutable after ingest; agents never edit or delete files there.
- `index.md` caps: ~200 lines total, <200 characters per entry line.
- Frontmatter: `type` is the only mandatory field; allowed types `concept | source | answer | decision | card`.
- Contradictions are flagged with `> ⚠ CONTRADICTION:` blocks, never auto-resolved.
- `## My Take` sections are human-owned; agents never rewrite them.
- Every ingest/lint ends with a git commit inside the lore repo.
- Zero external dependencies: no network fetching, no vector DBs, no local models.
- Testing happens against a throwaway lore at `/tmp/test-lore` and a throwaway project at `/tmp/test-project`; the real `~/.claude/lore.json` is restored at the end of any task that touches it.

## File Structure

```
~/Project/lore/
  .claude-plugin/plugin.json          # Task 1
  .claude-plugin/marketplace.json     # Task 1
  README.md                           # Task 1 (stub) → Task 7 (full)
  skills/
    lore/SKILL.md                    # Task 2 — core contract (schema, retrieval ladder, rules)
    lore-init/SKILL.md               # Task 3 — /lore-init
    lore-init/templates/CLAUDE.md    # Task 3 — full-rules schema copied into every new lore
    lore-ingest/SKILL.md             # Task 4 — /lore-ingest
    lore-lint/SKILL.md               # Task 5 — /lore-lint
    lore-link/SKILL.md               # Task 6 — /lore-link
```

---

### Task 1: Plugin repo scaffold and manifests

**Files:**
- Create: `~/Project/lore/.claude-plugin/plugin.json`
- Create: `~/Project/lore/.claude-plugin/marketplace.json`
- Create: `~/Project/lore/README.md` (stub)

**Interfaces:**
- Produces: a git repo at `~/Project/lore` that later tasks add skills into; plugin name `lore` used by install commands in Task 7.

- [ ] **Step 1: Create repo and manifests**

```bash
mkdir -p ~/Project/lore/.claude-plugin ~/Project/lore/skills
cd ~/Project/lore && git init -q
git config user.email "kutzuim@gmail.com" && git config user.name "kutzuim"
```

Write `.claude-plugin/plugin.json`:

```json
{
  "name": "lore",
  "version": "0.1.0",
  "description": "Lore (Long-term Organized Reference): a persistent, human-readable knowledge base on disk, maintained by Claude Code skills: drop files into raw/, get an interlinked markdown wiki with a catalog index. Link any project to it with /lore-link.",
  "author": { "name": "kutzuim" }
}
```

Write `.claude-plugin/marketplace.json`:

```json
{
  "name": "lore-marketplace",
  "owner": { "name": "kutzuim" },
  "plugins": [
    {
      "name": "lore",
      "source": "./",
      "description": "Lore (Long-term Organized Reference) — a markdown second brain for Claude Code: universal inbox, agent-maintained wiki, index-first retrieval."
    }
  ]
}
```

Write `README.md` stub:

```markdown
# lore

A Claude Code plugin that maintains a markdown knowledge base on disk.
Full docs land with v0.1.0 (see plan Task 7).
```

- [ ] **Step 2: Verify manifests are valid JSON**

Run:
```bash
cd ~/Project/lore
python3 -m json.tool .claude-plugin/plugin.json >/dev/null && echo PLUGIN_OK
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null && echo MARKETPLACE_OK
```
Expected: `PLUGIN_OK` and `MARKETPLACE_OK`.

- [ ] **Step 3: Commit**

```bash
cd ~/Project/lore && git add -A && git commit -m "feat: scaffold lore plugin manifests"
```

---

### Task 2: Core `lore` skill (the contract)

**Files:**
- Create: `~/Project/lore/skills/lore/SKILL.md`

**Interfaces:**
- Produces: the conventions every other skill defers to — config path `~/.claude/lore.json`, page schema, retrieval ladder, citation/contradiction/My-Take rules. Tasks 3-6 reference this skill by name (`lore`) and must not restate its rules differently.

- [ ] **Step 1: Write the skill**

Write `skills/lore/SKILL.md` with exactly this content:

````markdown
---
name: lore
description: Use when answering any domain or knowledge question in a project linked to the lore (its CLAUDE.md contains a "lore:start" pointer block), and as the shared contract for all lore-* skills. Defines the lore folder layout, page schema, retrieval ladder, and citation rules.
---

# The Lore — Core Contract

## Finding the lore

Read `~/.claude/lore.json` → `{"path": "<abs path>"}`. If the file is missing, tell the user to run `/lore-init` and stop.

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

- Format per line: `- [Title](wiki/Page.md) — one-line hook` (<200 chars).
- Grouped under `##` topic headings. Hard cap ~200 lines total; when near the cap, tighten hooks and merge sparse groups instead of exceeding it.

## log.md rules

Append-only. Entry format:

```
## [YYYY-MM-DD] <ingest|lint|skip|init|answer> | <subject>
One or two lines of detail.
```

A `raw/` file counts as already-processed iff its filename appears in `log.md`.

## Git

Every mutation of the lore (ingest, lint fix, answer promotion) ends with `git add -A && git commit` inside the lore repo, message prefixed `ingest:`, `lint:`, or `answer:`.
````

- [ ] **Step 2: Verify frontmatter parses and rules are present**

Run:
```bash
cd ~/Project/lore
python3 - <<'EOF'
import re
t = open('skills/lore/SKILL.md').read()
fm = re.match(r'^---\n(.*?)\n---\n', t, re.S)
assert fm and 'name: lore' in fm.group(1), 'frontmatter broken'
for needle in ['lore.json', 'Retrieval ladder', 'CONTRADICTION', 'My Take', 'Answer promotion', 'IMMUTABLE', "CLAUDE.md wins"]:
    assert needle in t, f'missing: {needle}'
print('LORE_SKILL_OK')
EOF
```
Expected: `LORE_SKILL_OK`.

- [ ] **Step 3: Commit**

```bash
cd ~/Project/lore && git add -A && git commit -m "feat: add core lore skill (contract)"
```

---

### Task 3: `/lore-init` skill + CLAUDE.md schema template

**Files:**
- Create: `~/Project/lore/skills/lore-init/SKILL.md`
- Create: `~/Project/lore/skills/lore-init/templates/CLAUDE.md`

**Interfaces:**
- Consumes: contract from `lore` skill (Task 2).
- Produces: a scaffolded lore folder (with its full-rules `CLAUDE.md` schema) and `~/.claude/lore.json`; Tasks 4-6 tests assume a lore scaffolded exactly this way. The template's rules must match Task 2's defaults exactly — it is the copy of the schema that the lore owns and the user evolves.

- [ ] **Step 1: Write the CLAUDE.md schema template**

Write `skills/lore-init/templates/CLAUDE.md`:

````markdown
# Lore — Schema

This folder is a lore — a second brain, Long-term Organized Reference — maintained by Claude Code (`lore` plugin).
This file is the schema: the full rules for how the lore is structured and
maintained. It is auto-loaded whenever Claude Code runs inside this folder, and
the plugin's skills read it from linked projects. Evolve it freely with the
agent as conventions settle — where this file differs from the plugin's
built-in defaults, this file wins.

## Layout

- `raw/` — inbox + originals: drop any file here (PDF, image, xlsx/csv, md, txt, saved HTML). IMMUTABLE after ingest; originals are ground truth and always win over derived wiki text.
- `wiki/` — agent-maintained distilled pages; the lore itself.
- `index.md` — catalog: one line per page (`- [Title](wiki/Page.md) — hook`, <200 chars), grouped under `##` topic headings; ~200-line hard cap. Read first on every query.
- `log.md` — append-only history; also the processed-file ledger (a `raw/` file is new iff its filename is absent from `log.md`).
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

## Git

Every mutation (ingest, lint fix, answer promotion) ends with a commit here, message prefixed `ingest:`, `lint:`, or `answer:`.

## Operations

`/lore-ingest` — process new `raw/` files into the wiki. `/lore-lint` — health check. `/lore-link` — point a project at this lore.
````

- [ ] **Step 2: Write the skill**

Write `skills/lore-init/SKILL.md`:

````markdown
---
name: lore-init
description: Use when the user runs /lore-init [path] — create (or re-point to) the lore folder, scaffold its layout with its CLAUDE.md schema, git-init it, and record its location in ~/.claude/lore.json.
---

# /lore-init [path]

Follow the `lore` skill for all conventions. Base directory of this skill contains `templates/CLAUDE.md` — the full-rules schema every new lore is seeded with.

1. Resolve `LORE` = the argument if given, else `$HOME/lore`. Expand to an absolute path.
2. **Existing lore?** If `$LORE/index.md` exists: do NOT touch the folder. Only rewrite the config (step 5), report "re-pointed config to existing lore", and stop after step 5.
3. **Non-empty, non-lore folder?** If `$LORE` exists, is non-empty, and has no `index.md`: refuse and ask the user for a different path. Never scaffold over foreign files.
4. Scaffold:

```bash
mkdir -p "$LORE/raw" "$LORE/wiki"
cat > "$LORE/index.md" <<'EOF'
# Lore Index

<!-- One line per wiki page: - [Title](wiki/Page.md) — hook. Grouped by ## topic. Cap ~200 lines. -->
EOF
cat > "$LORE/log.md" <<EOF
# Lore Log

## [$(date +%F)] init | lore created
EOF
cp "<skill-base-dir>/templates/CLAUDE.md" "$LORE/CLAUDE.md"
cd "$LORE" && git init -q && git add -A && git commit -q -m "init: lore scaffold"
```

(If git identity is unset in this environment, set a repo-local one first with `git config user.email` / `git config user.name`, asking the user for values if unknown.)

5. Record location:

```bash
mkdir -p ~/.claude
printf '{"path": "%s"}\n' "$LORE" > ~/.claude/lore.json
```

6. Report: lore path, what was created (or "re-pointed"), and next steps (drop files into `raw/`, run `/lore-ingest`, run `/lore-link` inside projects).
````

- [ ] **Step 3: Functional test — fresh init**

Perform the skill's procedure with argument `/tmp/test-lore` (save any existing real config first):

```bash
cp ~/.claude/lore.json /tmp/lore.json.bak 2>/dev/null || true
rm -rf /tmp/test-lore
```

Then execute steps 1-6 of the skill exactly as written (using `skills/lore-init/templates/CLAUDE.md` as the template source). Verify:

```bash
test -f /tmp/test-lore/index.md && test -f /tmp/test-lore/log.md \
  && test -f /tmp/test-lore/CLAUDE.md && test -d /tmp/test-lore/raw \
  && test -d /tmp/test-lore/wiki && echo SCAFFOLD_OK
grep -q 'this file wins' /tmp/test-lore/CLAUDE.md && echo SCHEMA_OK
cd /tmp/test-lore && git log --oneline | grep -q "init: lore scaffold" && echo GIT_OK
grep -q '/tmp/test-lore' ~/.claude/lore.json && echo CONFIG_OK
```
Expected: `SCAFFOLD_OK`, `SCHEMA_OK`, `GIT_OK`, `CONFIG_OK`.

- [ ] **Step 4: Functional test — idempotent re-init**

Run the procedure again with the same argument. Verify nothing changed:

```bash
cd /tmp/test-lore && [ "$(git log --oneline | wc -l)" = "1" ] && echo IDEMPOTENT_OK
```
Expected: `IDEMPOTENT_OK` (still exactly one commit; config merely rewritten).

- [ ] **Step 5: Commit**

```bash
cd ~/Project/lore && git add -A && git commit -m "feat: add /lore-init skill with CLAUDE.md schema template"
```

---

### Task 4: `/lore-ingest` skill

**Files:**
- Create: `~/Project/lore/skills/lore-ingest/SKILL.md`

**Interfaces:**
- Consumes: lore scaffolded by Task 3; conventions from Task 2 (`log.md` ledger rule, page schema, index caps, commit rule).
- Produces: `wiki/` pages + `index.md` entries + `log.md` `ingest`/`skip` entries; Task 5's lint operates on this output.

- [ ] **Step 1: Write the skill**

Write `skills/lore-ingest/SKILL.md`:

````markdown
---
name: lore-ingest
description: Use when the user runs /lore-ingest — find files in the lore's raw/ inbox that are not yet in log.md, distill each into wiki pages by content type, update index.md and log.md, and commit.
---

# /lore-ingest

Follow the `lore` skill for schema, index/log rules, and the commit rule. Lore path comes from `~/.claude/lore.json`; read `$LORE/CLAUDE.md` first — where it differs from these defaults, it wins.

Default flow is interactive: after each file, surface the key takeaways in the report so the user can steer emphasis before the next one. If the user asks for a batch run, process everything straight through and report once at the end.

## 1. Find new files

```bash
ls -1 "$LORE/raw/"
```
A file is NEW iff its filename does not appear in `$LORE/log.md` (check with `rg -F "<filename>" "$LORE/log.md"`). If no new files: report "nothing to ingest" and stop (no commit).

## 2. Process each new file by type

Before creating ANY page: `rg -i` the candidate title in `$LORE/index.md` and over `wiki/` filenames — if a page on that topic exists, UPDATE it (merge new facts, bump `freshness`, add the new `source`) instead of creating a duplicate.

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
````

- [ ] **Step 2: Create test fixtures in the test lore**

```bash
cat > /tmp/test-lore/raw/notes.md <<'EOF'
# Widget Alpha Notes
The Alpha widget uses a 12 MHz crystal. Its UART runs at 115200 baud.
It talks to the Beta module over SPI mode 0.
EOF
printf 'part,qty,price\nAlpha,2,3.50\nBeta,1,7.25\nCrystal 12MHz,4,0.40\n' > /tmp/test-lore/raw/bom.csv
python3 -c "import base64;open('/tmp/test-lore/raw/pixel.png','wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='))"
printf 'binary junk' > /tmp/test-lore/raw/mystery.bin
```

(PDF and xlsx pipelines are exercised later with real files in Task 7's acceptance pass — deterministic fixtures for them are not practical here.)

- [ ] **Step 3: Functional test — run the ingest procedure**

Execute the skill's procedure end-to-end against `/tmp/test-lore` (the config from Task 3 already points there). Then verify:

```bash
B=/tmp/test-lore
ls "$B"/wiki/*.md >/dev/null && echo PAGES_OK
rg -q 'type: card' "$B"/wiki/ && echo CARD_OK
rg -q 'notes.md' "$B/log.md" && rg -q 'bom.csv' "$B/log.md" && rg -q 'pixel.png' "$B/log.md" && echo LEDGER_OK
rg -q 'skip \| mystery.bin' "$B/log.md" && echo SKIP_OK
rg -q 'wiki/' "$B/index.md" && echo INDEX_OK
cd "$B" && git log --oneline -1 | grep -q '^.* ingest:' && echo COMMIT_OK
awk 'length > 200 && /^- \[/' "$B/index.md" | wc -l | grep -qx 0 && echo CAPS_OK
```
Expected: all seven `*_OK` markers.

- [ ] **Step 4: Functional test — idempotency**

Run the ingest procedure again with no new files. Verify:

```bash
cd /tmp/test-lore && N=$(git log --oneline | wc -l) && \
  echo "commits: $N (must equal the count after step 3 — no new commit)"
```
Expected: commit count unchanged; skill reports "nothing to ingest".

- [ ] **Step 5: Commit**

```bash
cd ~/Project/lore && git add -A && git commit -m "feat: add /lore-ingest skill"
```

---

### Task 5: `/lore-lint` skill

**Files:**
- Create: `~/Project/lore/skills/lore-lint/SKILL.md`

**Interfaces:**
- Consumes: a populated lore (Task 4 output shape).
- Produces: lint report + mechanical fixes committed as `lint:`; no interface consumed by later tasks.

- [ ] **Step 1: Write the skill**

Write `skills/lore-lint/SKILL.md`:

````markdown
---
name: lore-lint
description: Use when the user runs /lore-lint — health-check the lore: orphan pages, dead wikilinks, index drift, duplicate titles, stale pages, unresolved contradictions, missing concept pages and cross-references, knowledge gaps. Fix mechanical issues; report judgment calls.
---

# /lore-lint

Follow the `lore` skill for all conventions. Lore path from `~/.claude/lore.json`; read `$LORE/CLAUDE.md` first — where it differs from these defaults, it wins.

## Checks

1. **Orphan pages** — `wiki/*.md` with no line in `index.md`. FIX: add an index line in the right group.
2. **Ghost index entries** — `index.md` lines pointing at missing files. FIX: remove the line.
3. **Dead wikilinks** — `rg -o '\[\[[^]]+\]\]' wiki/` targets with no matching `wiki/<Target_With_Underscores>.md`. FIX: if an obvious near-match page exists, correct the link; else REPORT.
4. **Duplicate titles** — two pages whose `title:` differ only by case/punctuation. REPORT only (merging is a judgment call).
5. **Staleness** — pages with `freshness` older than 90 days. REPORT only.
6. **Contradictions** — count `> ⚠ CONTRADICTION` blocks. REPORT only; never resolve.
7. **Index caps** — file over ~200 lines or entries over 200 chars. FIX: tighten hooks, merge sparse groups.
8. **Frontmatter validity** — missing `type`, or `type` outside the allowed five. FIX missing/typo'd fields when the correct value is obvious from content; else REPORT.
9. **Missing concept pages** — a topic wikilinked or substantively discussed across 2+ pages with no page of its own. REPORT only (suggest the page).
10. **Missing cross-references** — two pages clearly covering the same entity with no wikilink between them. FIX when the connection is unambiguous; else REPORT.
11. **Knowledge gaps** — questions the wiki raises but cannot answer, claims a newer source may have superseded, sources worth finding next. REPORT only, phrased as suggested next questions/sources for the user to investigate.

## Output

- Apply all FIXes, then `cd "$LORE" && git add -A && git commit -m "lint: <summary>"` (skip commit if nothing fixed).
- Append to `log.md`: `## [YYYY-MM-DD] lint | <n> fixed, <m> reported`.
- Report to the user: fixed items, then reported items grouped by check, each with file paths.
````

- [ ] **Step 2: Plant defects in the test lore**

```bash
B=/tmp/test-lore
cat > "$B/wiki/Orphan_Page.md" <<'EOF'
---
type: concept
title: Orphan Page
captured: 2026-08-21
freshness: 2026-08-21
trust: extracted
---
Links to a page that does not exist: [[No_Such_Page]].
EOF
echo '- [Ghost](wiki/Ghost.md) — points nowhere' >> "$B/index.md"
```

- [ ] **Step 3: Functional test — run the lint procedure**

Execute the skill's procedure. Verify:

```bash
B=/tmp/test-lore
rg -q 'Orphan_Page' "$B/index.md" && echo ORPHAN_FIXED
rg -q 'Ghost' "$B/index.md" && echo GHOST_STILL_THERE || echo GHOST_REMOVED
rg -q 'lint \|' "$B/log.md" && echo LOGGED
cd "$B" && git log --oneline -1 | grep -q 'lint:' && echo COMMITTED
```
Expected: `ORPHAN_FIXED`, `GHOST_REMOVED`, `LOGGED`, `COMMITTED`; the run's report must list the dead wikilink `[[No_Such_Page]]` as reported (not silently deleted).

- [ ] **Step 4: Commit**

```bash
cd ~/Project/lore && git add -A && git commit -m "feat: add /lore-lint skill"
```

---

### Task 6: `/lore-link` skill

**Files:**
- Create: `~/Project/lore/skills/lore-link/SKILL.md`

**Interfaces:**
- Consumes: config file written by Task 3.
- Produces: a marker-delimited pointer block in a project's `CLAUDE.md`; the `lore` skill's description (Task 2) triggers off this block's presence.

- [ ] **Step 1: Write the skill**

Write `skills/lore-link/SKILL.md`:

````markdown
---
name: lore-link
description: Use when the user runs /lore-link inside a project — append a pointer block to that project's CLAUDE.md so Claude consults the lore for domain questions there.
---

# /lore-link

1. Read the lore path from `~/.claude/lore.json` (if missing → tell user to run `/lore-init`, stop).
2. Target file: `./CLAUDE.md` in the current project root (create if absent).
3. **Idempotency:** if the file already contains `<!-- lore:start -->`, replace everything between the start and end markers with the fresh block; otherwise append the block.

Block to write (substitute the real lore path):

```markdown
<!-- lore:start -->
## Lore
This project is linked to a knowledge base at `<LORE_PATH>`.
- For domain/knowledge questions, use the `lore` skill: read `<LORE_PATH>/index.md` first, then rg its wiki/; cite sources.
- Never edit `<LORE_PATH>/raw/`. Wiki edits must follow the lore skill's conventions.
<!-- lore:end -->
```

4. Report: linked path, and whether the block was added or refreshed.
````

- [ ] **Step 2: Functional test**

```bash
mkdir -p /tmp/test-project && cd /tmp/test-project && rm -f CLAUDE.md
```

Execute the skill's procedure in `/tmp/test-project`, then run it a second time. Verify:

```bash
grep -c 'lore:start' /tmp/test-project/CLAUDE.md | grep -qx 1 && echo LINK_IDEMPOTENT_OK
grep -q '/tmp/test-lore' /tmp/test-project/CLAUDE.md && echo LINK_PATH_OK
```
Expected: `LINK_IDEMPOTENT_OK`, `LINK_PATH_OK`.

- [ ] **Step 3: Commit**

```bash
cd ~/Project/lore && git add -A && git commit -m "feat: add /lore-link skill"
```

---

### Task 7: README, local install, acceptance pass, v0.1.0

**Files:**
- Modify: `~/Project/lore/README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: installable v0.1.0.

- [ ] **Step 1: Write the full README**

Replace `README.md` with:

```markdown
# lore

**L**ong-term **O**rganized **R**eference — a Claude Code plugin that maintains
a persistent, human-readable knowledge base ("the lore") on your disk. Drop any
file into an inbox folder; Claude distills it
into an interlinked markdown wiki with a catalog index. Link any project to the
lore with one command.

Zero dependencies: markdown + git + ripgrep. No databases, no APIs, no models.

## Install

    claude plugin marketplace add <owner>/lore
    claude plugin install lore@lore-marketplace

## Use

    /lore-init [path]     # once — creates the lore (default ~/lore), git-inits it
    # drop files into <lore>/raw/   (PDF, images, xlsx/csv, md, txt, saved HTML)
    /lore-ingest          # distill new raw files into the wiki
    /lore-link            # once per project — point it at the lore
    /lore-lint            # periodic health check (after ~5 ingests or monthly)

Then just ask questions in linked projects; answers cite their sources.

## The folder

    <lore>/
      CLAUDE.md       # the schema — full rules; evolve it with the agent, it wins over defaults
      index.md        # catalog — read this first
      log.md          # append-only history / processed-file ledger
      raw/            # your originals — never modified
      wiki/           # the distilled lore — plain markdown, yours to read and edit

Notes for humans: sections headed `## My Take` are never touched by the agent;
contradictions between sources are flagged, never silently resolved; every
change is a git commit you can review or revert.
```

- [ ] **Step 2: Commit and install locally**

```bash
cd ~/Project/lore && git add -A && git commit -m "docs: full README"
claude plugin marketplace add ~/Project/lore
claude plugin install lore@lore-marketplace
claude plugin list | grep -i lore && echo INSTALL_OK
```
Expected: `INSTALL_OK`. (If the marketplace-add syntax for a local path differs in the installed CLI version, consult `claude plugin --help` and adapt; the repo layout already matches the documented marketplace format.)

- [ ] **Step 3: Acceptance pass (spec §10)**

In a fresh Claude Code session (so installed skills load):

1. `/lore-init /tmp/test-lore2` → scaffold + config verified as in Task 3 Step 3.
2. Drop one real PDF and one real xlsx (any at hand) plus a png into `/tmp/test-lore2/raw/`; run `/lore-ingest` → pages/index/log/commit verified as in Task 4 Step 3; re-run → no-op.
3. Ask 3 questions answerable from the ingested content in `/tmp/test-project` (after `/lore-link`) → answers must cite `raw/...` or `wiki/...` sources. (The spec's full 10-question pass runs post-plan, once the user's real corpus is seeded.)
4. Plant a contradiction (edit a wiki page to disagree with its source, add a second source page claiming otherwise) → `/lore-lint` reports it, does not resolve it.

Record results in the task notes. Any failure → fix the relevant SKILL.md, re-run, then commit the fix.

- [ ] **Step 4: Restore real config and clean up**

```bash
[ -f /tmp/lore.json.bak ] && mv /tmp/lore.json.bak ~/.claude/lore.json || rm -f ~/.claude/lore.json
rm -rf /tmp/test-lore /tmp/test-lore2 /tmp/test-project
```

(The user re-points at their real lore later with `/lore-init`.)

- [ ] **Step 5: Tag release**

```bash
cd ~/Project/lore && git add -A && git commit -m "chore: v0.1.0" --allow-empty && git tag v0.1.0
```

---

## Post-plan (user-driven, not part of v0.1.0)

- Push the repo to a public host to make `claude plugin marketplace add <owner>/lore` work for others.
- Run `/lore-init` against the real lore path, move real source files into `raw/`, `/lore-ingest`, `/lore-link` in real projects.
