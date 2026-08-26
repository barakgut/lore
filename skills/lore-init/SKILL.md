---
name: lore-init
description: Use when the user runs /lore:lore-init [path] [--no-git] — create the lore folder, scaffold its layout with its CLAUDE.md schema, and git-init it unless --no-git. Writes nothing outside the lore folder.
---

# /lore:lore-init [path] [--no-git]

Follow the `lore` skill for all conventions. The full-rules schema every new lore is seeded with lives at `${CLAUDE_PLUGIN_ROOT}/skills/lore-init/templates/CLAUDE.md` — i.e. `templates/CLAUDE.md` next to this file, if you need to locate it another way.

1. Resolve `LORE` = the path argument if given, else `$HOME/lore`. Expand to an absolute path. Note whether the user passed `--no-git` — it decides step 4's last block.
2. **Already a lore?** If `$LORE/index.md` exists: touch nothing. Report "already a lore, nothing to do" with the path, remind the user that a lore needs no config — `cd` into it, or add the `## Knowledge Base` section from step 5 to a project's `CLAUDE.md` — and stop.
3. **Non-empty, non-lore folder?** If `$LORE` exists, is non-empty, and has no `index.md`: refuse and ask the user for a different path. Never scaffold over foreign files. One exception — if it holds both `wiki/` and `CLAUDE.md`, it is a lore whose generated index is merely missing (the `lore` skill's **Finding the lore**): scaffold nothing, regenerate per **Index regeneration** (step 4's last line), report the repair, and stop.
4. Scaffold:

```bash
mkdir -p "$LORE/raw" "$LORE/wiki"
cat > "$LORE/log.md" <<EOF
# Lore Log

## [$(date +%F)] init | lore created
EOF
cp "${CLAUDE_PLUGIN_ROOT}/skills/lore-init/templates/CLAUDE.md" "$LORE/CLAUDE.md"
cat > "$LORE/.ignore" <<'EOF'
dashboard.html
EOF
cat > "$LORE/.gitignore" <<'EOF'
dashboard.html
EOF
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lore_index.py" "$LORE"
```

If that copy fails — `CLAUDE_PLUGIN_ROOT` unset or the template not found there — locate `templates/CLAUDE.md` next to this SKILL.md and copy it. If you still cannot find it, STOP and tell the user: a lore without its `CLAUDE.md` has no schema layer, and step 2 will refuse to heal it later.

The last line writes `index.md` — the `# Lore Index` header plus the generated-marker comment the script keys on, and nothing else while `wiki/` is empty. Never write `index.md` by hand, not even a placeholder: it is generated from `wiki/` frontmatter, and the plugin hook denies file-tool writes to it. If the script is not where `CLAUDE_PLUGIN_ROOT` says, use `scripts/lore_index.py` under the plugin root (the directory holding this skill's `skills/` folder); if you still cannot find it, STOP and tell the user — a scaffold left without `index.md` is not recognised as a lore by step 2 or by the `lore` skill's cwd rung.

Then, **only if the user did not pass `--no-git`**, initialise the repository. Run this block on a default init; on `--no-git` do not run it at all — not even "just in case":

```bash
cd "$LORE" && git init -q && git add -A && git commit -q -m "init: lore scaffold"
```

(If git identity is unset in this environment, set a repo-local one first with `git config user.email` / `git config user.name`, asking the user for values if unknown.)

With `--no-git` the lore has no history and no undo. Say so once in the report: ingest and lint will write pages without committing.

5. Report: the lore path, what was created, whether git was initialised, and next steps — drop files into `raw/`, then `cd` into the lore and run `/lore:lore-ingest`. Mention that the lore ignores `dashboard.html`, the optional human-only view (`python3 scripts/lore_dashboard.py <lore>` from the plugin repo). Mention that `index.md` is generated from the pages' frontmatter and is never hand-edited. Nothing was written outside the lore folder.

   Then print this block verbatim, with `$LORE` substituted, and tell the user to paste it into the `CLAUDE.md` of every project that should use this lore (one lore can serve any number of projects; the lore itself keeps no list of them):

   ```markdown
   ## Knowledge Base
   This project has a knowledge base (a lore) at `$LORE`. It is the source of truth: you MUST consult it first, via the `lore` skill, before answering any domain question.
   ```
