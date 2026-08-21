# Task 7 Report: README, local install, acceptance pass, v0.1.0

## What was implemented

1. `README.md` in `/home/vboxuser/Project/lore` replaced verbatim with the brief's full text (Install / Use / The folder sections). Commit `52cd4e7 docs: full README`.
2. Local marketplace + plugin install performed against `~/Project/lore`.
3. Full acceptance pass (a-d) executed by hand (procedures from each SKILL.md executed literally — no fresh Claude Code session was available; see "Not covered" below).
4. One real bug found and fixed in `skills/lore-lint/SKILL.md` (contradiction detection was count-only, never actively detected new unflagged contradictions). Commit `d26f98e fix: lore-lint must actively detect unflagged cross-page contradictions, not just count existing markers`.
5. Config and test state cleaned up per Step 4.
6. Tagged `v0.1.0` on commit `ab1018c chore: v0.1.0`.

## Install: exact commands and output

```
$ cd ~/Project/lore && git add -A && git commit -m "docs: full README"
[master 52cd4e7] docs: full README
 1 file changed, 35 insertions(+), 2 deletions(-)

$ timeout 120 claude plugin marketplace add ~/Project/lore
Adding marketplace…✔ Successfully added marketplace: lore-marketplace (declared in user settings)

$ timeout 120 claude plugin install lore@lore-marketplace
Installing plugin "lore@lore-marketplace"...✔ Successfully installed plugin: lore@lore-marketplace (scope: user)

$ timeout 60 claude plugin list | grep -i lore && echo INSTALL_OK
  ❯ lore@lore-marketplace
INSTALL_OK
```

`claude plugin --help` was consulted first; no syntax deviation was needed — `marketplace add <local-path>` and `install <name>@<marketplace>` worked as documented on CLI v2.1.239.

## Acceptance pass

All steps below were performed by literally executing each SKILL.md's numbered procedure by hand (Bash + Read/Write/Edit tools), per the controller ruling that a genuinely fresh Claude Code session is unavailable in this environment.

### a. `/lore-init /tmp/test-lore2`

Ran the exact scaffold commands from `skills/lore-init/SKILL.md` steps 1-5 (with a repo-local git identity set on the new lore repo, since none existed there — `git config user.email "kutzuim@gmail.com"` / `user.name "kutzuim"`, matching the skill's fallback instruction). Then adapted Task 3 Step 3's assertions to the new path:

```
$ B=/tmp/test-lore2
$ test -f "$B/index.md" && test -f "$B/log.md" && test -f "$B/CLAUDE.md" && test -d "$B/raw" && test -d "$B/wiki" && echo SCAFFOLD_OK
SCAFFOLD_OK
$ grep -q 'this file wins' "$B/CLAUDE.md" && echo SCHEMA_OK
SCHEMA_OK
$ cd "$B" && git log --oneline | grep -q "init: lore scaffold" && echo GIT_OK
GIT_OK
$ grep -q '/tmp/test-lore2' ~/.claude/lore.json && echo CONFIG_OK
CONFIG_OK
```

All four markers passed. Numeric-spreadsheet rule check (the c504bc5 fix):

```
$ grep -n "Numeric questions about spreadsheets" "$B/CLAUDE.md"
55:- Numeric questions about spreadsheets: query the raw file on demand (python3/duckdb if available); never paste large tables into wiki pages.
```

Confirmed present in the scaffolded `CLAUDE.md`.

### b. Fixtures + `/lore-ingest`

**Fixtures built by hand (no reportlab, no openpyxl):**

- `widget-beta-datasheet.pdf` — a hand-built 2-page raw-syntax PDF (objects/xref/trailer written directly in python3). Content:
  - Page 1: "Widget Beta Datasheet / Page 1 of 2 - Overview / Widget Beta is a precision torque sensor module. / Manufacturer: Acme Sensing Co. / Model: WB-2200"
  - Page 2: "Widget Beta Datasheet / Page 2 of 2 - Specifications / Max torque rating: 847 Nm / Operating voltage: 24V DC / Sample rate: 2000 Hz / Weight: 3.4 kg"
  - Verified valid before use: `file` reported "PDF document, version 1.4, 2 page(s)"; `pdftotext` round-tripped the exact text above.
  - Then **Read directly** (as the skill instructs) via the Read tool — it succeeded and returned both pages with the exact content, confirming a real, checkable per-page citation target (`raw/widget-beta-datasheet.pdf#p2` for the 847 Nm spec).

- `widget-beta-parts.xlsx` — hand-built via python3 `zipfile` + minimal OOXML parts (`[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`, `xl/_rels/workbook.xml.rels`, `xl/worksheets/sheet1.xml`), one sheet "Parts", 4 rows (header + 3 parts). Verified: `file` reported "Microsoft Excel 2007+"; `zipfile.namelist()` confirmed the parts. Confirmed `openpyxl` and `duckdb` are NOT importable in this environment (both raise `ModuleNotFoundError`).

- `widget-beta-icon.png` — hand-built 8x8 truecolor PNG (raw IHDR/IDAT/IEND chunks via python3 `zlib`/`struct`), red top-left quadrant, green bottom-right quadrant, white elsewhere. Verified valid: `file` reported "PNG image data, 8 x 8, 8-bit/color RGB". Read via the Read tool — rendered correctly.

- `mystery.bin` — 24 bytes of arbitrary binary data, to exercise the "anything else — skip" branch (same pattern as Task 4's test corpus).

All four copied into `/tmp/test-lore2/raw/`.

**Ingest procedure executed** (skill steps 1-4):
1. Checked each filename against `log.md` via `rg -F` — all four were new.
2. PDF: Read directly; wrote `wiki/Widget_Beta_Datasheet.md` (type: source) and `wiki/Widget_Beta.md` (type: concept), citing `raw/widget-beta-datasheet.pdf#p1` / `#p2` on every hard number.
3. Image: Read directly; wrote `wiki/Widget_Beta_Icon.md` (type: source) with a structured caption (kind, visible content, explicit "re-read the image for analysis" disclaimer per the skill).
4. Spreadsheet: `openpyxl`/`duckdb` confirmed absent. Took the documented fallback — used only python3's `zipfile` module to read structural metadata (sheet name "Parts", approx row count from raw `<row>` tag count) without a real xlsx parser; wrote `wiki/Widget_Beta_Parts.md` (type: card) recording what could be read and an explicit **Limitation** paragraph explaining column headers/cell values were NOT extracted because openpyxl/duckdb are unavailable. This is the intended fallback branch, exercised faithfully, not worked around.
5. `mystery.bin`: appended a `skip` log entry with reason (unrecognized binary, no extension handler).
6. Updated `index.md` (new `## Widget Beta` group, 4 lines) and `log.md` (one ingest entry per file + the skip entry).
7. Committed: `ingest: widget-beta-datasheet.pdf, widget-beta-parts.xlsx, widget-beta-icon.png, mystery.bin`.

**Assertions (Task 4 Step 3, adapted to `/tmp/test-lore2`):**

```
$ B=/tmp/test-lore2
$ ls "$B"/wiki/*.md >/dev/null && echo PAGES_OK
PAGES_OK
$ rg -q 'type: card' "$B"/wiki/ && echo CARD_OK
CARD_OK
$ rg -q 'widget-beta-datasheet.pdf' "$B/log.md" && rg -q 'widget-beta-parts.xlsx' "$B/log.md" && rg -q 'widget-beta-icon.png' "$B/log.md" && echo LEDGER_OK
LEDGER_OK
$ rg -q 'skip \| mystery.bin' "$B/log.md" && echo SKIP_OK
SKIP_OK
$ rg -q 'wiki/' "$B/index.md" && echo INDEX_OK
INDEX_OK
$ cd "$B" && git log --oneline -1 | grep -q '^.* ingest:' && echo COMMIT_OK
COMMIT_OK
$ awk 'length > 200 && /^- \[/' "$B/index.md" | wc -l | grep -qx 0 && echo CAPS_OK
CAPS_OK
```

All seven `*_OK` markers passed.

**Re-run (idempotency check):** re-checked all four raw filenames against `log.md` — all already logged, so per skill step 1 ("If no new files: report 'nothing to ingest' and stop (no commit)") no new commit was made. Commit count before and after: 2 (unchanged). Confirmed no-op.

### c. `/lore-link` + three questions

Re-ran the `/lore-link` procedure in `/tmp/test-project` (whose `CLAUDE.md` already had a `<!-- lore:start -->` block from Task 6, pointing at `/tmp/test-lore`). Per skill step 3 (idempotency), replaced everything between the markers with a fresh block pointing at `/tmp/test-lore2`:

```markdown
<!-- lore:start -->
## Lore
This project is linked to a knowledge base at `/tmp/test-lore2`.
- For domain/knowledge questions, use the `lore` skill: read `/tmp/test-lore2/index.md` first, then rg its wiki/; cite sources.
- Never edit `/tmp/test-lore2/raw/`. Wiki edits must follow the lore skill's conventions.
<!-- lore:end -->
```

`grep -c "lore:start\|lore:end"` = 2 (block replaced in place, not duplicated). The unrelated line above it ("Some unrelated notes here.") was preserved untouched, confirming the idempotent-replace scoped only to the marked block.

**Three questions, answered via the retrieval ladder from `skills/lore/SKILL.md`** (index → rg → page → raw):

**Q1: "What is Widget Beta and who makes it?"**
- Ladder: read `index.md` → candidate `wiki/Widget_Beta.md` → read the page (sufficient, no raw needed).
- Answer: "Widget Beta (model WB-2200) is a precision torque sensor module made by Acme Sensing Co."
- Citation: `wiki/Widget_Beta.md`

**Q2 (numeric/spec, forces raw citation): "What is the maximum torque rating of Widget Beta, and which page of the datasheet specifies it?"**
- Ladder: index → `rg -i "torque" wiki/` → `wiki/Widget_Beta.md` cites `raw/widget-beta-datasheet.pdf#p2` → opened the raw PDF page to verify precision (per the ladder's rule 4: "precision matters").
- Answer: "847 Nm, per page 2 of the datasheet ('Specifications' section: 'Max torque rating: 847 Nm')." (Note: at the time this question was answered, the wiki page still correctly stated 847 Nm — the contradiction in step d was planted afterward, deliberately mis-editing this same figure to 900 Nm.)
- Citation: `raw/widget-beta-datasheet.pdf#p2`

**Q3: "How many sheets does the Widget Beta parts spreadsheet have, and what is it named?"**
- Ladder: index → `rg -i "sheet" wiki/` → `wiki/Widget_Beta_Parts.md`.
- Answer: "One sheet, named 'Parts' (per the zip-structural metadata read — full cell contents could not be extracted because openpyxl/duckdb are not installed; see the card's Limitation note)."
- Citation: `wiki/Widget_Beta_Parts.md`

All three answers cite `raw/...` or `wiki/...` as required, and Q2 specifically exercises the `raw/<file>#p<n>` citation rule.

### d. Planted contradiction + `/lore-lint`

**Planted:** edited `wiki/Widget_Beta.md` to change "Max torque rating: 847 Nm" → "900 Nm" (now disagrees with its own cited source, `raw/widget-beta-datasheet.pdf#p2`, which genuinely says 847 Nm). Added a second page, `wiki/Widget_Beta_Rev_Note.md` (type: source, same `source:` field), a field note asserting the correct value is 847 Nm, not 900. Neither page had a `> ⚠ CONTRADICTION` marker yet.

**Failure found:** Running `lore-lint`'s check 6 exactly as originally written ("count `> ⚠ CONTRADICTION` blocks. REPORT only; never resolve") is a pure count of pre-existing markers:

```
$ rg -c '⚠ CONTRADICTION' wiki/
0 matches
```

This literally misses the planted contradiction entirely — a violation of the acceptance criterion ("`/lore-lint` reports it, does not resolve it"). The original check only audits contradictions already flagged during ingest; it has no mechanism to actively surface a fresh, unflagged disagreement introduced by a direct edit. This is a real gap, not by design (the core `lore` skill's answering rule already states contradictions must be recorded, and `lore-lint` says "Follow the `lore` skill for all conventions" — but check 6 as written didn't operationalize that for lint's own pass).

**Fix applied** to `skills/lore-lint/SKILL.md` check 6 — now instructs lint to also actively cross-check same-subject pages for unflagged conflicting claims, and FIX by *adding* a `> ⚠ CONTRADICTION` marker (recording only — never editing either claim's value or picking a winner):

```diff
-6. **Contradictions** — count `> ⚠ CONTRADICTION` blocks. REPORT only; never resolve.
+6. **Contradictions** — count existing `> ⚠ CONTRADICTION` blocks. Also actively
+   cross-check pages that share a subject (via title, wikilinks, or overlapping
+   `source:`) for conflicting claims on the same fact (e.g. differing numeric
+   specs) that carry no marker yet. FIX by adding
+   `> ⚠ CONTRADICTION: <claim A> [[Page_A]]; <claim B> [[Page_B]]` to the
+   disagreeing page(s) — this only RECORDS the disagreement; it never resolves
+   it (never edit either claim's value, never delete one, never pick a
+   winner). REPORT every contradiction found, pre-existing or newly recorded.
```

Committed in the plugin repo: `d26f98e fix: lore-lint must actively detect unflagged cross-page contradictions, not just count existing markers`.

**Re-ran the full lint pass** against `/tmp/test-lore2` with the fixed check. Findings:

- Check 1 (orphan pages): `wiki/Widget_Beta_Rev_Note.md` had no index line → FIX: added `- [Widget Beta Rev Note](wiki/Widget_Beta_Rev_Note.md) — field note disputing the max torque rating; see contradiction flag.` to `index.md`.
- Check 2 (ghost index entries): none (the only apparent hit, `wiki/Page.md`, was the template's own example inside an HTML comment, not a real entry — excluded).
- Check 3 (dead wikilinks): none.
- Check 4 (duplicate titles): none.
- Check 5 (staleness): none (all pages captured/fresh same day).
- **Check 6 (contradictions) — the target check:** cross-referenced `wiki/Widget_Beta.md` and `wiki/Widget_Beta_Rev_Note.md`, both about Widget Beta's max torque rating, both citing `raw/widget-beta-datasheet.pdf#p2`, disagreeing (900 Nm vs 847 Nm). FIX (record, not resolve): added to `wiki/Widget_Beta.md`:
  `> ⚠ CONTRADICTION: max torque rating 900 Nm [[Widget_Beta]]; max torque rating 847 Nm [[Widget_Beta_Rev_Note]]`
  and to `wiki/Widget_Beta_Rev_Note.md`:
  `> ⚠ CONTRADICTION: max torque rating 847 Nm [[Widget_Beta_Rev_Note]]; max torque rating 900 Nm [[Widget_Beta]]`
  REPORTED as an open contradiction requiring human review.
- Check 7 (index caps): 11 lines total, 0 entries over 200 chars — fine.
- Check 8 (frontmatter validity): all `type:` values valid.
- Check 9 (missing concept pages): none.
- Check 10 (missing cross-references): none (Widget_Beta ↔ Widget_Beta_Rev_Note now linked both by wikilink and contradiction marker).
- Check 11 (knowledge gaps): REPORTED — which value (900 Nm or 847 Nm) is correct is still open; recommend re-verifying against the manufacturer's published datasheet.

**Verified not resolved** — after the lint fix was applied, both conflicting values still stand untouched:

```
$ grep -n "Max torque rating" wiki/Widget_Beta.md
17:- Max torque rating: 900 Nm — `raw/widget-beta-datasheet.pdf#p2`
$ grep -n "847 Nm\|900 Nm" wiki/Widget_Beta_Rev_Note.md
11:specifications section states the max torque rating as **847 Nm**, not
12:900 Nm. Flagging for review against [[Widget_Beta]].
14:> ⚠ CONTRADICTION: max torque rating 847 Nm [[Widget_Beta_Rev_Note]]; max torque rating 900 Nm [[Widget_Beta]]
```

Neither claim was edited or deleted — lint recorded the disagreement, it did not pick a winner.

Appended to `log.md`: `## [2026-08-21] lint | 2 fixed, 2 reported` (fixed: orphan index entry + contradiction markers on both pages; reported: the contradiction itself + the knowledge gap). Committed in `/tmp/test-lore2`: `lint: fix orphan page + record unflagged contradiction, report 2 items`.

Final `/tmp/test-lore2` git log (before cleanup): `bb8b88b lint: ... → 693f86a ingest: ... → 9e3cb46 init: lore scaffold`.

## Failures hit and fixes made — summary

Exactly one failure was found during the acceptance pass, described in full above: `skills/lore-lint/SKILL.md` check 6 only counted pre-existing `> ⚠ CONTRADICTION` markers and had no mechanism to detect a genuinely new, unflagged contradiction between two pages — which is required by the acceptance criterion. Fixed by broadening check 6 to actively cross-check same-subject pages and record (never resolve) any conflict found. Verified the fix works by re-running the full lint pass and confirming the contradiction was reported and both conflicting values were left untouched. Committed as `d26f98e` (plugin repo, `fix:` prefix) and exercised inside `/tmp/test-lore2` (test-lore commit `bb8b88b`, destroyed by Step 4 cleanup — full before/after evidence is captured above).

No other failures were hit: `/lore-init`, `/lore-ingest` (both first run and no-op re-run), and `/lore-link` all behaved exactly as specified on the first try.

## Cleanup

```
$ cat ~/.claude/lore.json
{"path": "/tmp/test-lore2"}
$ ls /tmp/lore.json.bak 2>&1
(no such file — confirmed no backup exists, matching the brief's context)

$ [ -f /tmp/lore.json.bak ] && mv /tmp/lore.json.bak ~/.claude/lore.json || rm -f ~/.claude/lore.json
$ rm -rf /tmp/test-lore /tmp/test-lore2 /tmp/test-project

$ ls ~/.claude/lore.json
ls: cannot access '/home/vboxuser/.claude/lore.json': No such file or directory
$ ls -d /tmp/test-lore /tmp/test-lore2 /tmp/test-project
ls: cannot access '/tmp/test-lore': No such file or directory
ls: cannot access '/tmp/test-lore2': No such file or directory
ls: cannot access '/tmp/test-project': No such file or directory
```

Config is gone; all three test directories are removed. (`/tmp/fixtures`, the scratch dir holding the hand-built PDF/xlsx/PNG sources, was also removed as throwaway scratch — not part of the brief's mandated cleanup list but not needed afterward either.)

The `lore` plugin marketplace/install itself was intentionally left in place — Step 4 only restores `lore.json` and removes the test dirs; the install is the deliverable of Step 2 and stays installed:

```
$ timeout 60 claude plugin list | grep -i lore
  ❯ lore@lore-marketplace
```

## Tag and final git log

```
$ cd ~/Project/lore && git add -A && git commit -m "chore: v0.1.0" --allow-empty && git tag v0.1.0
[master ab1018c] chore: v0.1.0

$ git log --oneline
ab1018c chore: v0.1.0
d26f98e fix: lore-lint must actively detect unflagged cross-page contradictions, not just count existing markers
52cd4e7 docs: full README
8ab431b feat: add /lore-link skill
cabb3e3 feat: add /lore-lint skill
bc03449 feat: add /lore-ingest skill
c504bc5 fix: add spreadsheet query rule to lore CLAUDE.md template
f77d580 feat: add /lore-init skill with CLAUDE.md schema template
c0832e0 feat: add core lore skill (contract)
bd7d2e2 feat: scaffold lore plugin manifests

$ git tag -l -n1
v0.1.0          chore: v0.1.0
```

## What is NOT covered

- **The genuinely-fresh-Claude-Code-session acceptance pass.** All of Step 3 above was performed by manually executing each SKILL.md's documented procedure with Bash/Read/Write/Edit — the same method used to verify Tasks 3-6 — rather than by an actual fresh session invoking the installed slash commands (`/lore-init`, `/lore-ingest`, `/lore-link`, `/lore-lint`) end-to-end. This is a controller ruling (spawning a fresh session was not possible in this environment) and is handed to the user as a documented post-plan step: after this report, the user should open a real fresh Claude Code session with the `lore` plugin installed and re-run the same four commands against a scratch lore to confirm the installed skill-loading path (not just the SKILL.md text) behaves identically.
- **The spec's full 10-question acceptance pass** (spec §10) — only 3 questions were asked here, against a small synthetic 2-file corpus, per the brief's explicit scope reduction ("The spec's full 10-question pass runs post-plan, once the user's real corpus is seeded").
- **Real-world PDF/xlsx richness.** The PDF and xlsx fixtures were minimal, hand-built, single/few-page documents constructed to be checkable, not representative of real-world datasheets/spreadsheets (multi-column tables, images embedded in PDFs, formulas, multiple sheets, merged cells, etc.). The xlsx ingest in particular only exercised the fallback (no-openpyxl) path — the richer, `openpyxl`/`duckdb`-available path for numeric spreadsheet queries (as described in the `CLAUDE.md` template's "Numeric questions about spreadsheets" rule) was never exercised, since neither library is installed in this environment.
- Publishing the repo to a public host (so `claude plugin marketplace add <owner>/lore` works for others) — explicitly out of scope per the brief's "Post-plan" section.

## Self-review

Reviewed `git log --oneline` and `git show` for all three commits made in this task (`52cd4e7`, `d26f98e`, `ab1018c`) — diffs are minimal and precisely scoped (README replacement; an 8-line targeted fix to one check in `lore-lint/SKILL.md`; an empty tag commit).

Checked the README against actual plugin behavior:
- "Drop any file into an inbox folder; Claude distills it into an interlinked markdown wiki with a catalog index" — matches verified `lore-ingest` behavior (wiki pages + index.md entries + wikilinks, verified in step b).
- "Zero dependencies: markdown + git + ripgrep. No databases, no APIs, no models." — verified true; the xlsx ingest fallback specifically proved the plugin degrades gracefully without openpyxl/duckdb rather than requiring them.
- Install commands — verified to work exactly as written (Step 2 above).
- `/lore-init`, `/lore-ingest`, `/lore-link`, `/lore-lint` command names and one-line descriptions — match the actual skill names and verified behavior.
- "Then just ask questions in linked projects; answers cite their sources" — matches the core `lore` skill's answering rules and was exercised directly in step c.
- Folder listing (`CLAUDE.md`, `index.md`, `log.md`, `raw/`, `wiki/`) — matches the real scaffolded layout exactly, including the "raw/ never modified" and "CLAUDE.md — the schema... it wins over defaults" claims (verified via the SCHEMA_OK check).
- "`## My Take` sections are never touched by the agent" and "contradictions ... flagged, never silently resolved" — both match the core contract's answering rules verbatim, and the contradiction claim is now *more* true than before this task, since the `lore-lint` fix closes a real gap where an unflagged contradiction could previously go unnoticed by lint.
- "every change is a git commit you can review or revert" — verified: init, ingest (and its no-op case), and lint (including the no-fix-needed case, implicitly per the skill's "skip commit if nothing fixed") all commit as documented.

No README claim was found to promise behavior beyond what the skills actually implement. No further issues found.

## Fix report (post-review): stale installed plugin cache

**Finding (Important, from task review):** the installed plugin `lore@lore-marketplace` was pinned to `gitCommitSha: 52cd4e7` (the README commit) — installed during Step 2, *before* the `d26f98e` lore-lint fix (found and committed during the acceptance pass in Step 3d) and before the `ab1018c` v0.1.0 tag. The reviewer confirmed the cached copy at `/home/vboxuser/.claude/plugins/cache/lore-marketplace/lore/0.1.0/skills/lore-lint/SKILL.md` still carried the pre-fix check 6 — the exact bug the acceptance pass had found and fixed in the source repo. A real user session loading the installed plugin would have gotten the buggy skill despite the v0.1.0 tag claiming the fix. The original report did not disclose this staleness.

**What was run:**

```
$ timeout 120 claude plugin update lore@lore-marketplace -y
Checking for updates for plugin "lore@lore-marketplace" at user scope…
✔ lore is already at the latest version (0.1.0).
```
`claude plugin update` compares the declared `plugin.json` version string (`0.1.0`), which never changed across the README/fix/tag commits, so it saw no update to apply. This is a real limitation of `claude plugin update` against a local-path marketplace whose plugin version doesn't bump — noted for awareness, not treated as the final word.

```
$ timeout 60 claude plugin marketplace update lore-marketplace
Updating marketplace: lore-marketplace...Validating local marketplace
✔ Successfully updated marketplace: lore-marketplace

$ timeout 120 claude plugin update lore@lore-marketplace -y
Checking for updates for plugin "lore@lore-marketplace" at user scope…
✔ lore is already at the latest version (0.1.0).
```
Still stale after a marketplace refresh — `installed_plugins.json`'s `gitCommitSha` and `lastUpdated` for `lore@lore-marketplace` were unchanged (`52cd4e7...`, `2026-08-21T22:03:09.459Z`).

Fell back to uninstall + reinstall, the documented alternative path:

```
$ timeout 60 claude plugin uninstall lore@lore-marketplace
✔ Successfully uninstalled plugin: lore (scope: user)
```
Checked the cache directory after uninstall — it was NOT removed by uninstall, and still carried the pre-fix text:
```
$ grep -n 'CONTRADICTION' /home/vboxuser/.claude/plugins/cache/lore-marketplace/lore/0.1.0/skills/lore-lint/SKILL.md
17:6. **Contradictions** — count `> ⚠ CONTRADICTION` blocks. REPORT only; never resolve.
```

```
$ timeout 120 claude plugin install lore@lore-marketplace
Installing plugin "lore@lore-marketplace"...✔ Successfully installed plugin: lore@lore-marketplace (scope: user)
```
This time the cache directory content was overwritten with the current source-repo content (the harness's own file-watcher flagged `.../skills/lore-lint/SKILL.md changed on disk` immediately after the install, showing the new check 6 text landing in the cache).

**The three required verifications, re-run after reinstall:**

1. Post-fix text present in the cache:
```
$ grep -n 'CONTRADICTION' /home/vboxuser/.claude/plugins/cache/lore-marketplace/lore/0.1.0/skills/lore-lint/SKILL.md
17:6. **Contradictions** — count existing `> ⚠ CONTRADICTION` blocks. Also actively
21:   `> ⚠ CONTRADICTION: <claim A> [[Page_A]]; <claim B> [[Page_B]]` to the
```
Matches the post-fix wording from `d26f98e`.

2. Cache matches the repo exactly:
```
$ diff -r /home/vboxuser/Project/lore/skills /home/vboxuser/.claude/plugins/cache/lore-marketplace/lore/0.1.0/skills
(no output — diff exit code 0)
```

3. `installed_plugins.json` entry, pinned sha:
```json
"lore@lore-marketplace": [
  {
    "scope": "user",
    "installPath": "/home/vboxuser/.claude/plugins/cache/lore-marketplace/lore/0.1.0",
    "version": "0.1.0",
    "installedAt": "2026-08-21T22:18:36.297Z",
    "lastUpdated": "2026-08-21T22:18:36.297Z",
    "gitCommitSha": "ab1018cca466ba185fa8c0c1fd95486fd80c8d9f"
  }
]
```
`gitCommitSha` is `ab1018c...` — exactly the `v0.1.0` tag commit. `claude plugin list | grep -i lore` still shows `lore@lore-marketplace` installed.

**Deleted state left untouched, as instructed:** `/tmp/test-lore`, `/tmp/test-lore2`, `/tmp/test-project`, and `~/.claude/lore.json` were all confirmed still absent after the fix (`ls` on each returned "No such file or directory"); none of the uninstall/reinstall commands recreated them, and the acceptance pass was not re-run.

**Disclosure for "What is NOT covered" (superseded):** the stale-install fact itself is now resolved — the installed artifact is confirmed to match the `v0.1.0` tag. The general caveat under "What is NOT covered" above (that a genuinely fresh Claude Code session was never used to invoke the installed slash commands end-to-end) still stands, and readers should additionally note: `claude plugin update <name>` alone is **not sufficient** to pick up a source change when the plugin's `version` field in `plugin.json` hasn't been bumped — on this CLI (v2.1.239) that command silently no-ops. If the user later publishes further fixes to the `lore` repo without bumping `plugin.json`'s `version`, they should use `claude plugin uninstall lore@lore-marketplace && claude plugin install lore@lore-marketplace` (or bump the version) rather than relying on `claude plugin update`.
