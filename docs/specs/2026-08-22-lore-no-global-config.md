# lore — Remove Global Config; Self-Describing Lore Folders

Date: 2026-08-22
Status: approved design, pending user review of this spec
Supersedes: §4.1 "Config" row and §5 `/lore-init` config step of `docs/specs/2026-08-21-lore-plugin-design.md`

## 1. Summary

Delete `~/.claude/lore.json`. A lore becomes a fully self-describing folder: nothing about it lives outside it. Skills locate the lore through a four-rung resolution ladder that ends in a hard failure rather than a guess. `/lore:lore-link` takes the lore path as an argument instead of reading it from global config. Git stays the default for new lores, with a `--no-git` opt-out for lores that live inside an already-synced folder.

The motivation is not simplification of the config file itself — it is 40 bytes the user never sees. It is that a single-valued global pointer structurally caps the machine at one lore, and holds state about the lore outside the lore.

## 2. Goals

- No lore state anywhere outside the lore folder.
- Unlimited independent lores on one machine, with no registry, no active-lore concept, and no config.
- Ambiguous resolution fails loudly and tells the user how to disambiguate; it never picks a lore.
- Git remains the default undo/audit layer for every lore, with one documented escape hatch.
- Every skill states step 1 identically, so the five skills cannot drift.

## 3. Non-goals

- No lore registry, no `~/.claude/lores.json`, no "active lore" selection.
- No disk scanning or heuristic search for lores.
- No support for one project linking to multiple lores. A project's `CLAUDE.md` carries exactly one `lore:start` block naming exactly one path.
- No migration tooling. An existing `~/.claude/lore.json` is simply ignored; the user runs `/lore:lore-link <path>` once per project, or `cd`s into the lore.
- This change does not deliver the "several wikis browsable in Obsidian as one knowledge base" goal. See §8.

## 4. Architecture

### 4.1 Resolution ladder

Every lore skill resolves `LORE` with the following rungs, first match wins:

| # | Rung | Test |
|---|---|---|
| 1 | Explicit path in the user's message | The user named a path, e.g. `/lore:lore-ingest ~/wikis/hardware` |
| 2 | cwd is itself a lore | `./index.md`, `./raw/`, and `./wiki/` all exist |
| 3 | The project's link block | `<!-- lore:start -->` block in the project's `CLAUDE.md` names a path, and that path has an `index.md` |
| 4 | Hard fail | Stop. Do not guess, do not scan the disk, do not fall back to `~/lore`. |

Whatever path a rung yields is expanded (`~`) and resolved against cwd to an absolute, symlink-resolved path before it is tested; the §4.2 repository test compares `$LORE` against `git rev-parse --show-toplevel`, which prints a path in exactly that form.

The rung 4 message is fixed:

> No lore found. `cd` into a lore, pass its path (`/lore:lore-ingest <path>`), or run `/lore:lore-link <path>` in this project.

Rungs 2 and 3 cannot both match: a lore's own `CLAUDE.md` is the schema file and never carries a `lore:start` marker. Rung 3 is the common case — the project's `CLAUDE.md` is already loaded in context when the user asks a knowledge question in a linked project.

Two "is a lore" tests are used deliberately. Rung 2 requires all three of `index.md`, `raw/`, and `wiki/`, because it fires on an arbitrary working directory and a lone `index.md` is a common filename. Rungs 1 and 3 require only `index.md`, because the path was named explicitly and the stricter test would reject a lore whose `raw/` or `wiki/` the user has temporarily emptied.

If a rung matches but the resolved path is not a lore (no `index.md`), that is a hard failure naming the bad path — not a fall-through to the next rung. A stale link block must be reported, not silently bypassed.

`~/.claude/lore.json` is never read and never written. It is also never *mentioned* — no skill file may name it, not even to say it is unused: a skill that names a path teaches the agent that the path is part of the system. The correct behaviour when a stale config exists is not "ignore it", it is "have never heard of it". An existing file is therefore inert by construction, and the acceptance pass proves it (§7.6).

### 4.2 Git

`git init` remains part of `/lore:lore-init` unless `--no-git` is passed. The rationale is unchanged from the original design: the user never issues a git command, the skills commit on their behalf, and the commit history is the only mechanism by which an agent's bad distillation — a wrong register value, a merged concept page, a clobbered `## My Take` block — can be reviewed or reverted.

`--no-git` exists for one real conflict: a lore placed inside a folder already synchronised by Obsidian Sync, iCloud, or Dropbox, or nested inside another git repository.

When the lore is not a git repository, `lore-ingest` and `lore-lint` skip their commit step and state in the report that changes were written without a commit. They do not error, and they do not offer to run `git init`.

Repository test, used identically in both skills:

```bash
[ "$(git -C "$LORE" rev-parse --show-toplevel 2>/dev/null)" = "$LORE" ]
```

The test must be this narrow — "is the lore its own repository root", not "is the lore inside a repository". `git rev-parse` searches upward, so the wider test passes for a `--no-git` lore nested in a parent repo, and `git add -A` then stages that parent's whole tree regardless of `-C`, committing the user's unrelated project files against an explicit opt-out.

### 4.3 Command surface

| Command | Change |
|---|---|
| `/lore:lore-init [path] [--no-git]` | No longer writes any config. The "re-point the config to an existing lore" branch is deleted outright — there is no config to re-point. If the target already contains `index.md`, report "already a lore, nothing to do" and exit without touching the folder. The refusal to scaffold over a non-empty foreign folder is unchanged. |
| `/lore:lore-link <path>` | `path` becomes a required argument; it previously came from `lore.json`. No argument is a hard failure with usage text. The target is validated (must contain `index.md`) before the block is written. It also refuses when cwd is itself a lore (the rung-2 three-part test), because a lore's own `CLAUDE.md` is its schema and must never carry a `lore:start` block — this guard is what makes the §4.1 "rungs 2 and 3 cannot both match" invariant a rule rather than a convention. Idempotency and malformed-block handling are unchanged. |
| `/lore:lore-ingest [path]` | Step 1 becomes the ladder. Commit step gains the repo guard. Everything else unchanged. |
| `/lore:lore-lint [path]` | Step 1 becomes the ladder. Commit step gains the repo guard. Everything else unchanged. |
| `lore` (core skill) | "Finding the lore" is replaced by the ladder. The Git section gains the not-a-repo case. |

`/lore:lore-init` reports next steps as: drop files into `raw/`, then either `cd` into the lore and run `/lore:lore-ingest`, or run `/lore:lore-link <path>` inside a project.

## 5. Files changed

| File | Change |
|---|---|
| `skills/lore/SKILL.md` | Replace "Finding the lore" with §4.1. Add the not-a-repo case to the Git section. This is the authoritative copy; the other four defer to it. |
| `skills/lore-init/SKILL.md` | Delete step 5 (config write). Delete step 2's re-point branch, replace with the already-a-lore exit. Add `--no-git`. |
| `skills/lore-link/SKILL.md` | Step 1 becomes the required path argument plus target validation. |
| `skills/lore-ingest/SKILL.md` | Header line (path source) and §4 commit guard. |
| `skills/lore-lint/SKILL.md` | Header line (path source) and the Output commit guard. |
| `skills/lore-init/templates/CLAUDE.md` | Update if it states the config path or an unconditional commit rule. |
| `README.md` | Rewrite the "The lore's location is stored in..." paragraph; document `--no-git` and the `cd`-or-link model in **Use**. |
| `.claude-plugin/plugin.json` | Version bump `0.1.0` → `0.2.0`. |

`docs/specs/2026-08-21-lore-plugin-design.md` and `docs/plans/2026-08-21-lore-plugin.md` are left unmodified — they are dated records of the original design, superseded by this document rather than edited.

## 6. Failure modes and error handling

| Situation | Behaviour |
|---|---|
| No rung matches | Hard fail with the §4.1 message. Nothing is created or written. |
| Link block names a path with no `index.md` | Hard fail naming the path and the block; suggest re-running `/lore:lore-link <path>`. No fall-through. |
| `/lore:lore-link` with no argument | Hard fail with usage. No file is touched. |
| `/lore:lore-link` target is not a lore | Hard fail; the project `CLAUDE.md` is not modified. |
| `/lore:lore-init` on an existing lore | Report "already a lore, nothing to do"; exit. No writes. |
| `/lore:lore-init` on a non-empty foreign folder | Refuse and ask for another path (unchanged). |
| Lore is not a git repo during ingest/lint | Complete the work, skip the commit, state it in the report. Not an error. |

## 7. Verification

The repo has no automated test harness; verification follows the existing pattern of a recorded acceptance transcript in `docs/verification/`. The acceptance script must cover, against throwaway lores in `/tmp`:

1. Two lores existing simultaneously; ingesting into each by `cd` and by explicit path; confirming neither sees the other's `raw/` or `log.md`.
2. Rung 4 hard failure from a directory that is neither a lore nor a linked project — assert nothing was created.
3. A link block pointing at a deleted lore — assert hard failure, not fall-through to cwd.
4. `/lore:lore-link` with no argument, and against a non-lore path — assert the project `CLAUDE.md` is unmodified in both cases.
5. `--no-git` init followed by an ingest — assert pages are written, no commit is attempted, and the report says so.
6. A pre-existing `~/.claude/lore.json` present and pointing somewhere wrong — assert it is ignored and does not influence resolution.
7. `/lore:lore-init` re-run on an existing lore — assert no writes and the correct report.

Any `~/.claude/lore.json` present on the machine is backed up before the run and restored after, per the convention in `docs/plans/2026-08-21-lore-plugin.md`.

## 8. Known limitation

This change enables N independent lores. It does not by itself deliver a set of wikis browsable in Obsidian as one knowledge base with live cross-links — separate lores have separate indexes, separate logs, and wikilinks that do not resolve across folders.

For that goal the recommendation is unchanged: one lore, with topic subfolders under `wiki/` and the index split into `index.md` (topic hub) plus `index/<topic>.md`, which `skills/lore/SKILL.md` already sanctions once the catalog outgrows ~200 lines. The Obsidian vault root is then the lore root. Page filenames must stay globally unique, since Obsidian resolves `[[Target]]` by basename across the whole vault.

The two decisions are independent. Removing global config is correct on its own merits.
