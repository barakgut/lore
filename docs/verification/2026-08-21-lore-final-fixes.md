# lore plugin — final whole-branch review fixes

Date: 2026-08-21
Repo: /home/vboxuser/Project/lore
Baseline: `ab1018c` (chore: v0.1.0) → final: `0af6443`, tag `v0.1.0` moved to `0af6443`.

Status: **DONE_WITH_CONCERNS** (one extra defect found and fixed outside the findings list — see "Unlisted defect found"; nothing blocked).

---

## Finding-by-finding

### 1 (Critical) — README/skills advertise commands that will not resolve

Plugin skills are addressed `plugin:skill`, so every bare `/lore-*` was replaced with the namespaced form. Skill directory names and frontmatter `name:` fields were left untouched, per ruling.

Changed:

- `/home/vboxuser/Project/lore/README.md` — "## Use" block:
  ```
      /lore:lore-init [path]   # once — creates the lore (default ~/lore), git-inits it
      # drop files into <lore>/raw/   (PDF, images, xlsx/csv, md, txt, saved HTML)
      /lore:lore-ingest        # distill new raw files into the wiki
      /lore:lore-link          # once per project — point it at the lore
      /lore:lore-lint          # periodic health check (after ~5 ingests or monthly)
  ```
- `skills/lore-init/SKILL.md` — `description: Use when the user runs /lore:lore-init [path] — …`; heading `# /lore:lore-init [path]`; step 6 next steps now `run /lore:lore-ingest`, `run /lore:lore-link`.
- `skills/lore-ingest/SKILL.md` — `description: Use when the user runs /lore:lore-ingest — …`; heading `# /lore:lore-ingest`.
- `skills/lore-lint/SKILL.md` — `description: Use when the user runs /lore:lore-lint — …`; heading `# /lore:lore-lint`.
- `skills/lore-link/SKILL.md` — `description: Use when the user runs /lore:lore-link inside a project — …`; heading `# /lore:lore-link`; step 1 now points at `/lore:lore-init`.
- `skills/lore/SKILL.md` — "Finding the lore": "tell the user to run `/lore:lore-init` and stop."
- `skills/lore-init/templates/CLAUDE.md` — "## Operations": ``/lore:lore-ingest`` — process new `raw/` files into the wiki. ``/lore:lore-lint`` — health check. ``/lore:lore-link`` — point a project at this lore.
- `.claude-plugin/plugin.json` — description tail now "Link any project to it with /lore:lore-link." (a bare name here would also have been wrong and is caught by the repo-wide grep).

Each `description:` still names its trigger explicitly.

### 2 (Important) — lint left the lore dirty / commit unreachable

`skills/lore-lint/SKILL.md` "## Output" is now:

```
- Apply all FIXes, then append to `log.md`: `## [YYYY-MM-DD] lint | <n> fixed, <m> reported`.
  Count each item once: a newly recorded contradiction marker is a FIX, so it belongs in `<n>` and not in `<m>`, even though the user-facing report lists every contradiction.
- Then commit: `cd "$LORE" && git add -A && git commit -m "lint: <summary>"`. Always commit — the log entry is itself a change, so a lint run is never a clean tree.
- Report to the user: fixed items, then reported items grouped by check, each with file paths.
```

Log append now precedes the commit (matching `lore-ingest`), and the commit is unconditional with the reason stated. (The `<n>`/`<m>` sentence also discharges half of finding 14.)

### 3 (Important) — ingest narrowed its deference; `## My Take` unprotected

`skills/lore-ingest/SKILL.md`:

- Opening: "Follow the `lore` skill for all conventions. Lore path comes from `~/.claude/lore.json`; read `$LORE/CLAUDE.md` first — where it differs from these defaults, it wins."
- §2 page-update step, appended: "When updating, never rewrite, reorder, or delete a `## My Take` section — those are human-owned; add your new material outside them."

### 4 (Important) — substring ledger matching / no re-ingest path

`skills/lore-ingest/SKILL.md` §1 now reads:

```
A file is NEW iff its filename is not the subject of a ledger entry heading — check the headings only, not the whole file:

    rg -N '^## \[' "$LORE/log.md" | rg -F "<filename>"

Matching the whole file would let a detail line (or a longer filename like `v2_spec.pdf`) mask an unprocessed `spec.pdf`.

**Re-ingest:** if the user names a specific file, process it regardless of the ledger and append a fresh `ingest` entry — that is how a page written under a limitation (e.g. a `card` written while openpyxl was absent) gets upgraded.
```

The same anchored rule was propagated to the core contract and the template (see "Cross-file consistency" below), since all three previously stated the loose version.

### 5 (Important) — contradictory index caps

Per the controller ruling the ~200-**line** cap is now REPORT-only with a stated remedy; the <200-**character**-per-entry cap stays a FIX. Applied in all three places plus the scaffold comment:

- `skills/lore/SKILL.md` "## index.md rules":
  ```
  - Format per line: `- [Title](wiki/Page.md) — one-line hook`. Hard cap <200 chars per entry: tighten the hook to fit.
  - Grouped under `##` topic headings. Target ~200 lines total; past that, never drop entries to fit — every page must stay reachable from the index. Report it and propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.
  ```
- `skills/lore-init/templates/CLAUDE.md` "## Layout", `index.md` bullet: same two rules, in the template's single-bullet voice.
- `skills/lore-lint/SKILL.md` check 7, split in two:
  ```
  7. **Index entry cap** — entries over 200 chars. FIX: tighten the hook.
     **Index size** — file over ~200 lines. REPORT only: do not drop entries to fit (every page must stay reachable from the index); propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.
  ```
- `skills/lore-init/SKILL.md` scaffold comment: `<!-- One line per wiki page: - [Title](wiki/Page.md) — hook. Grouped by ## topic. <200 chars per entry; target ~200 lines. -->`

Check 1 (orphan pages → FIX by adding an index line) is now satisfiable in every state. This is a knowing departure from spec §4.3's "hard cap" on lines, per ruling.

### 6 (Important) — undefined behavior on half-present marker pair

`skills/lore-link/SKILL.md` step 3, appended: "If `<!-- lore:start -->` is present but `<!-- lore:end -->` is not, do NOT modify the file: report the malformed block and ask the user to fix or remove it (writing to EOF would destroy whatever they wrote after it)."

### 7 (Important) — unresolved `<skill-base-dir>` placeholder

`skills/lore-init/SKILL.md`:

- Preamble: "The full-rules schema every new lore is seeded with lives at `${CLAUDE_PLUGIN_ROOT}/skills/lore-init/templates/CLAUDE.md` — i.e. `templates/CLAUDE.md` next to this file, if you need to locate it another way."
- Step 4 bash: `cp "${CLAUDE_PLUGIN_ROOT}/skills/lore-init/templates/CLAUDE.md" "$LORE/CLAUDE.md"`
- New fail-loud paragraph after the block: "If that copy fails — `CLAUDE_PLUGIN_ROOT` unset or the template not found there — locate `templates/CLAUDE.md` next to this SKILL.md and copy it. If you still cannot find it, STOP and tell the user: a lore without its `CLAUDE.md` has no schema layer, and step 2 will refuse to heal it later."

### 8 (Important) — spec §9 bootstrapping had no implementation

- `skills/lore-ingest/SKILL.md` §1, new line: "**Existing notes:** also treat any `$LORE/wiki/*.md` with no YAML frontmatter as new — add frontmatter, an `index.md` line, and an `ingest` log entry (§9 bootstrapping: notes copied in from a prior system)."
- `README.md`, new section:
  ```
  ## Bootstrapping existing notes

  Already have a pile of notes? Copy the source documents into `<lore>/raw/` and
  any already-distilled notes into `<lore>/wiki/`, then run `/lore:lore-ingest`:
  raw files are distilled as usual, and wiki pages without frontmatter get
  frontmatter, an index entry, and a log entry. One-time copy — the pages belong
  to the lore from then on.
  ```

### 9 (Minor) — template softened raw immutability

`skills/lore-init/templates/CLAUDE.md`, `raw/` bullet: "… IMMUTABLE: never edit or delete anything here. Originals are ground truth and always win over derived wiki text." (was "IMMUTABLE after ingest; originals are …"). Now matches the core contract's imperative verbatim.

### 10 (Minor) — template dropped index cap guidance

Restored, in the form ruling 5 leaves it in — see finding 5 above.

### 12 (Minor) — `init:` missing from commit-prefix lists

- `skills/lore/SKILL.md`: "Every mutation of the lore (init, ingest, lint fix, answer promotion) ends with `git add -A && git commit` inside the lore repo, message prefixed `init:`, `ingest:`, `lint:`, or `answer:`."
- `skills/lore-init/templates/CLAUDE.md`: "Every mutation (init, ingest, lint fix, answer promotion) ends with a commit here, message prefixed `init:`, `ingest:`, `lint:`, or `answer:`."

### 13 (Minor) — lint check 2 would delete the scaffold comment

`skills/lore-lint/SKILL.md` check 2: "**Ghost index entries** — entry lines in `index.md` (lines matching `^- \[`, never HTML comments or scaffold guidance) pointing at missing files. FIX: remove the line."

### 14 (Minor) — check 6: marker names, double count, idempotency

`skills/lore-lint/SKILL.md` check 6 now:

```
6. **Contradictions** — count existing `> ⚠ CONTRADICTION` blocks. Also actively
   cross-check pages that share a subject (via title, wikilinks, or overlapping
   `source:`) for conflicting claims on the same fact (e.g. differing numeric
   specs). Skip any pair where either page already carries a CONTRADICTION
   marker naming that fact — lint is idempotent, so a re-run never adds a
   second marker for the same disagreement. Otherwise FIX by adding
   `> ⚠ CONTRADICTION: <claim A> [[Source_A]]; <claim B> [[Source_B]]` to the
   disagreeing page(s) — this only RECORDS the disagreement; it never resolves
   it (never edit either claim's value, never delete one, never pick a
   winner). REPORT every contradiction found, pre-existing or newly recorded.
```

Marker placeholders now match the core contract (`Source_A`/`Source_B`); "that carry no marker yet" became an explicit idempotency rule; the double-count is fixed in "## Output" (a newly recorded marker counts in `<n> fixed` only).

### 15 (Minor) — `ls -1` misses subdirectories and dotfiles

`skills/lore-ingest/SKILL.md` §1:

```bash
find "$LORE/raw" -type f -printf '%P\n'
```
followed by "(`find`, not `ls` — a dropped folder of documents and dotfiles must be seen too; paths are relative to `raw/`.)"

### 16 (Minor) — lore-link never checks it is at a project root

`skills/lore-link/SKILL.md` step 2: "Target file: `./CLAUDE.md` in the current project root (create if absent). Sanity-check that this IS the project root: if `./.git` is absent, confirm the path with the user before writing — a `CLAUDE.md` left in a subdirectory is never loaded."

### 17 (Minor) — README gaps (four)

- Config file / re-pointing, after the Use block: "The lore's location is stored in `~/.claude/lore.json`. If that file is lost or you move the folder, `/lore:lore-init <path>` on the existing lore just re-points the config — it never touches your notes."
- Own git repo, at the end: "The lore is its own git repository — back it up like any other repo, or add a remote and push it to carry your knowledge base between machines."
- Unknown types, in the intro: "… into an interlinked markdown wiki with a catalog index — file types it cannot read are skipped with a note in the log, never silently dropped."
- Dependencies: "Zero dependencies: markdown + git + ripgrep, plus python3 for reading spreadsheets. No databases, no APIs, no models."

### 19 (Minor) — unescaped JSON path

`skills/lore-init/SKILL.md` step 5:

```bash
mkdir -p ~/.claude
python3 -c 'import json,sys; print(json.dumps({"path": sys.argv[1]}))' "$LORE" > ~/.claude/lore.json
```

---

## Unlisted defect found and fixed

`skills/lore-lint/SKILL.md`'s `description:` contained an unquoted `": "` — "health-check the lore: orphan pages, …" — which makes the YAML frontmatter **unparseable** (`yaml.scanner.ScannerError: mapping values are not allowed here`). This was pre-existing at `ab1018c` and is not in the findings list, but the mandated verification ("parseable YAML frontmatter") exposed it. Minimal fix, keeping the sentence unquoted like its four siblings: "health-check the lore **for** orphan pages, …". Raising it here rather than silently absorbing it — it is the reason the status is DONE_WITH_CONCERNS.

## Deliberately NOT changed

- **Finding 18 (LICENSE / extra manifest fields)** — parked by ruling; no license file added, no manifest fields added.
- **Skill directory names and frontmatter `name:` fields** — left as `lore`, `lore-init`, `lore-ingest`, `lore-lint`, `lore-link` per ruling on finding 1 (spec §7 fixes them); only the documented invocation form changed.
- **`plugin.json` version** — stays `0.1.0`.
- **`marketplace.json`** — untouched; its description contains no command name.
- **Spec §4.3's "hard cap ~200 lines"** — knowingly departed from, per ruling 5. The spec file itself was not edited (it is in the oidar repo, not the product).
- **Ingest §3's "respect the caps from the `lore` skill"** — left as-is; it now inherits the corrected caps by reference, so no local restatement was needed.
- **No lore was scaffolded and no skill procedure was run** — verification is static only.

---

## Verification

### Manifests parse

```
$ python3 -m json.tool .claude-plugin/plugin.json
{
    "name": "lore",
    "version": "0.1.0",
    "description": "Lore (Long-term Organized Reference): a persistent, human-readable knowledge base on disk, maintained by Claude Code skills: drop files into raw/, get an interlinked markdown wiki with a catalog index. Link any project to it with /lore:lore-link.",
    "author": {
        "name": "kutzuim"
    }
}
$ python3 -m json.tool .claude-plugin/marketplace.json
{
    "name": "lore-marketplace",
    "owner": {
        "name": "kutzuim"
    },
    "plugins": [
        {
            "name": "lore",
            "source": "./",
            "description": "Lore (Long-term Organized Reference) — a markdown second brain for Claude Code: universal inbox, agent-maintained wiki, index-first retrieval."
        }
    ]
}
```

### Frontmatter parses as YAML and `name` matches directory

Script (PyYAML, stock on this machine):

```python
import yaml,re,os
ok=True
for d in sorted(os.listdir('skills')):
    p=os.path.join('skills',d,'SKILL.md')
    t=open(p,encoding='utf-8').read()
    m=re.match(r'^---\n(.*?)\n---\n', t, re.S)
    fm=yaml.safe_load(m.group(1))
    good = isinstance(fm,dict) and fm.get('name')==d and fm.get('description')
    ok &= bool(good)
    print(f"{p}: yaml parses OK | name={fm.get('name')!r} == dir {d!r}: {fm.get('name')==d} | keys={sorted(fm)}")
print('ALL OK' if ok else 'FAILURES')
```

Output:

```
skills/lore/SKILL.md: yaml parses OK | name='lore' == dir 'lore': True | keys=['description', 'name']
skills/lore-ingest/SKILL.md: yaml parses OK | name='lore-ingest' == dir 'lore-ingest': True | keys=['description', 'name']
skills/lore-init/SKILL.md: yaml parses OK | name='lore-init' == dir 'lore-init': True | keys=['description', 'name']
skills/lore-link/SKILL.md: yaml parses OK | name='lore-link' == dir 'lore-link': True | keys=['description', 'name']
skills/lore-lint/SKILL.md: yaml parses OK | name='lore-lint' == dir 'lore-lint': True | keys=['description', 'name']
ALL OK
```

(The same run before the finding-outside-the-list fix ended in `yaml.scanner.ScannerError: mapping values are not allowed here … line 2, column 76: … ore-lint — health-check the lore: orphan pages,` — that is the evidence for the unlisted defect.)

### Cross-file consistency for every rule touched

```
$ C=skills/lore/SKILL.md; T=skills/lore-init/templates/CLAUDE.md

=== RULE: commit prefixes (must all list init:, ingest:, lint:, answer:) ===
skills/lore-init/templates/CLAUDE.md:59:Every mutation (init, ingest, lint fix, answer promotion) ends with a commit here, message prefixed `init:`, `ingest:`, `lint:`, or `answer:`.
skills/lore/SKILL.md:82:Every mutation of the lore (init, ingest, lint fix, answer promotion) ends with `git add -A && git commit` inside the lore repo, message prefixed `init:`, `ingest:`, `lint:`, or `answer:`.
28:cd "$LORE" && git init -q && git add -A && git commit -q -m "init: lore scaffold"          (skills/lore-init/SKILL.md)
54:cd "$LORE" && git add -A && git commit -m "ingest: <filenames>"                            (skills/lore-ingest/SKILL.md)
38:- Then commit: `cd "$LORE" && git add -A && git commit -m "lint: <summary>"`. Always commit — the log entry is itself a change, so a lint run is never a clean tree.   (skills/lore-lint/SKILL.md)

=== RULE: index caps (<200 chars = FIX; ~200 lines = REPORT, never drop) ===
skills/lore/SKILL.md:66:- Format per line: `- [Title](wiki/Page.md) — one-line hook`. Hard cap <200 chars per entry: tighten the hook to fit.
skills/lore/SKILL.md:67:- Grouped under `##` topic headings. Target ~200 lines total; past that, never drop entries to fit — every page must stay reachable from the index. Report it and propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.
skills/lore-lint/SKILL.md:27:7. **Index entry cap** — entries over 200 chars. FIX: tighten the hook.
skills/lore-lint/SKILL.md:28:   **Index size** — file over ~200 lines. REPORT only: do not drop entries to fit (every page must stay reachable from the index); propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.
skills/lore-init/templates/CLAUDE.md:14:- `index.md` — catalog: one line per page (`- [Title](wiki/Page.md) — hook`), grouped under `##` topic headings. Read first on every query. Hard cap <200 chars per entry: tighten the hook to fit. Target ~200 lines total; past that, never drop entries to fit — every page must stay reachable from the index. Report it and propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.
skills/lore-init/SKILL.md:20:<!-- One line per wiki page: - [Title](wiki/Page.md) — hook. Grouped by ## topic. <200 chars per entry; target ~200 lines. -->

=== RULE: raw/ immutability imperative ===
skills/lore/SKILL.md:21:  raw/              # inbox + originals. IMMUTABLE: never edit or delete anything here
skills/lore-init/templates/CLAUDE.md:12:- `raw/` — inbox + originals: drop any file here (PDF, image, xlsx/csv, md, txt, saved HTML). IMMUTABLE: never edit or delete anything here. Originals are ground truth and always win over derived wiki text.

=== RULE: contradiction marker format ===
skills/lore/SKILL.md:60:  `> ⚠ CONTRADICTION: <claim A> [[Source_A]]; <claim B> [[Source_B]]`
skills/lore-ingest/SKILL.md:43:… If a new source contradicts an existing page, add a `> ⚠ CONTRADICTION:` block to that page — do not pick a winner.
skills/lore-lint/SKILL.md:17:6. **Contradictions** — count existing `> ⚠ CONTRADICTION` blocks. Also actively
skills/lore-lint/SKILL.md:20:   specs). Skip any pair where either page already carries a CONTRADICTION
skills/lore-lint/SKILL.md:23:   `> ⚠ CONTRADICTION: <claim A> [[Source_A]]; <claim B> [[Source_B]]` to the
skills/lore-init/templates/CLAUDE.md:53:- Contradictions are never silently resolved: `> ⚠ CONTRADICTION: <A> [[Source_A]]; <B> [[Source_B]]`.

=== RULE: processed-file ledger anchored to entry headings ===
skills/lore/SKILL.md:78:A `raw/` file counts as already-processed iff its filename is the subject of an entry heading (`^## \[`) in `log.md` — match the headings, not the whole file, so a detail line never masks an unprocessed file.
skills/lore-ingest/SKILL.md:19:A file is NEW iff its filename is not the subject of a ledger entry heading — check the headings only, not the whole file:
skills/lore-init/templates/CLAUDE.md:15:- `log.md` — append-only history; also the processed-file ledger (a `raw/` file is new iff its filename is not the subject of an entry heading (`^## \[`) in `log.md` — match the headings, not the whole file).

=== RULE: ## My Take human-owned ===
skills/lore/SKILL.md:61:- **`## My Take` sections are human-owned.** Never rewrite, reorder, or delete them.
skills/lore-init/templates/CLAUDE.md:54:- `## My Take` sections are human-owned: never rewrite, reorder, or delete them.
skills/lore-ingest/SKILL.md:35:… When updating, never rewrite, reorder, or delete a `## My Take` section — those are human-owned; add your new material outside them.
README.md:49:Notes for humans: sections headed `## My Take` are never touched by the agent;
```

All five rules agree across the core contract, the template, and the relevant operation skills.

### No bare command names, no placeholder

```
$ git grep -n -E '(^|[^:a-zA-Z])/lore-(init|ingest|lint|link)' -- .
  none
$ git grep -n 'skill-base-dir' -- .
  none
```

(The regex excludes a preceding `:` so `/lore:lore-init` does not match, and excludes a preceding letter so path fragments like `skills/lore-init/SKILL.md` do not match. A looser `grep -rn` was run first and its only content hit — `skills/lore/SKILL.md:10` — was fixed before this run.)

### No lore-scaffolding side effects

```
$ ls ~/.claude/lore.json
ls: cannot access '/home/vboxuser/.claude/lore.json': No such file or directory
$ ls -d /tmp/test-lore* /tmp/test-project
ls: cannot access '/tmp/test-lore*': No such file or directory
ls: cannot access '/tmp/test-project': No such file or directory
```

Nothing was created; no skill procedure was executed.

---

## Reinstall

```
$ timeout 120 claude plugin uninstall lore@lore-marketplace
✔ Successfully uninstalled plugin: lore (scope: user)
EXIT=0

$ timeout 120 claude plugin install lore@lore-marketplace --scope user
Installing plugin "lore@lore-marketplace"...✔ Successfully installed plugin: lore@lore-marketplace (scope: user)
EXIT=0
```

Post-install verification 1 — `installed_plugins.json` pins the final commit:

```
    "lore@lore-marketplace": [
      {
        "scope": "user",
        "installPath": "/home/vboxuser/.claude/plugins/cache/lore-marketplace/lore/0.1.0",
        "version": "0.1.0",
        "installedAt": "2026-08-21T22:35:18.888Z",
        "lastUpdated": "2026-08-21T22:35:18.888Z",
        "gitCommitSha": "0af6443e46e751458e79606a98e3b84989de7cbb"
      }
    ]
```

Post-install verification 2 — skills tree identical:

```
$ diff -r /home/vboxuser/Project/lore/skills /home/vboxuser/.claude/plugins/cache/lore-marketplace/lore/0.1.0/skills
SKILLS IDENTICAL (no output)
```

Post-install verification 3 — the template shipped (the one file a failed copy would silently omit):

```
$ ls -l …/lore/0.1.0/skills/lore-init/templates/
-rw-rw-r-- 1 vboxuser vboxuser 3550 Aug 21 22:35 CLAUDE.md
```

Installed tree also carries `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`.

---

## Finished repo state

```
$ git log --oneline -3
0af6443 fix: correct command names, ledger matching, and lint/link failure modes
ab1018c chore: v0.1.0
d26f98e fix: lore-lint must actively detect unflagged cross-page contradictions, not just count existing markers

$ git tag -l --points-at HEAD
v0.1.0

$ git status --short
(clean)

$ git diff --stat ab1018c..HEAD
 .claude-plugin/plugin.json           |  2 +-
 README.md                            | 31 ++++++++++++++++++++++++-------
 skills/lore-ingest/SKILL.md          | 26 ++++++++++++++++++++------
 skills/lore-init/SKILL.md            | 16 +++++++++-------
 skills/lore-init/templates/CLAUDE.md | 10 +++++-----
 skills/lore-link/SKILL.md            | 10 +++++-----
 skills/lore-lint/SKILL.md            | 20 ++++++++++++--------
 skills/lore/SKILL.md                 | 10 +++++-----
 8 files changed, 81 insertions(+), 44 deletions(-)
```

One commit, since every finding group touches files shared with other groups and hunk-level staging is not available non-interactively; the commit message enumerates the groups.

---

## Self-review of `git diff ab1018c..HEAD`

- **Unintended rule changes:** none found. Every hunk maps to a finding (or to the unlisted YAML defect). No untouched rule was reworded, no section was restructured, no section was added beyond the README's "Bootstrapping existing notes" (finding 8) and the two README sentences of finding 17.
- **README still matches the skills:** the Use block's four commands match the four skill headings and descriptions; the "skipped with a note in the log" claim matches `lore-ingest` §2's "Anything else — … Append a `skip` entry to `log.md` with the reason"; the "re-points the config, never touches your notes" claim matches `lore-init` step 2's existing-lore branch; the bootstrapping section matches `lore-ingest` §1's new frontmatter-less-wiki-page rule; "python3" matches the spreadsheet pipeline's use of python3/openpyxl and `lore-init` step 5's new `json.dumps` call.
- **Ripple check on ruling 5:** lint check 1 (orphan → add an index line) and check 7 no longer prescribe opposite actions in any state; `lore-ingest` §3's "respect the caps from the `lore` skill" now resolves to the corrected caps.
- **Ripple check on the ledger change:** the anchored rule is stated identically in the core contract, the template, and `lore-ingest`; the `init` entry the scaffold writes (`## [date] init | lore created`) is a heading in the same form, so no false "already processed" hit is possible for a raw file named "lore created".
- **`find … -printf '%P\n'`** is GNU findutils (present on this Linux box, stock) — no new dependency; it prints paths relative to `raw/`, which is what the ledger and the log entries record.
- **Nits accepted:** the README now says "Zero dependencies: markdown + git + ripgrep, plus python3 …", which reads slightly against "zero"; kept because python3 is stock and the finding explicitly asked for it to be named. The commit message's phrase "quote-free fix" describes the YAML repair (reworded the sentence rather than quoting the scalar).

---

# Addendum — residual on finding 4 (controller ruling, second pass)

Date: 2026-08-21
Baseline for this pass: `0af6443` → final `0e6cedc`; tag `v0.1.0` force-moved from `0af6443` to `0e6cedc`.

## The residual, restated

The first-pass fix anchored the ledger search to `^## \[` heading lines. That removed the
detail-line false positive but NOT the collision the finding was named for: `lore-ingest` §3
writes the heading `## [YYYY-MM-DD] ingest | v2_spec.pdf`, and `rg -F "spec.pdf"` matches that
heading as a literal substring. A later-dropped `spec.pdf` was therefore still classified as
already-processed and silently never ingested. Compounding it, the rationale sentence I added
asserted the case was handled — a false guarantee a future agent would trust instead of adding
real delimiting.

## What changed (three files, nothing else)

The filename must now be the ENTIRE remainder of the heading line — the whole field after `| `,
anchored at both ends: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`.

One sentence, byte-identical in all three files that state the rule:

> A `raw/` file counts as already-processed iff `log.md` contains an entry heading whose filename
> field is exactly that filename: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`. Match the
> whole field, anchored at both ends — never a substring: `spec.pdf` occurs inside the heading for
> `v2_spec.pdf`, so a substring test (`rg -F "spec.pdf"`) would classify a newly dropped `spec.pdf`
> as already processed and silently never ingest it.

- `skills/lore/SKILL.md` (line 78, "## log.md rules") — the sentence, verbatim.
- `skills/lore-init/templates/CLAUDE.md` (line 15, `log.md` bullet) — the sentence, verbatim, after
  "append-only history; also the processed-file ledger."
- `skills/lore-ingest/SKILL.md` §1 — the sentence with "A file" for "A `raw/` file" and
  "Everything else is NEW." appended (it is the operative step), replacing BOTH the old
  `rg -N '^## \[' | rg -F` command and the false rationale line. Since `rg -F` cannot anchor, the
  executable form is now a python3 check that regex-escapes the candidate filename (python3 is
  already a stated dependency):

```bash
python3 - "$LORE/log.md" "<filename>" <<'PY'
import re, sys
log = open(sys.argv[1], encoding='utf-8').read()
pat = r'^## \[[0-9-]{10}\] (?:ingest|skip) \| ' + re.escape(sys.argv[2]) + r'\s*$'
print("PROCESSED" if re.search(pat, log, re.M) else "NEW")
PY
```

Nothing else was touched: no other finding, no restructuring, finding 18 still parked. `git diff`
for this pass covers exactly these three files.

## Verification

### Both directions, `ingest |` and `skip |`

Fixture (`/tmp/lore-rule-demo/log.md`, deleted after the run) — note the detail line deliberately
contains `spec.pdf`, and the headings use the longer names:

```
# Lore Log

## [2026-08-21] init | lore created

## [2026-08-21] ingest | v2_spec.pdf
Created 3 pages; see spec.pdf notes inline.

## [2026-08-21] skip | v2_archive.zip
Unknown type.
```

Result (new whole-field rule vs. the substring rule the ruling rejects):

```
spec.pdf           whole-field -> NEW        (old substring rule -> PROCESSED)
v2_spec.pdf        whole-field -> PROCESSED  (old substring rule -> PROCESSED)
archive.zip        whole-field -> NEW        (old substring rule -> PROCESSED)
v2_archive.zip     whole-field -> PROCESSED  (old substring rule -> PROCESSED)
lore created       whole-field -> NEW        (old substring rule -> PROCESSED)

BOTH DIRECTIONS OK: v2_spec.pdf/v2_archive.zip match; spec.pdf/archive.zip do not.
```

The three asserts in that script (ingest direction, skip direction, and "an `init` heading is not a
file ledger entry") all passed — a rule that never matches would have failed the first two.

Running the snippet **exactly as shipped** in `skills/lore-ingest/SKILL.md`:

```
shipped snippet, verbatim from skills/lore-ingest/SKILL.md:
  spec.pdf         -> NEW
  v2_spec.pdf      -> PROCESSED
  archive.zip      -> NEW
  v2_archive.zip   -> PROCESSED
```

### The three files state the rule identically

```
$ git grep -n 'whole field, anchored at both ends' -- .
skills/lore-ingest/SKILL.md:19:A file counts as already-processed iff `log.md` contains an entry heading whose filename field is exactly that filename: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`. Match the whole field, anchored at both ends — never a substring: `spec.pdf` occurs inside the heading for `v2_spec.pdf`, so a substring test (`rg -F "spec.pdf"`) would classify a newly dropped `spec.pdf` as already processed and silently never ingest it. Everything else is NEW.
skills/lore-init/templates/CLAUDE.md:15:- `log.md` — append-only history; also the processed-file ledger. A `raw/` file counts as already-processed iff `log.md` contains an entry heading whose filename field is exactly that filename: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`. Match the whole field, anchored at both ends — never a substring: `spec.pdf` occurs inside the heading for `v2_spec.pdf`, so a substring test (`rg -F "spec.pdf"`) would classify a newly dropped `spec.pdf` as already processed and silently never ingest it.
skills/lore/SKILL.md:78:A `raw/` file counts as already-processed iff `log.md` contains an entry heading whose filename field is exactly that filename: `^## \[YYYY-MM-DD\] (ingest|skip) \| <filename>$`. Match the whole field, anchored at both ends — never a substring: `spec.pdf` occurs inside the heading for `v2_spec.pdf`, so a substring test (`rg -F "spec.pdf"`) would classify a newly dropped `spec.pdf` as already processed and silently never ingest it.
```

Byte-identity of the shared span (regex-extracted from each file and compared):

```
skills/lore/SKILL.md: identical to core contract -> True
skills/lore-init/templates/CLAUDE.md: identical to core contract -> True
skills/lore-ingest/SKILL.md: identical to core contract -> True
```

### Frontmatter still parses (unchanged, re-checked)

```
skills/lore/SKILL.md: yaml OK, name='lore' == dir: True
skills/lore-ingest/SKILL.md: yaml OK, name='lore-ingest' == dir: True
skills/lore-init/SKILL.md: yaml OK, name='lore-init' == dir: True
skills/lore-link/SKILL.md: yaml OK, name='lore-link' == dir: True
skills/lore-lint/SKILL.md: yaml OK, name='lore-lint' == dir: True
```

### No side effects

```
$ ls ~/.claude/lore.json
ls: cannot access '/home/vboxuser/.claude/lore.json': No such file or directory
$ ls -d /tmp/test-lore* /tmp/test-project
ls: cannot access '/tmp/test-lore*': No such file or directory
ls: cannot access '/tmp/test-project': No such file or directory
```

The demonstration fixture lived in `/tmp/lore-rule-demo/` (a plain `log.md`, not a lore) and was
removed; no skill procedure was run.

## Commit, tag, reinstall

```
$ git commit  →  0e6cedc fix: match the processed-file ledger on the whole filename field
$ git tag -f v0.1.0
Updated tag 'v0.1.0' (was 0af6443)
$ git log --oneline -2
0e6cedc fix: match the processed-file ledger on the whole filename field
0af6443 fix: correct command names, ledger matching, and lint/link failure modes
$ git tag -l --points-at HEAD
v0.1.0
$ git status --short
CLEAN
```

```
$ timeout 120 claude plugin uninstall lore@lore-marketplace
✔ Successfully uninstalled plugin: lore (scope: user)
EXIT=0
$ timeout 120 claude plugin install lore@lore-marketplace --scope user
Installing plugin "lore@lore-marketplace"...✔ Successfully installed plugin: lore@lore-marketplace (scope: user)
EXIT=0

$ diff -r /home/vboxuser/Project/lore/skills /home/vboxuser/.claude/plugins/cache/lore-marketplace/lore/0.1.0/skills
IDENTICAL (no output)

$ installed_plugins.json → plugins["lore@lore-marketplace"]
[
  {
    "scope": "user",
    "installPath": "/home/vboxuser/.claude/plugins/cache/lore-marketplace/lore/0.1.0",
    "version": "0.1.0",
    "installedAt": "2026-08-21T22:44:54.849Z",
    "lastUpdated": "2026-08-21T22:44:54.849Z",
    "gitCommitSha": "0e6cedc35b4d6a84c9b32b3184891ff049a39c94"
  }
]
```

`plugin.json` version remains `0.1.0`.

## Note for the record

The first-pass rationale sentence claimed a guarantee the rule did not deliver. The corrected text
names the exact colliding pair (`v2_spec.pdf` / `spec.pdf`) as the reason the match is whole-field,
so the guarantee stated and the guarantee implemented are now the same one.
