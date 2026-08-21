---
name: lore-lint
description: Use when the user runs /lore:lore-lint — health-check the lore for orphan pages, dead wikilinks, index drift, duplicate titles, stale pages, unresolved contradictions, missing concept pages and cross-references, knowledge gaps. Fix mechanical issues; report judgment calls.
---

# /lore:lore-lint

Follow the `lore` skill for all conventions. Lore path from `~/.claude/lore.json`; read `$LORE/CLAUDE.md` first — where it differs from these defaults, it wins.

## Checks

1. **Orphan pages** — `wiki/*.md` with no line in `index.md`. FIX: add an index line in the right group.
2. **Ghost index entries** — entry lines in `index.md` (lines matching `^- \[`, never HTML comments or scaffold guidance) pointing at missing files. FIX: remove the line.
3. **Dead wikilinks** — `rg -o '\[\[[^]]+\]\]' wiki/` targets with no matching `wiki/<Target_With_Underscores>.md`. FIX: if an obvious near-match page exists, correct the link; else REPORT.
4. **Duplicate titles** — two pages whose `title:` differ only by case/punctuation. REPORT only (merging is a judgment call).
5. **Staleness** — pages with `freshness` older than 90 days. REPORT only.
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
7. **Index entry cap** — entries over 200 chars. FIX: tighten the hook.
   **Index size** — file over ~200 lines. REPORT only: do not drop entries to fit (every page must stay reachable from the index); propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.
8. **Frontmatter validity** — missing `type`, or `type` outside the allowed five. FIX missing/typo'd fields when the correct value is obvious from content; else REPORT.
9. **Missing concept pages** — a topic wikilinked or substantively discussed across 2+ pages with no page of its own. REPORT only (suggest the page).
10. **Missing cross-references** — two pages clearly covering the same entity with no wikilink between them. FIX when the connection is unambiguous; else REPORT.
11. **Knowledge gaps** — questions the wiki raises but cannot answer, claims a newer source may have superseded, sources worth finding next. REPORT only, phrased as suggested next questions/sources for the user to investigate.

## Output

- Apply all FIXes, then append to `log.md`: `## [YYYY-MM-DD] lint | <n> fixed, <m> reported`.
  Count each item once: a newly recorded contradiction marker is a FIX, so it belongs in `<n>` and not in `<m>`, even though the user-facing report lists every contradiction.
- Then commit: `cd "$LORE" && git add -A && git commit -m "lint: <summary>"`. Always commit — the log entry is itself a change, so a lint run is never a clean tree.
- Report to the user: fixed items, then reported items grouped by check, each with file paths.
