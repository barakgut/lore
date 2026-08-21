---
name: lore-init
description: Use when the user runs /lore:lore-init [path] — create (or re-point to) the lore folder, scaffold its layout with its CLAUDE.md schema, git-init it, and record its location in ~/.claude/lore.json.
---

# /lore:lore-init [path]

Follow the `lore` skill for all conventions. The full-rules schema every new lore is seeded with lives at `${CLAUDE_PLUGIN_ROOT}/skills/lore-init/templates/CLAUDE.md` — i.e. `templates/CLAUDE.md` next to this file, if you need to locate it another way.

1. Resolve `LORE` = the argument if given, else `$HOME/lore`. Expand to an absolute path.
2. **Existing lore?** If `$LORE/index.md` exists: do NOT touch the folder. Only rewrite the config (step 5), report "re-pointed config to existing lore", and stop after step 5.
3. **Non-empty, non-lore folder?** If `$LORE` exists, is non-empty, and has no `index.md`: refuse and ask the user for a different path. Never scaffold over foreign files.
4. Scaffold:

```bash
mkdir -p "$LORE/raw" "$LORE/wiki"
cat > "$LORE/index.md" <<'EOF'
# Lore Index

<!-- One line per wiki page: - [Title](wiki/Page.md) — hook. Grouped by ## topic. <200 chars per entry; target ~200 lines. -->
EOF
cat > "$LORE/log.md" <<EOF
# Lore Log

## [$(date +%F)] init | lore created
EOF
cp "${CLAUDE_PLUGIN_ROOT}/skills/lore-init/templates/CLAUDE.md" "$LORE/CLAUDE.md"
cd "$LORE" && git init -q && git add -A && git commit -q -m "init: lore scaffold"
```

If that copy fails — `CLAUDE_PLUGIN_ROOT` unset or the template not found there — locate `templates/CLAUDE.md` next to this SKILL.md and copy it. If you still cannot find it, STOP and tell the user: a lore without its `CLAUDE.md` has no schema layer, and step 2 will refuse to heal it later.

(If git identity is unset in this environment, set a repo-local one first with `git config user.email` / `git config user.name`, asking the user for values if unknown.)

5. Record location:

```bash
mkdir -p ~/.claude
python3 -c 'import json,sys; print(json.dumps({"path": sys.argv[1]}))' "$LORE" > ~/.claude/lore.json
```

6. Report: lore path, what was created (or "re-pointed"), and next steps (drop files into `raw/`, run `/lore:lore-ingest`, run `/lore:lore-link` inside projects).
