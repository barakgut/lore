---
name: lore-link
description: Use when the user runs /lore:lore-link <path> — append a pointer block to that project's CLAUDE.md so Claude consults the lore at <path> for domain questions there.
---

# /lore:lore-link <path>

1. `<path>` is required — the lore to link this project to. If the user gave no path, STOP with:

   > Usage: `/lore:lore-link <path-to-lore>` — e.g. `/lore:lore-link ~/lore`

   Do not infer it from cwd and do not guess. Writing the wrong path here silently mis-routes every later question in this project.

2. Expand `<path>` to an absolute path and validate it is a lore: `[ -f "<path>/index.md" ]`. If not, STOP and name the path — **do not modify** the project's `CLAUDE.md`.
3. Target file: `./CLAUDE.md` in the current project root (create if absent). Two checks before writing anything:
   - **Refuse if cwd is itself a lore** — `[ -f ./index.md ] && [ -d ./raw ] && [ -d ./wiki ]`, the same three-part test the `lore` skill's rung 2 uses. If it passes, STOP and explain: a lore's own `CLAUDE.md` is its schema and must never carry a `lore:start` block. Run this command from the project you want to link, not from inside a lore. (`./.git` is no substitute — a default lore is git-initialised too.)
   - **Sanity-check that this IS the project root** — if `./.git` is absent, confirm the path with the user before writing; a `CLAUDE.md` left in a subdirectory is never loaded.
4. **Idempotency:** if the file already contains `<!-- lore:start -->`, replace everything between the start and end markers with the fresh block; otherwise append the block. If `<!-- lore:start -->` is present but `<!-- lore:end -->` is not, do NOT modify the file: report the malformed block and ask the user to fix or remove it (writing to EOF would destroy whatever they wrote after it).

Block to write (substitute the real lore path):

```markdown
<!-- lore:start -->
## Lore
This project is linked to a knowledge base at `<LORE_PATH>`.
- For domain/knowledge questions, use the `lore` skill: read `<LORE_PATH>/index.md` first, then rg its wiki/; cite sources.
- Never edit `<LORE_PATH>/raw/`. Wiki edits must follow the lore skill's conventions.
<!-- lore:end -->
```

5. Report: linked path, and whether the block was added or refreshed.
