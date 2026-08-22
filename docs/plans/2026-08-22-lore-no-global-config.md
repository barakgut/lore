# Remove Global Config — Self-Describing Lore Folders — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete `~/.claude/lore.json` so a lore is a fully self-describing folder, located by a four-rung resolution ladder that hard-fails instead of guessing.

**Architecture:** All five skills are markdown instruction files; there is no compiled code and no test framework. The `lore` core skill owns the authoritative copy of the resolution ladder and the git rule; the other four defer to it by name and must not restate the rules differently. Verification is therefore two-layer: static assertions (python3/bash over the skill text) prove the prose says the right thing, and a recorded live acceptance transcript proves the skills behave correctly when Claude Code actually executes them.

**Tech Stack:** Claude Code plugin format (`skills/*/SKILL.md`), bash, git, python3, ripgrep.

**Spec:** `docs/specs/2026-08-22-lore-no-global-config.md`

## Global Constraints

- No skill file and no line of the README may name `~/.claude/lore.json` — not even to say it is unused. Naming a path teaches the agent the path is part of the system; the target behaviour is not "ignore it" but "have never heard of it". A stale file is then inert by construction, proven live in Task 6, Scenario 6.
- The resolution ladder has exactly four rungs, first match wins: (1) a path in the user's message, (2) cwd is a lore, (3) the project's `lore:start` block, (4) hard fail.
- Rung 4 message, verbatim: ``No lore found. `cd` into a lore, pass its path (`/lore:lore-ingest <path>`), or run `/lore:lore-link <path>` in this project.``
- A rung that matches but resolves to a non-lore path is a hard failure naming that path — never a fall-through to the next rung.
- Two "is a lore" tests: rung 2 requires `index.md` **and** `raw/` **and** `wiki/`; rungs 1 and 3 require only `index.md`.
- Git stays the default for new lores. `--no-git` is the only escape hatch.
- Repo test, used verbatim in both ingest and lint: `git -C "$LORE" rev-parse --git-dir >/dev/null 2>&1`
- A non-git lore is not an error: do the work, skip the commit, say so in the report, never offer to run `git init`.
- `skills/lore/SKILL.md` is the authoritative copy of the ladder and the git rule. Tasks 2-4 reference it by name and must not paraphrase it into different rules.
- No changes to: page schema, frontmatter, index/log formats, the retrieval ladder for *content*, contradiction handling, `## My Take` rules, or any lint check.
- `docs/specs/2026-08-21-lore-plugin-design.md` and `docs/plans/2026-08-21-lore-plugin.md` are historical records — never edited.
- Live testing uses throwaway lores under `/tmp` only. Any real `~/.claude/lore.json` on the machine is backed up before a task that could touch it and restored after.

## File Structure

```
skills/
  lore/SKILL.md                     # Task 1 — authoritative ladder + git rule
  lore-init/SKILL.md                # Task 2 — drop config write, add --no-git
  lore-init/templates/CLAUDE.md     # Task 2 — git section gains the no-git case
  lore-link/SKILL.md                # Task 3 — path becomes a required argument
  lore-ingest/SKILL.md              # Task 4 — ladder header + commit guard
  lore-lint/SKILL.md                # Task 4 — ladder header + commit guard
README.md                           # Task 5 — Use section + config paragraph
.claude-plugin/plugin.json          # Task 5 — version 0.1.0 → 0.2.0
docs/verification/2026-08-22-lore-no-global-config-acceptance.md   # Task 6
```

---

### Task 1: Core `lore` skill — the resolution ladder and the git rule

**Files:**
- Modify: `skills/lore/SKILL.md` — the `## Finding the lore` section (currently lines 8-12) and the `## Git` section (currently the last section)

**Interfaces:**
- Produces: the authoritative `## Finding the lore` ladder and `## Git` rule that Tasks 2, 3, and 4 defer to by name. Tasks 2-4 must not restate these rules in different words.
- Consumes: nothing.

- [ ] **Step 1: Write the failing assertion script**

Create `/tmp/lore-check/task1.py`:

```python
import re, sys, pathlib
t = pathlib.Path('skills/lore/SKILL.md').read_text(encoding='utf-8')

required = [
    '## Finding the lore',
    'first match wins',
    "A path in the user's message",
    'cwd is a lore',
    'lore:start',
    'No lore found.',
    'never fall through',
    'git -C "$LORE" rev-parse --git-dir',
    'skip the commit',
]
forbidden = [
    'lore.json',
    'run `/lore:lore-init` and stop',
]
missing = [n for n in required if n not in t]
present = [n for n in forbidden if n in t]
if missing:
    print('MISSING:', missing); sys.exit(1)
if present:
    print('STILL PRESENT:', present); sys.exit(1)
fm = re.match(r'^---\n(.*?)\n---\n', t, re.S)
if not fm or 'name: lore' not in fm.group(1):
    print('FRONTMATTER BROKEN'); sys.exit(1)
print('TASK1_OK')
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `mkdir -p /tmp/lore-check && python3 /tmp/lore-check/task1.py`
Expected: FAIL, printing `MISSING: [...]` and listing `## Finding the lore` content that does not exist yet, exit code 1.

- [ ] **Step 3: Replace the "Finding the lore" section**

In `skills/lore/SKILL.md`, replace the whole `## Finding the lore` section (from the heading down to, but not including, `## Folder contract`) with:

````markdown
## Finding the lore

Resolve `$LORE` with these rungs, first match wins. Never guess, never scan the disk, never fall back to `~/lore`.

1. **A path in the user's message** — e.g. `/lore:lore-ingest ~/wikis/hardware`.
2. **cwd is a lore** — `[ -f ./index.md ] && [ -d ./raw ] && [ -d ./wiki ]`. Use cwd.
3. **The project's link block** — the `<!-- lore:start -->` block in the project's `CLAUDE.md` names a path. It is usually already in context; otherwise read `./CLAUDE.md`.
4. **Nothing matched** — STOP. Tell the user, verbatim:

   > No lore found. `cd` into a lore, pass its path (`/lore:lore-ingest <path>`), or run `/lore:lore-link <path>` in this project.

Rung 2 needs all three of `index.md`, `raw/`, and `wiki/` — it fires on whatever directory the user happens to be in, and a lone `index.md` is a common filename. Rungs 1 and 3 need only `index.md`, because the path was named on purpose and the stricter test would reject a lore whose `raw/` the user has temporarily emptied.

If a rung matches but the path has no `index.md`, STOP and name the bad path — **never fall through** to the next rung. A stale `lore:start` block must be reported (suggest re-running `/lore:lore-link <path>`), not silently bypassed.

Rungs 2 and 3 cannot both match: a lore's own `CLAUDE.md` is its schema and never carries a `lore:start` marker.

Then read `<lore>/CLAUDE.md` — the lore's schema. The rules below are the defaults every new lore is seeded with; where the lore's CLAUDE.md differs (the user evolves it over time), the lore's CLAUDE.md wins.
````

- [ ] **Step 4: Replace the Git section**

Replace the whole `## Git` section at the end of `skills/lore/SKILL.md` with:

````markdown
## Git

Every mutation of the lore (init, ingest, lint fix, answer promotion) ends with `git add -A && git commit` inside the lore repo, message prefixed `init:`, `ingest:`, `lint:`, or `answer:`.

A lore created with `/lore:lore-init --no-git` is not a repository. Test before committing:

```bash
git -C "$LORE" rev-parse --git-dir >/dev/null 2>&1
```

If that fails: do the work, **skip the commit**, and state in the report that changes were written without a commit. Never error, and never offer to run `git init` — the user opted out deliberately.
````

- [ ] **Step 5: Run the assertion script to verify it passes**

Run: `python3 /tmp/lore-check/task1.py`
Expected: `TASK1_OK`, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add skills/lore/SKILL.md
git commit -m "feat(lore): resolve lore by ladder, not global config"
```

---

### Task 2: `/lore:lore-init` — no config write, `--no-git`, no re-point branch

**Files:**
- Modify: `skills/lore-init/SKILL.md` — frontmatter description, title line, steps 2, 4, 5, 6
- Modify: `skills/lore-init/templates/CLAUDE.md` — the `## Git` section (currently lines 57-59)

**Interfaces:**
- Consumes: the `## Git` rule from `skills/lore/SKILL.md` (Task 1) — the template's git section must agree with it.
- Produces: a scaffolded lore with no external config. Tasks 3, 4, and 6 assume a lore scaffolded exactly this way, and that `--no-git` produces a lore with no `.git` directory.

- [ ] **Step 1: Write the failing assertion script**

Create `/tmp/lore-check/task2.py`:

```python
import sys, pathlib
s = pathlib.Path('skills/lore-init/SKILL.md').read_text(encoding='utf-8')
tpl = pathlib.Path('skills/lore-init/templates/CLAUDE.md').read_text(encoding='utf-8')

required_skill = [
    '/lore:lore-init [path] [--no-git]',
    'already a lore, nothing to do',
    'NO_GIT',
    'has no schema layer',
]
forbidden_skill = [
    'lore.json',
    're-pointed config',
    'Record location',
]
required_tpl = ['--no-git', 'skip the commit']

missing = [n for n in required_skill if n not in s] + [n for n in required_tpl if n not in tpl]
present = [n for n in forbidden_skill if n in s]
if 'lore.json' in tpl:
    present.append('lore.json in templates/CLAUDE.md')
if missing:
    print('MISSING:', missing); sys.exit(1)
if present:
    print('STILL PRESENT:', present); sys.exit(1)
print('TASK2_OK')
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 /tmp/lore-check/task2.py`
Expected: FAIL — `STILL PRESENT: ['lore.json', 're-pointed config', 'Record location']`, exit code 1.

- [ ] **Step 3: Update the frontmatter and title**

In `skills/lore-init/SKILL.md`, replace the `description:` line with:

```yaml
description: Use when the user runs /lore:lore-init [path] [--no-git] — create the lore folder, scaffold its layout with its CLAUDE.md schema, and git-init it unless --no-git. Writes nothing outside the lore folder.
```

Replace the title line `# /lore:lore-init [path]` with:

```markdown
# /lore:lore-init [path] [--no-git]
```

- [ ] **Step 4: Replace steps 1 and 2**

Replace step 1 and step 2 with:

````markdown
1. Resolve `LORE` = the path argument if given, else `$HOME/lore`. Expand to an absolute path. Set `NO_GIT=1` if the user passed `--no-git`, else `NO_GIT=0`.
2. **Already a lore?** If `$LORE/index.md` exists: touch nothing. Report "already a lore, nothing to do" with the path, remind the user that a lore needs no config — `cd` into it, or run `/lore:lore-link <path>` in a project — and stop.
````

- [ ] **Step 5: Make the scaffold's git init conditional**

In step 4's bash block, replace the final `cd "$LORE" && git init -q && ...` line with:

```bash
if [ "$NO_GIT" = "0" ]; then
  cd "$LORE" && git init -q && git add -A && git commit -q -m "init: lore scaffold"
fi
```

Immediately after the bash block's existing `CLAUDE_PLUGIN_ROOT` fallback paragraph, add:

```markdown
With `--no-git` the lore has no history and no undo. Say so once in the report: ingest and lint will write pages without committing.
```

- [ ] **Step 6: Delete the config step and fix the report**

Delete step 5 in its entirety — the `## 5. Record location` heading, its prose, and its bash block (`mkdir -p ~/.claude` … `> ~/.claude/lore.json`). Renumber the old step 6 to step 5 and replace its text with:

````markdown
5. Report: the lore path, what was created, whether git was initialised, and next steps — drop files into `raw/`, then either `cd` into the lore and run `/lore:lore-ingest`, or run `/lore:lore-link <path>` inside a project. Nothing was written outside the lore folder.
````

- [ ] **Step 7: Update the template's Git section**

In `skills/lore-init/templates/CLAUDE.md`, replace the `## Git` section body with:

````markdown
Every mutation (init, ingest, lint fix, answer promotion) ends with a commit here, message prefixed `init:`, `ingest:`, `lint:`, or `answer:`.

If this lore was created with `--no-git` it is not a repository: do the work, skip the commit, and say so in the report. Never run `git init` on it.
````

- [ ] **Step 8: Run the assertion script to verify it passes**

Run: `python3 /tmp/lore-check/task2.py`
Expected: `TASK2_OK`, exit code 0.

- [ ] **Step 9: Verify the scaffold both ways, live**

Run:
```bash
rm -rf /tmp/t-git /tmp/t-nogit
# simulate the skill's scaffold, git branch
mkdir -p /tmp/t-git/raw /tmp/t-git/wiki && touch /tmp/t-git/index.md /tmp/t-git/log.md
cd /tmp/t-git && git init -q && git add -A && git commit -q -m "init: lore scaffold" --allow-empty
git -C /tmp/t-git rev-parse --git-dir >/dev/null 2>&1 && echo GIT_BRANCH_OK
# no-git branch
mkdir -p /tmp/t-nogit/raw /tmp/t-nogit/wiki && touch /tmp/t-nogit/index.md /tmp/t-nogit/log.md
git -C /tmp/t-nogit rev-parse --git-dir >/dev/null 2>&1 || echo NOGIT_BRANCH_OK
rm -rf /tmp/t-git /tmp/t-nogit
```
Expected: `GIT_BRANCH_OK` and `NOGIT_BRANCH_OK`. This only proves the two scaffold branches are well-formed; that `/lore:lore-init` itself writes no config is proven live in Task 6, Scenario 6.

- [ ] **Step 10: Commit**

```bash
cd ~/Project/lore
git add skills/lore-init/SKILL.md skills/lore-init/templates/CLAUDE.md
git commit -m "feat(lore-init): drop config write, add --no-git"
```

---

### Task 3: `/lore:lore-link` — path becomes a required argument

**Files:**
- Modify: `skills/lore-link/SKILL.md` — frontmatter description, title line, steps 1-4 renumbering

**Interfaces:**
- Consumes: the ladder from `skills/lore/SKILL.md` (Task 1) — rung 3 reads the block this skill writes, so the `<!-- lore:start -->` / `<!-- lore:end -->` marker names and the "This project is linked to a knowledge base at `<LORE_PATH>`" line must not change.
- Produces: the `lore:start` block that rung 3 resolves. Task 6 asserts a no-argument invocation leaves the project `CLAUDE.md` byte-identical.

- [ ] **Step 1: Write the failing assertion script**

Create `/tmp/lore-check/task3.py`:

```python
import sys, pathlib
t = pathlib.Path('skills/lore-link/SKILL.md').read_text(encoding='utf-8')
required = [
    '# /lore:lore-link <path>',
    'Usage: `/lore:lore-link <path-to-lore>`',
    'is required',
    '"<path>/index.md"',
    'do not modify',
    '<!-- lore:start -->',
    '<!-- lore:end -->',
]
forbidden = ['lore.json']
missing = [n for n in required if n not in t]
present = [n for n in forbidden if n in t]
if missing:
    print('MISSING:', missing); sys.exit(1)
if present:
    print('STILL PRESENT:', present); sys.exit(1)
print('TASK3_OK')
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 /tmp/lore-check/task3.py`
Expected: FAIL — `MISSING` lists the usage and validation strings, and `STILL PRESENT: ['lore.json']`, exit code 1.

- [ ] **Step 3: Update the frontmatter and title**

Replace the `description:` line with:

```yaml
description: Use when the user runs /lore:lore-link <path> — append a pointer block to that project's CLAUDE.md so Claude consults the lore at <path> for domain questions there.
```

Replace the title line `# /lore:lore-link` with:

```markdown
# /lore:lore-link <path>
```

- [ ] **Step 4: Replace step 1 with the argument requirement and validation**

Replace the current step 1 (`Read the lore path from ~/.claude/lore.json ...`) with these two steps, and renumber the existing steps 2, 3, 4 to 3, 4, 5:

````markdown
1. `<path>` is required — the lore to link this project to. If the user gave no path, STOP with:

   > Usage: `/lore:lore-link <path-to-lore>` — e.g. `/lore:lore-link ~/lore`

   Do not infer it from cwd and do not guess. Writing the wrong path here silently mis-routes every later question in this project.

2. Expand `<path>` to an absolute path and validate it is a lore: `[ -f "<path>/index.md" ]`. If not, STOP and name the path — **do not modify** the project's `CLAUDE.md`.
````

- [ ] **Step 5: Run the assertion script to verify it passes**

Run: `python3 /tmp/lore-check/task3.py`
Expected: `TASK3_OK`, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add skills/lore-link/SKILL.md
git commit -m "feat(lore-link): require the lore path as an argument"
```

---

### Task 4: `/lore:lore-ingest` and `/lore:lore-lint` — ladder header and commit guard

**Files:**
- Modify: `skills/lore-ingest/SKILL.md` — the header line (line 8) and the `## 4. Commit and report` section
- Modify: `skills/lore-lint/SKILL.md` — the header line (line 8) and the first bullet of `## Output`

**Interfaces:**
- Consumes: the ladder and git rule from `skills/lore/SKILL.md` (Task 1); the repo test string must match Task 1's verbatim.
- Produces: nothing later tasks depend on structurally. Task 6 asserts both commands hard-fail from an unrelated directory and both write-without-committing in a `--no-git` lore.

- [ ] **Step 1: Write the failing assertion script**

Create `/tmp/lore-check/task4.py`:

```python
import sys, pathlib
files = ['skills/lore-ingest/SKILL.md', 'skills/lore-lint/SKILL.md']
bad = []
for f in files:
    t = pathlib.Path(f).read_text(encoding='utf-8')
    if 'lore.json' in t:
        bad.append((f, 'lore.json still present'))
    for n in ['Finding the lore', 'git -C "$LORE" rev-parse --git-dir', 'without a commit']:
        if n not in t:
            bad.append((f, 'missing: ' + n))
if bad:
    print('FAIL:', bad); sys.exit(1)
print('TASK4_OK')
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 /tmp/lore-check/task4.py`
Expected: FAIL listing `lore.json still present` and the three missing strings for both files, exit code 1.

- [ ] **Step 3: Replace the header line in both skills**

In `skills/lore-ingest/SKILL.md` and `skills/lore-lint/SKILL.md`, replace the line beginning `Follow the \`lore\` skill for all conventions.` with this identical line in both:

```markdown
Follow the `lore` skill for all conventions — including its **Finding the lore** ladder, which resolves `$LORE` (a path in the user's message, else cwd if it is a lore, else the project's `lore:start` block, else hard fail). Then read `$LORE/CLAUDE.md` — where it differs from these defaults, it wins.
```

- [ ] **Step 4: Guard the commit in `lore-ingest`**

In `skills/lore-ingest/SKILL.md` § `## 4. Commit and report`, replace the bash block with:

```bash
if git -C "$LORE" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$LORE" add -A && git -C "$LORE" commit -m "ingest: <filenames>"
else
  echo "NOT_A_GIT_REPO"
fi
```

and append to that section's report sentence:

```markdown
If the lore is not a git repository (`--no-git`), say plainly that the pages were written without a commit — there is no undo for this ingest.
```

- [ ] **Step 5: Guard the commit in `lore-lint`**

In `skills/lore-lint/SKILL.md` § `## Output`, replace the commit bullet with:

````markdown
- Then commit, if the lore is a git repository:

  ```bash
  if git -C "$LORE" rev-parse --git-dir >/dev/null 2>&1; then
    git -C "$LORE" add -A && git -C "$LORE" commit -m "lint: <summary>"
  else
    echo "NOT_A_GIT_REPO"
  fi
  ```

  When it is a repo, always commit — the log entry is itself a change, so a lint run is never a clean tree. When it is not, report that fixes were written without a commit.
````

- [ ] **Step 6: Run the assertion script to verify it passes**

Run: `python3 /tmp/lore-check/task4.py`
Expected: `TASK4_OK`, exit code 0.

- [ ] **Step 7: Verify the two header lines are byte-identical**

Run:
```bash
diff <(grep -F 'Finding the lore' skills/lore-ingest/SKILL.md) \
     <(grep -F 'Finding the lore' skills/lore-lint/SKILL.md) && echo HEADERS_IDENTICAL
```
Expected: `HEADERS_IDENTICAL`.

- [ ] **Step 8: Commit**

```bash
git add skills/lore-ingest/SKILL.md skills/lore-lint/SKILL.md
git commit -m "feat(ingest,lint): use the ladder, guard the commit"
```

---

### Task 5: README and version bump

**Files:**
- Modify: `README.md` — the `## Use` block (line 77) and the config paragraph (lines 85-88)
- Modify: `.claude-plugin/plugin.json` — `version`

**Interfaces:**
- Consumes: the final command surface from Tasks 2 and 3 — `/lore:lore-init [path] [--no-git]` and `/lore:lore-link <path>`.
- Produces: user-facing documentation. Task 6 cites it when recording the acceptance pass.

- [ ] **Step 1: Write the failing assertion script**

Create `/tmp/lore-check/task5.py`:

```python
import json, sys, pathlib
r = pathlib.Path('README.md').read_text(encoding='utf-8')
required = ['--no-git', '/lore:lore-link <path>', 'self-describing', 'as many separate lores']
missing = [n for n in required if n not in r]
if 'lore.json' in r:
    missing.append('lore.json still referenced')
if missing:
    print('FAIL:', missing); sys.exit(1)
v = json.loads(pathlib.Path('.claude-plugin/plugin.json').read_text(encoding='utf-8'))['version']
if v != '0.2.0':
    print('VERSION NOT BUMPED:', v); sys.exit(1)
print('TASK5_OK')
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 /tmp/lore-check/task5.py`
Expected: FAIL — `FAIL: ['--no-git', '/lore:lore-link <path>', 'self-describing', 'as many separate lores', 'lore.json still referenced']`, exit code 1.

- [ ] **Step 3: Update the Use block**

Replace the `## Use` code block with:

```
    /lore:lore-init [path] [--no-git]   # once — creates the lore (default ~/lore), git-inits it
    # drop files into <lore>/raw/   (PDF, images, xlsx/csv, md, txt, saved HTML)
    cd <lore> && /lore:lore-ingest      # distill new raw files into the wiki
    /lore:lore-link <path>              # once per project — point it at the lore
    /lore:lore-lint                     # periodic health check (after ~5 ingests or monthly)
```

- [ ] **Step 4: Replace the config paragraph**

Replace the paragraph beginning "The lore's location is stored in `~/.claude/lore.json`." with:

```markdown
A lore is self-describing — nothing about it is stored anywhere else. Commands
find it in this order: a path you name (`/lore:lore-ingest ~/wikis/hardware`),
the folder you are standing in, or the `lore:start` block that
`/lore:lore-link` wrote into a project's `CLAUDE.md`. If none of those apply the
command stops and says so rather than guessing at your notes. Moved a lore?
Re-run `/lore:lore-link <new-path>` in the projects that point at it.

Because nothing is global, you can keep as many separate lores as you like — one
per domain, per client, per machine.

`/lore:lore-init --no-git` skips `git init`, for a lore that lives inside a
folder already synced by Obsidian Sync, iCloud, or Dropbox, or nested in another
repo. Ingest and lint then write pages without committing and tell you so — you
lose the undo, so prefer the default.
```

- [ ] **Step 5: Bump the version**

In `.claude-plugin/plugin.json`, change `"version": "0.1.0"` to `"version": "0.2.0"`. This is a breaking change: `/lore:lore-link` gained a required argument.

- [ ] **Step 6: Run the assertion script to verify it passes**

Run: `python3 /tmp/lore-check/task5.py`
Expected: `TASK5_OK`, exit code 0.

- [ ] **Step 7: Verify no skill or doc still instructs reading the config**

Run:
```bash
grep -rn 'lore\.json' README.md skills/ .claude-plugin/ && echo "LEAK FOUND" || echo NO_CONFIG_LEAK
```
Expected: `NO_CONFIG_LEAK` — zero occurrences, no exceptions. (`docs/` is excluded on purpose: the historical spec and plan keep their references, and this plan's own Task 2 Step 6 names the file only to say what to delete.)

- [ ] **Step 8: Commit**

```bash
git add README.md .claude-plugin/plugin.json
git commit -m "docs: self-describing lores, --no-git; bump to 0.2.0"
```

---

### Task 6: Live acceptance pass

**Files:**
- Create: `docs/verification/2026-08-22-lore-no-global-config-acceptance.md`

**Interfaces:**
- Consumes: all five skills as edited in Tasks 1-4 and the README from Task 5.
- Produces: the recorded transcript that closes the spec's §7. This is the only task that proves the skills *behave*; Tasks 1-5 only prove the prose *says* the right thing.

**Method:** these scenarios must be run by actually invoking the slash commands in a Claude Code session with the plugin reloaded — not by simulating them in bash. Record each scenario's command, the agent's response, and the asserted filesystem state in the transcript file.

- [ ] **Step 1: Back up any real config and reload the plugin**

```bash
cp ~/.claude/lore.json /tmp/lore.json.bak 2>/dev/null && echo BACKED_UP || echo NO_REAL_CONFIG
claude plugin marketplace update lore-marketplace
```
Then start a new Claude Code session — skills load at startup.

- [ ] **Step 2: Scenario 1 — two lores side by side**

```bash
rm -rf /tmp/lore-a /tmp/lore-b /tmp/proj-a
```
Run `/lore:lore-init /tmp/lore-a` and `/lore:lore-init /tmp/lore-b`. Drop a distinct small `.md` file into each `raw/`. `cd /tmp/lore-a` and run `/lore:lore-ingest` (rung 2); then from any directory run `/lore:lore-ingest /tmp/lore-b` (rung 1).
Assert:
```bash
grep -c ingest /tmp/lore-a/log.md /tmp/lore-b/log.md
grep -q "$(basename $(ls /tmp/lore-b/raw))" /tmp/lore-a/log.md && echo CROSS_CONTAMINATION || echo ISOLATED_OK
```
Expected: one `ingest` entry each, and `ISOLATED_OK`.

- [ ] **Step 3: Scenario 2 — rung 4 hard fail**

```bash
mkdir -p /tmp/nowhere && cd /tmp/nowhere
```
Run `/lore:lore-ingest`.
Expected: the agent stops and prints the rung-4 message. Assert nothing was created:
```bash
[ -z "$(ls -A /tmp/nowhere)" ] && echo NOTHING_CREATED
```

- [ ] **Step 4: Scenario 3 — stale link block does not fall through**

```bash
mkdir -p /tmp/proj-a && cd /tmp/proj-a && git init -q
```
Run `/lore:lore-link /tmp/lore-a`, then `rm -rf /tmp/lore-a`, then `/lore:lore-ingest` from `/tmp/proj-a`.
Expected: hard failure naming `/tmp/lore-a` and suggesting `/lore:lore-link` — **not** a fall-through to cwd and **not** a rung-4 generic message.

- [ ] **Step 5: Scenario 4 — lore-link argument guards**

From `/tmp/proj-a`:
```bash
md5sum /tmp/proj-a/CLAUDE.md > /tmp/before.md5
```
Run `/lore:lore-link` with no argument, then `/lore:lore-link /tmp/not-a-lore`.
Expected: usage message, then a not-a-lore failure. Assert:
```bash
md5sum -c /tmp/before.md5 && echo CLAUDE_MD_UNTOUCHED
```

- [ ] **Step 6: Scenario 5 — `--no-git` end to end**

```bash
rm -rf /tmp/lore-ng
```
Run `/lore:lore-init /tmp/lore-ng --no-git`, drop a small `.md` into `/tmp/lore-ng/raw/`, `cd /tmp/lore-ng`, run `/lore:lore-ingest`.
Expected: pages written, no commit attempted, and the report says so. Assert:
```bash
[ ! -d /tmp/lore-ng/.git ] && [ -n "$(ls -A /tmp/lore-ng/wiki)" ] && echo NOGIT_INGEST_OK
```

- [ ] **Step 7: Scenario 6 — a stale config is ignored**

```bash
mkdir -p ~/.claude && echo '{"path": "/tmp/WRONG-LORE"}' > ~/.claude/lore.json
mkdir -p /tmp/nowhere2 && cd /tmp/nowhere2
```
Run `/lore:lore-ingest`.
Expected: the rung-4 hard-fail message. The agent must not mention or resolve `/tmp/WRONG-LORE`.

- [ ] **Step 8: Scenario 7 — init on an existing lore**

```bash
md5sum /tmp/lore-b/index.md /tmp/lore-b/log.md > /tmp/before-b.md5
```
Run `/lore:lore-init /tmp/lore-b`.
Expected: "already a lore, nothing to do". Assert:
```bash
md5sum -c /tmp/before-b.md5 && echo EXISTING_LORE_UNTOUCHED
```

- [ ] **Step 9: Restore the machine and write the transcript**

```bash
[ -f /tmp/lore.json.bak ] && mv /tmp/lore.json.bak ~/.claude/lore.json || rm -f ~/.claude/lore.json
rm -rf /tmp/lore-a /tmp/lore-b /tmp/lore-ng /tmp/proj-a /tmp/nowhere /tmp/nowhere2 /tmp/lore-check
```
Write `docs/verification/2026-08-22-lore-no-global-config-acceptance.md` in the style of `docs/verification/2026-08-21-lore-acceptance-pass.md`: one section per scenario with the command run, the agent's actual response, the assertion output, and a PASS/FAIL verdict. Record any scenario that failed and what was changed to fix it — do not rewrite history to look clean.

- [ ] **Step 10: Commit**

```bash
cd ~/Project/lore
git add docs/verification/2026-08-22-lore-no-global-config-acceptance.md
git commit -m "docs: acceptance pass for self-describing lores"
```

---

## Post-plan (not in scope)

The Obsidian single-knowledge-base layout (one lore, topic subfolders under `wiki/`, index split into `index.md` + `index/<topic>.md`) is spec §8's known limitation and needs its own brainstorm. Removing global config neither delivers nor blocks it.
