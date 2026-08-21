---
name: lore-link
description: Use when the user runs /lore:lore-link inside a project — append a pointer block to that project's CLAUDE.md so Claude consults the lore for domain questions there.
---

# /lore:lore-link

1. Read the lore path from `~/.claude/lore.json` (if missing → tell user to run `/lore:lore-init`, stop).
2. Target file: `./CLAUDE.md` in the current project root (create if absent). Sanity-check that this IS the project root: if `./.git` is absent, confirm the path with the user before writing — a `CLAUDE.md` left in a subdirectory is never loaded.
3. **Idempotency:** if the file already contains `<!-- lore:start -->`, replace everything between the start and end markers with the fresh block; otherwise append the block. If `<!-- lore:start -->` is present but `<!-- lore:end -->` is not, do NOT modify the file: report the malformed block and ask the user to fix or remove it (writing to EOF would destroy whatever they wrote after it).

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
