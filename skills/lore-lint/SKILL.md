---
name: lore-lint
description: Use when the user runs /lore:lore-lint — health-check the lore for orphan pages, dead wikilinks, index drift, duplicate titles, unresolved contradictions, schema violations, missing footnote attribution, missing concept pages and cross-references, knowledge gaps, and discard candidates. Fix mechanical issues; report judgment calls.
---

# /lore:lore-lint

Follow the `lore` skill for all conventions — including its **Finding the lore** ladder, which resolves `$LORE` (a path in the user's message, else cwd if it is a lore, else the project's `lore:start` block, else hard fail). Then read `$LORE/CLAUDE.md` — where it differs from these defaults, it wins.

## Checks

1. **Orphan pages** — `wiki/*.md` with no line in `index.md` (a line under
   `## Deprecated` counts). FIX: add an index line in the right group —
   `## Deprecated` if the page has `status: deprecated`.
2. **Ghost index entries** — entry lines in `index.md` (lines matching `^- \[`, never HTML comments or scaffold guidance) pointing at missing files. FIX: remove the line.
3. **Dead wikilinks** — `rg -o '\[\[[^]]+\]\]' wiki/` targets with no matching `wiki/<Target_With_Underscores>.md`. FIX: if an obvious near-match page exists, correct the link; else REPORT.
4. **Duplicate titles** — two pages whose `title:` differ only by case/punctuation. REPORT only (merging is a judgment call).
5. **Contradictions** — count existing `> ⚠ CONTRADICTION` blocks. Also actively
   cross-check pages that share a subject (via title, wikilinks, or overlapping
   `sources[].resource`) for conflicting claims on the same fact (e.g. differing
   numeric specs). Skip any pair where either page already carries a
   CONTRADICTION marker naming that fact — lint is idempotent, so a re-run
   never adds a second marker for the same disagreement. Otherwise FIX by
   adding `> ⚠ CONTRADICTION: <claim A> [[Source_A]]; <claim B> [[Source_B]]`
   to the disagreeing page(s) — this only RECORDS the disagreement; it never
   resolves it (never edit either claim's value, never delete one, never pick a
   winner). REPORT every contradiction found, pre-existing or newly recorded.
6. **Index entry cap** — entries over 200 chars. FIX: tighten the hook.
   **Index size** — file over ~200 lines. REPORT only: do not drop entries to fit (every page must stay reachable from the index); propose either consolidating related pages or splitting into `index.md` (topic hub) plus `index/<topic>.md`.
   **Deprecated placement** — a `status: deprecated` page whose index line is
   not under `## Deprecated`. FIX: move the line there.
7. **Frontmatter validity** — against the `lore` skill's page schema:
   mandatory `type` (one of the allowed five), `title`, `description`,
   `sources` (each entry with a `resource`; `id` on every entry when the body
   contains `[^` footnotes), and `generated` with both `by` and `at`. `status`,
   if present, must be `draft`, `stable`, or `deprecated`. FIX missing/typo'd
   fields when the correct value is obvious from content; else REPORT. A page
   carrying unsupported old-schema fields (`source:`, `captured`, `freshness`,
   `trust`, `verified`, `stale_after`) is REPORT only: name it as pre-0.3,
   suggest re-ingesting its raw source — never auto-migrate.
8. **Footnote discipline** — a page with 2+ `sources` entries whose nontrivial
   claims lack `[^id]` markers. REPORT only (attribution needs source
   knowledge lint doesn't have).
9. **Missing concept pages** — a topic wikilinked or substantively discussed across 2+ pages with no page of its own. REPORT only (suggest the page).
10. **Missing cross-references** — two pages clearly covering the same entity with no wikilink between them. FIX when the connection is unambiguous; else REPORT.
11. **Knowledge gaps** — questions the wiki raises but cannot answer, claims a newer source may have superseded, sources worth finding next. REPORT only, phrased as suggested next questions/sources for the user to investigate.
12. **Discard candidates** — pages that look like dead weight: near-duplicates,
    mis-ingests, pages superseded by newer ones, pages already
    `status: deprecated` for some time (candidates for permanent deletion).
    REPORT only, phrased as the discard flow's triggers: "discard page X" /
    "delete page X permanently".

## Output

- Apply all FIXes, then append to `log.md`: `## [YYYY-MM-DD] lint | <n> fixed, <m> reported`.
  Count each item once: a newly recorded contradiction marker is a FIX, so it belongs in `<n>` and not in `<m>`, even though the user-facing report lists every contradiction.
- Then commit, if the lore is a git repository:

  ```bash
  if [ "$(git -C "$LORE" rev-parse --show-toplevel 2>/dev/null)" = "$LORE" ]; then
    git -C "$LORE" add -A && git -C "$LORE" commit -m "lint: <summary>"
  else
    echo "NOT_A_GIT_REPO"
  fi
  ```

  When it is a repo, always commit — the log entry is itself a change, so a lint run is never a clean tree. When it is not, report that fixes were written without a commit.
- Report to the user: fixed items, then reported items grouped by check, each with file paths.
