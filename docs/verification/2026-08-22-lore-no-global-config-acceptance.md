# Acceptance pass — self-describing lores (no global config)

Date: 2026-08-22
Branch: `worktree-lore-no-global-config`
Skills exercised live: `skills/lore`, `skills/lore-init`, `skills/lore-ingest`,
`skills/lore-link` as of `afd96aa`, plus `skills/lore-init/templates/CLAUDE.md`.
`skills/lore-lint` was verified statically only — no scenario below runs it; the
one thing checked was the text of its commit guard.

Closes spec §7. Tasks 1-5 asserted over the *text* of the skills; this is the only
pass that exercises what the skills make an agent *do*.

---

## Method — read this before trusting any verdict below

**These scenarios were executed by literally following each `SKILL.md`'s numbered
procedure as the executing agent. They were NOT executed by Claude Code
slash-command dispatch with the plugin loaded.**

For every scenario the relevant `skills/<name>/SKILL.md` was re-read fresh from
this worktree at the moment the scenario ran, its steps were followed in order,
and `$LORE` was resolved by walking the `lore` skill's **Finding the lore** ladder
rung by rung rather than by jumping to the known answer. Every command below was
really run and every block of output is the real terminal output.

Consequently this pass proves:

- the instructions are correct, unambiguous, and followable;
- the ladder resolves as specified, including its hard failures;
- the filesystem end state is what the spec requires.

It does **not** prove:

- that Claude Code's skill-dispatch layer selects the right skill for
  `/lore:lore-init`, `/lore:lore-ingest`, `/lore:lore-link`, `/lore:lore-lint`;
- that the frontmatter `description:` fields trigger on the right user phrasings;
- that the packaged plugin (`.claude-plugin/`) loads these five skills at session
  startup.

A future interactive confirmation run would add exactly those three things: open a
real Claude Code session with this branch installed as the plugin, type the four
slash commands against a scratch lore, and confirm the same end states. That run
is cheap and should be done once before release; nothing in this pass substitutes
for it.

### Deviations from the task brief, and why

**Ruling 1 — the brief's Step 1 `claude plugin marketplace update lore-marketplace`
was skipped entirely, and no fresh interactive session was started.** The installed
plugin resolves to `~/.claude/plugins/marketplaces/lore-marketplace/`, a *different
checkout* from this worktree. Reloading it would have exercised the OLD pre-Task-1
skills, i.e. tested the wrong code, while also mutating user-level plugin state
outside the worktree. An interactive session could not be started from here either.
Hence the by-hand execution described above — the same controller ruling and the
same method as `docs/verification/2026-08-21-lore-acceptance-pass.md`.

**Ruling 2 — the real `~/.claude/lore.json` was never read, written, moved, or
deleted, and its existence was never even checked.** The brief's Step 1 backup,
Step 7 bogus-config write, and Step 9 restore/delete were all skipped. Scenario 6
instead ran under a throwaway `HOME=/tmp/fakehome`, with the bogus config placed at
`/tmp/fakehome/.claude/lore.json` so that `~/.claude/lore.json` resolved to it.
This proves what spec §7.6 asks — that a stale config at that path cannot influence
resolution — against a config at the same *relative* path rather than the literal
home path. Since the resolution ladder contains no filesystem lookup of that path
at all (verified by grep inside the scenario), the distinction is immaterial.

**Ruling 3** — Step 10's leading `cd ~/Project/lore` was dropped; all repo git
commands ran inside this worktree.

**Ruling 5** — the brief's `/tmp` paths were used verbatim, plus `/tmp/fakehome`.

**`CLAUDE_PLUGIN_ROOT` is unset in this environment** (`CLAUDE_PLUGIN_ROOT=[]`).
`lore-init`'s scaffold line
`cp "${CLAUDE_PLUGIN_ROOT}/skills/lore-init/templates/CLAUDE.md" …` was run in its
literal form once, observed to fail, and then the skill's own documented fallback
("locate `templates/CLAUDE.md` next to this SKILL.md") was taken, resolving to
`<worktree>/skills/lore-init/templates/CLAUDE.md`. See Scenario 1.

### Two environment facts that shaped execution

1. **`rg` is not on this machine's shell `PATH`** (`which rg` → nothing;
   `/usr/bin/rg` and `/snap/bin/rg` absent). The skills use `rg` for the
   "does a page on this topic already exist?" pre-check and for wikilink scanning.
   Every such step was executed with `grep -ri`, which is equivalent for these
   uses, and the substitution is called out where it occurs. This is an
   environment gap, not a skill defect — ripgrep is a declared dependency in the
   README ("markdown + git + ripgrep"). Claude Code's own Grep tool bundles
   ripgrep; the bare shell does not.
2. **No global git identity is configured.** `lore-init` step 4 anticipates this
   ("If git identity is unset in this environment, set a repo-local one first…").
   The fallback was needed and was taken. See Scenario 1.

---

## Scenario 1 — two lores side by side

**Procedures run:** `skills/lore-init/SKILL.md` twice, then
`skills/lore-ingest/SKILL.md` twice — once resolving via rung 2, once via rung 1.

### 1a. `/lore:lore-init /tmp/lore-a`

Steps 1-3 evaluated, then the step 4 scaffold block run verbatim:

```
### lore-init step 1: resolve LORE and NO_GIT
LORE=/tmp/lore-a  NO_GIT=0

### lore-init step 2: already a lore?
NOT_A_LORE -> continue

### lore-init step 3: non-empty, non-lore folder?
DOES_NOT_EXIST -> continue

### lore-init step 4: template copy, verbatim form (CLAUDE_PLUGIN_ROOT is unset here)
$ cp "${CLAUDE_PLUGIN_ROOT}/skills/lore-init/templates/CLAUDE.md" /tmp/cp-probe.md
cp: cannot stat '/skills/lore-init/templates/CLAUDE.md': No such file or directory
cp exit=1
--- taking the documented fallback: templates/CLAUDE.md next to the SKILL.md
-rw-rw-r-- 1 vboxuser vboxuser 3992 Aug 22 07:09 /home/vboxuser/Project/lore/.claude/worktrees/lore-no-global-config/skills/lore-init/templates/CLAUDE.md

### lore-init step 4: scaffold
Author identity unknown

*** Please tell me who you are.

Run

  git config --global user.email "you@example.com"
  git config --global user.name "Your Name"

to set your account's default identity.
Omit --global to set the identity only in this repository.

fatal: unable to auto-detect email address (got 'vboxuser@dev.(none)')
scaffold exit=128

### result
.git
CLAUDE.md
index.md
log.md
raw
wiki
fatal: your current branch 'master' does not have any commits yet
```

Two documented fallbacks fired on this first run, both of which the skill
predicts and tells the agent how to handle:

- the `${CLAUDE_PLUGIN_ROOT}` copy failed → used `templates/CLAUDE.md` next to the
  SKILL.md, as step 4's follow-up paragraph instructs;
- `git commit` failed for want of an identity → step 4's parenthetical says to set
  a repo-local one. Applied:

```
### skill step 4 parenthetical: git identity is unset in this environment -> set a repo-local one
commit exit=0

### result
.git
CLAUDE.md
index.md
log.md
raw
wiki
99d1dc9 init: lore scaffold
```

Neither is a skill defect — in both cases the agent was told what to do and the
instruction worked. Both are recorded because they are the first thing a real user
on a fresh machine will hit.

### 1b. `/lore:lore-init /tmp/lore-b`

Same procedure, with the template path and the identity step applied up front:

```
### lore-init step 1
LORE=/tmp/lore-b  NO_GIT=0
### lore-init step 2: already a lore?
NOT_A_LORE -> continue
### lore-init step 3: non-empty non-lore?
DOES_NOT_EXIST -> continue
### lore-init step 4: scaffold (template via documented fallback path)
scaffold exit=0
### result
.git
CLAUDE.md
index.md
log.md
raw
wiki
9b11935 init: lore scaffold
```

Then one distinct markdown file was dropped into each inbox:
`/tmp/lore-a/raw/alpha-note.md` (Alpha Widget, AW-100, Northgate Fluidics) and
`/tmp/lore-b/raw/bravo-note.md` (Bravo Relay, BR-7, Eastvale Controls).

### 1c. `cd /tmp/lore-a` → `/lore:lore-ingest` — resolves by **rung 2**

Ladder walked rung by rung:

```
cwd=/tmp/lore-a

### lore skill, Finding the lore — rung 1: a path in the user's message?
user message was: /lore:lore-ingest   (no path) -> NO MATCH

### rung 2: cwd is a lore?  [ -f ./index.md ] && [ -d ./raw ] && [ -d ./wiki ]
MATCH -> LORE=/tmp/lore-a

### rung matched; does $LORE/index.md exist? (the 'matched but not a lore' guard)
yes -> proceed

### read $LORE/CLAUDE.md (the schema)
# Lore — Schema
...

### ingest step 1: find new files
$ find "$LORE/raw" -type f -printf %P\\n
alpha-note.md

### ledger test, anchored, per the skill
alpha-note.md -> NEW
```

The anchored `python3` ledger test from the skill was used, not a substring `rg -F`.
Then step 2 (markdown → read directly), step 3 (index + log), step 4 (commit):

```
### ingest step 2 pre-check (rg unavailable -> grep -ri equivalent)
(no index hit -> create, do not update)
...
### ingest step 4: commit
committed
a690301 ingest: alpha-note.md
99d1dc9 init: lore scaffold
```

Pages written: `wiki/Alpha_Widget.md` (`type: concept`) and
`wiki/Alpha_Widget_Note.md` (`type: source`), each with full frontmatter,
`raw/alpha-note.md` citations on every hard number, and wikilinks to each other.

### 1d. `/lore:lore-ingest /tmp/lore-b` — resolves by **rung 1**

The brief says "from any directory". This was deliberately run **from inside
`/tmp/lore-a`**, where rung 2 would also match — a strictly stronger test that
first-match-wins ordering holds and rung 1 beats rung 2.

```
cwd=/tmp/lore-a   (rung 2 would match here — testing that rung 1 wins)

### rung 1: a path in the user's message?  '/lore:lore-ingest /tmp/lore-b'
MATCH -> LORE=/tmp/lore-b

### rungs 1 and 3 test only for index.md
index.md present -> proceed

### ingest step 1: find new files
bravo-note.md
bravo-note.md -> NEW
...
### step 4: commit
committed
4bd545a ingest: bravo-note.md
9b11935 init: lore scaffold

### cwd lore (/tmp/lore-a) must be untouched by this run:
a690301 ingest: alpha-note.md
99d1dc9 init: lore scaffold
```

`/tmp/lore-a` was clean (`git status --porcelain` printed nothing) and its history
was unchanged — the rung-1 path won and the cwd lore was not written to.

### Assertions

```
$ grep -c ingest /tmp/lore-a/log.md /tmp/lore-b/log.md
/tmp/lore-a/log.md:1
/tmp/lore-b/log.md:1

$ grep -q "$(basename $(ls /tmp/lore-b/raw))" /tmp/lore-a/log.md && echo CROSS_CONTAMINATION || echo ISOLATED_OK
ISOLATED_OK

$ grep -q "$(basename $(ls /tmp/lore-a/raw))" /tmp/lore-b/log.md && echo CROSS_CONTAMINATION || echo ISOLATED_OK   # reverse direction
ISOLATED_OK
```

(The reverse-direction check is an addition; the brief only asks for one direction.)

**Verdict: PASS.** One `ingest` entry each, no cross-contamination in either
direction, and rung 1 correctly outranked a matching rung 2.

---

## Scenario 2 — rung 4 hard fail

**Procedure run:** `skills/lore-ingest/SKILL.md` → `skills/lore/SKILL.md`
**Finding the lore**, from an empty `/tmp/nowhere`.

```
cwd=/tmp/nowhere

### rung 1: a path in the user's message?  '/lore:lore-ingest' (bare) -> NO MATCH

### rung 2: cwd is a lore?
index.md: no
raw/:     no
wiki/:    no
NO MATCH

### rung 3: the project's lore:start block in ./CLAUDE.md
./CLAUDE.md does not exist -> NO MATCH

### rung 4: nothing matched -> STOP
```

Rung 4 says STOP and tell the user, verbatim. As the executing agent, this is the
response given and nothing further was done:

> No lore found. `cd` into a lore, pass its path (`/lore:lore-ingest <path>`), or run `/lore:lore-link <path>` in this project.

Byte-checked against `skills/lore/SKILL.md` line 17. No directory was scanned, no
`~/lore` was guessed at, no lore was created.

### Assertion

```
$ [ -z "$(ls -A /tmp/nowhere)" ] && echo NOTHING_CREATED
NOTHING_CREATED
```

**Verdict: PASS.**

---

## Scenario 3 — a stale link block hard-fails, it does not fall through

**Procedures run:** `skills/lore-link/SKILL.md`, then `skills/lore-ingest/SKILL.md`.

### 3a. `/lore:lore-link /tmp/lore-a` from `/tmp/proj-a`

```
cwd=/tmp/proj-a

===== /lore:lore-link /tmp/lore-a =====
### lore-link step 1: <path> given? -> /tmp/lore-a  (yes)
### lore-link step 2: expand to absolute + validate it is a lore
[ -f "/tmp/lore-a/index.md" ] -> true, is a lore
### lore-link step 3: target ./CLAUDE.md; sanity-check ./.git
./.git present -> yes
./CLAUDE.md exists -> no (create)
### lore-link step 4: idempotency — lore:start already present?
absent -> append block
### lore-link step 5: report — linked /tmp/lore-a; block ADDED
--- /tmp/proj-a/CLAUDE.md ---
<!-- lore:start -->
## Lore
This project is linked to a knowledge base at `/tmp/lore-a`.
- For domain/knowledge questions, use the `lore` skill: read `/tmp/lore-a/index.md` first, then rg its wiki/; cite sources.
- Never edit `/tmp/lore-a/raw/`. Wiki edits must follow the lore skill's conventions.
<!-- lore:end -->
```

### 3b. Break the link, then `/lore:lore-ingest` from `/tmp/proj-a`

```
===== rm -rf /tmp/lore-a =====
ls: cannot access '/tmp/lore-a': No such file or directory

===== /lore:lore-ingest  (from /tmp/proj-a) =====
### rung 1: path in user's message? bare command -> NO MATCH
### rung 2: cwd is a lore?
index.md: no
raw/:     no
wiki/:    no
-> NO MATCH
### rung 3: the project's lore:start block
3:This project is linked to a knowledge base at `/tmp/lore-a`.
-> MATCH, names /tmp/lore-a
### rung matched — does it have index.md?  (rungs 1 and 3 test only index.md)
[ -f /tmp/lore-a/index.md ] -> false
-> STOP and name the bad path; never fall through to rung 4 or to cwd
```

`skills/lore/SKILL.md` line 21: "If a rung matches but the path has no `index.md`,
STOP and name the bad path — **never fall through** to the next rung. A stale
`lore:start` block must be reported (suggest re-running `/lore:lore-link <path>`)."
As the executing agent, this is the response given:

> The `lore:start` block in `/tmp/proj-a/CLAUDE.md` points at `/tmp/lore-a`, but there is no `index.md` there — that path is not a lore. Stopping rather than guessing. Re-run `/lore:lore-link <path>` in this project with the correct lore path.

It names `/tmp/lore-a`; it is **not** the generic rung-4 message; and it did **not**
fall through to cwd.

### Assertion

```
### assertion: nothing was written into /tmp/proj-a beyond CLAUDE.md and .git
.git
CLAUDE.md
```

**Verdict: PASS.**

---

## Scenario 4 — `lore-link` argument guards

**Procedure run:** `skills/lore-link/SKILL.md`, twice, from `/tmp/proj-a`
(depends on Scenario 3 having written `/tmp/proj-a/CLAUDE.md`).

```
$ md5sum /tmp/proj-a/CLAUDE.md > /tmp/before.md5
89ba22fb6f26db944df90635514c0c32  /tmp/proj-a/CLAUDE.md

===== /lore:lore-link   (no argument) =====
### lore-link step 1: <path> is required. The user gave none -> STOP with the usage message.
    (do not infer from cwd, do not guess; steps 2-5 are never reached, so ./CLAUDE.md is not opened)

===== /lore:lore-link /tmp/not-a-lore =====
### lore-link step 1: <path> given -> /tmp/not-a-lore
### lore-link step 2: expand to absolute, validate it is a lore
[ -f "/tmp/not-a-lore/index.md" ] -> false
-> STOP and name the path; DO NOT modify the project's CLAUDE.md (step 3 never reached)
```

Agent responses, taken verbatim from the skill where it specifies them:

1. no argument →

   > Usage: `/lore:lore-link <path-to-lore>` — e.g. `/lore:lore-link ~/lore`

2. `/tmp/not-a-lore` →

   > `/tmp/not-a-lore` is not a lore — it has no `index.md`. Not modifying this project's `CLAUDE.md`. Pass the path of an existing lore, or create one with `/lore:lore-init /tmp/not-a-lore`.

Note that the no-argument case stops at step 1, so the project's `CLAUDE.md` is
never even opened, and the not-a-lore case stops at step 2, before step 3 names a
target file.

### Assertion

```
$ md5sum -c /tmp/before.md5 && echo CLAUDE_MD_UNTOUCHED
/tmp/proj-a/CLAUDE.md: OK
CLAUDE_MD_UNTOUCHED

### and the file still contains exactly one lore:start block, still naming /tmp/lore-a
1
3:This project is linked to a knowledge base at `/tmp/lore-a`.
```

**Verdict: PASS.**

---

## Scenario 5 — `--no-git` end to end

**Procedures run:** `skills/lore-init/SKILL.md` with `--no-git`, then
`skills/lore-ingest/SKILL.md` from inside the resulting lore.

### 5a. `/lore:lore-init /tmp/lore-ng --no-git`

```
### step 1
LORE=/tmp/lore-ng  NO_GIT=1
### step 2: already a lore?
NOT_A_LORE -> continue
### step 3: non-empty non-lore?
DOES_NOT_EXIST -> continue
### step 4: scaffold (template via the documented fallback path; CLAUDE_PLUGIN_ROOT unset)
NO_GIT=1 -> git init skipped
### step 5: report
CLAUDE.md
index.md
log.md
raw
wiki
.git present? no (as intended)
```

Per step 4's closing line, the report said once: this lore has no history and no
undo; ingest and lint will write pages without committing.

### 5b. `cd /tmp/lore-ng` → `/lore:lore-ingest`

```
cwd=/tmp/lore-ng
===== /lore:lore-ingest =====
### rung 1: no path in the message -> NO MATCH
### rung 2: cwd is a lore?
MATCH -> LORE=/tmp/lore-ng

### step 1: find new files
charlie-note.md
charlie-note.md -> NEW
...
### step 4: commit — guarded
NOT_A_GIT_REPO
```

The guard `git -C "$LORE" rev-parse --git-dir` returned non-zero, the commit was
skipped, no error was raised, and — per the skill's closing line and the global
constraint — **`git init` was never offered**. The agent report said plainly: pages
were written without a commit; there is no undo for this ingest.

### Assertion

```
$ [ ! -d /tmp/lore-ng/.git ] && [ -n "$(ls -A /tmp/lore-ng/wiki)" ] && echo NOGIT_INGEST_OK
NOGIT_INGEST_OK

CLAUDE.md
index.md
log.md
raw
wiki
Charlie_Sensor.md
Charlie_Sensor_Note.md
```

**Verdict: PASS.**

---

## Scenario 6 — a stale global config is ignored

**Ruling 2 applies in full here.** The real `~/.claude/lore.json` was never read,
written, moved, or deleted, and its existence was never checked. This scenario ran
under a throwaway `HOME=/tmp/fakehome`, so that `~/.claude/lore.json` resolved to
`/tmp/fakehome/.claude/lore.json`. That proves spec §7.6 against a config at the
same *relative* path rather than the literal home path — which is sufficient,
because the grep inside the scenario shows the plugin contains no reference to that
filename at all, at any path.

**Procedure run:** `skills/lore-ingest/SKILL.md` → the ladder, from `/tmp/nowhere2`.

```
cwd=/tmp/nowhere2
HOME=/tmp/fakehome
stale config at ~/.claude/lore.json: {"path": "/tmp/WRONG-LORE"}

===== /lore:lore-ingest =====
### The ladder in skills/lore/SKILL.md has exactly four rungs. Grep the whole plugin
### for any config-file rung before walking it:
$ grep -rn "lore.json" <worktree>/skills <worktree>/README.md <worktree>/.claude-plugin
grep exit=1  (1 = no matches anywhere)

### rung 1: path in the user's message? bare command -> NO MATCH
### rung 2: cwd is a lore?
index.md: no
raw/:     no
wiki/:    no
-> NO MATCH
### rung 3: ./CLAUDE.md lore:start block?
./CLAUDE.md does not exist -> NO MATCH
### rung 4: nothing matched -> STOP with the verbatim message.
    There is no rung that reads ~/.claude/lore.json, so /tmp/WRONG-LORE is never consulted.
```

Agent response — again the rung-4 message, verbatim, with no mention of
`/tmp/WRONG-LORE`:

> No lore found. `cd` into a lore, pass its path (`/lore:lore-ingest <path>`), or run `/lore:lore-link <path>` in this project.

### Assertions

```
/tmp/WRONG-LORE exists? no — never created or resolved
$ [ -z "$(ls -A /tmp/nowhere2)" ] && echo NOTHING_CREATED
NOTHING_CREATED
stale config still untouched: {"path": "/tmp/WRONG-LORE"}
```

The `grep -rn "lore.json"` over `skills/`, `README.md` and `.claude-plugin/`
returning exit 1 with no matches is the structural proof behind the behavioural
one: the global config cannot influence resolution because nothing in the plugin
names it.

**Verdict: PASS.**

---

## Scenario 7 — `lore-init` on an existing lore

**Procedure run:** `skills/lore-init/SKILL.md` against `/tmp/lore-b`.

```
$ md5sum /tmp/lore-b/index.md /tmp/lore-b/log.md > /tmp/before-b.md5
23b9d75aced5211aa1b74b9a35cada58  /tmp/lore-b/index.md
fb2d07e3c5a22b6ff1ae66051215e76f  /tmp/lore-b/log.md
git HEAD before: 4bd545a

===== /lore:lore-init /tmp/lore-b =====
### step 1: LORE=/tmp/lore-b, NO_GIT=0
### step 2: already a lore?  [ -f $LORE/index.md ]
true -> touch nothing; report 'already a lore, nothing to do'; STOP
### steps 3-5 are never reached.
```

Agent response, following step 2's required content (path, "nothing to do", and the
reminder that a lore needs no config):

> `/tmp/lore-b` is already a lore — nothing to do. Nothing was written. A lore needs no config: `cd` into it and run `/lore:lore-ingest`, or run `/lore:lore-link /tmp/lore-b` inside a project to point that project at it.

### Assertion

```
$ md5sum -c /tmp/before-b.md5 && echo EXISTING_LORE_UNTOUCHED
/tmp/lore-b/index.md: OK
/tmp/lore-b/log.md: OK
EXISTING_LORE_UNTOUCHED

git HEAD after:  4bd545a
working tree:    0
(0 = clean)
```

HEAD unchanged and the working tree clean, so nothing outside those two files
changed either.

**Verdict: PASS.**

---

## Summary

| # | Scenario | Rung exercised | Verdict |
|---|----------|----------------|---------|
| 1 | Two lores side by side | 2, then 1 (from inside another lore) | PASS |
| 2 | Rung 4 hard fail | 4 | PASS |
| 3 | Stale link block does not fall through | 3 → hard fail naming the path | PASS |
| 4 | `lore-link` argument guards | n/a (steps 1 and 2 guards) | PASS |
| 5 | `--no-git` end to end | 2 | PASS |
| 6 | Stale global config ignored | 4 | PASS |
| 7 | `lore-init` on an existing lore | n/a (step 2 guard) | PASS |

**7/7 PASS. No scenario failed and nothing was changed to make one pass.** No skill
file, the README, or `.claude-plugin/` was modified by this pass; the only repo
change is this transcript.

Global constraints all held:

- no skill file and no line of the README names `~/.claude/lore.json`
  (`grep -rn` → exit 1, no matches);
- the four-rung ladder resolved first-match-wins, including rung 1 beating a
  simultaneously-matching rung 2 (Scenario 1d);
- the rung-4 message appeared verbatim in Scenarios 2 and 6;
- a matched-but-bad rung hard-failed naming the path, and did not fall through
  (Scenario 3);
- rungs 1 and 3 tested only `index.md`; rung 2 required all three of `index.md`,
  `raw/`, `wiki/`;
- git stayed the default; `--no-git` skipped the commit, was not an error, and
  `git init` was never offered (Scenario 5).

---

## One concern found (not a scenario failure, not fixed here)

**The git-repo guard walks up to parent repositories.** All three of `lore`,
`lore-ingest` and `lore-lint` test for a repo with:

```bash
git -C "$LORE" rev-parse --git-dir >/dev/null 2>&1
```

`git rev-parse` searches *upward*. A `--no-git` lore created inside an existing git
repository therefore reads as a repo, and the skill will commit into the parent.
Probed directly (extra check, not in the brief):

```
inner-lore/.git present? no (it is a --no-git lore)
$ git -C /tmp/lore-check/inner-lore rev-parse --git-dir
/tmp/lore-check/.git
exit=0
GUARD SAYS: git repo -> the skill would commit (into the PARENT repo /tmp/lore-check)
```

Impact: a user who runs `/lore:lore-init ./notes --no-git` inside a project
repository gets exactly what `--no-git` promised to avoid — their lore's contents
committed, into the *project's* history rather than their own. It is an edge case
(the documented layout puts a lore in its own folder, and Scenario 5 shows the
guard behaving correctly for a standalone lore), so it did not fail any scenario.

A narrower test would be `[ -d "$LORE/.git" ]`, or
`[ "$(git -C "$LORE" rev-parse --show-toplevel 2>/dev/null)" = "$LORE" ]`, which
also handles worktrees and `.git` files. **Left unfixed deliberately** — this pass
is not permitted to modify skill files; recorded here for the controller to
decide.

### Resolution (added after the pass, in the same commit as the fix)

The controller ruled this a Critical defect and it is now **fixed**. A second half
of the problem was confirmed while fixing it: `lore-ingest` commits with
`git -C "$LORE" add -A`, and `git add -A` stages from the *repository root*
regardless of `-C` — so the old guard did not merely commit into the parent repo,
it swept every unrelated modified file in the user's project into a commit titled
`ingest: <filenames>`, against an explicit `--no-git` opt-out.

The guard is now the narrow root-identity test suggested above, used byte-identically
in all three skills and in the spec:

```bash
[ "$(git -C "$LORE" rev-parse --show-toplevel 2>/dev/null)" = "$LORE" ]
```

Files changed by the fix: `skills/lore/SKILL.md` (the `## Git` section, plus prose
explaining that the lore must be its own repository *root* and that `$LORE` must be
absolute and symlink-resolved for the comparison to hold), `skills/lore-ingest/SKILL.md`
(§4), `skills/lore-lint/SKILL.md` (`## Output`), and
`docs/specs/2026-08-22-lore-no-global-config.md` §4.2 (code block plus a sentence
recording why the narrow test is required).

The scenario verdicts above are unchanged and were not re-run — Scenario 5 exercised
a standalone `--no-git` lore, which both the old and the new guard handle correctly.
The nested-lore case that the old guard got wrong was never covered by a scenario;
it is covered by the fix wave's own guard-behaviour check instead.

---

## Cleanup

Brief Step 9's first line (backup/restore of the real `~/.claude/lore.json`) was
deliberately not run, per Ruling 2.

```
### verification
absent: /tmp/lore-a
absent: /tmp/lore-b
absent: /tmp/lore-ng
absent: /tmp/proj-a
absent: /tmp/nowhere
absent: /tmp/nowhere2
absent: /tmp/lore-check
absent: /tmp/fakehome
absent: /tmp/WRONG-LORE
absent: /tmp/not-a-lore
absent: /tmp/before.md5
absent: /tmp/before-b.md5
absent: /tmp/cp-probe.md
```

Every path the brief allocates is gone, `/tmp/fakehome` included. The real
`~/.claude/` was never touched.
