---
name: lore-lint
description: Use when the user runs /lore:lore-lint — health-check the lore for index drift, ungrouped pages, group hygiene, dead wikilinks, duplicate titles, unresolved contradictions, schema violations, missing footnote attribution, missing concept pages and cross-references, knowledge gaps, and discard candidates. Fix mechanical issues; report judgment calls.
---

# /lore:lore-lint

Follow the `lore` skill for all conventions — including its **Finding the lore** ladder, which resolves `$LORE` (a path in the user's message, else cwd if it is a lore, else the project's `## Knowledge Base` section, else hard fail). Then read `$LORE/CLAUDE.md` — where it differs from these defaults, it wins.

## Checks

Start with the index script in check mode (the command is in the `lore`
skill's **Index regeneration** section; add `--check`). Its output feeds
check 1.

1. **Index drift** — `--check` exits 1 and prints `DRIFT <path>` lines: the
   index on disk is not what the pages' frontmatter says (a page added,
   renamed, deleted, regrouped, re-described, or deprecated without
   regeneration; a stale `index/*.md`). FIX: regenerate — the plain run at
   the end (see Output). Orphan pages, ghost entries, and deprecated pages
   listed outside `## Deprecated` cannot exist in a generated index except as
   drift, so this one check covers all three. If the plain run answers
   `ERROR: … run --seed-groups once`, follow the `lore` skill's
   **Index regeneration** section.
2. **Ungrouped pages** — non-deprecated `wiki/*.md` with no `group:`
   (`rg --files-without-match '^group:' "$LORE/wiki"` lists them; `rg -L`
   is `--follow`, not `--files-without-match`). FIX: add
   `group:` — reuse an existing group (`--groups`) when one fits, else the
   page's obvious topic, title-case.
3. **Group hygiene** — groups that differ only by case, punctuation, or
   plural (`Register Maps` vs `register-map`), and groups holding a single
   page. REPORT only, as merge candidates: the fix is changing `group:` on the
   pages, then regenerating.
4. **Dead wikilinks** — `rg -o '\[\[[^]]+\]\]' wiki/` targets with no matching `wiki/<Target_With_Underscores>.md`. FIX: if an obvious near-match page exists, correct the link; else REPORT.
5. **Duplicate titles** — two pages whose `title:` differ only by case/punctuation. REPORT only (merging is a judgment call).
6. **Contradictions** — count existing `> ⚠ CONTRADICTION` blocks. Also actively
   cross-check pages that share a subject (via title, wikilinks, or overlapping
   `sources[].resource`) for conflicting claims on the same fact (e.g. differing
   numeric specs). Skip any pair where either page already carries a
   CONTRADICTION marker naming that fact — lint is idempotent, so a re-run
   never adds a second marker for the same disagreement. Otherwise FIX by
   adding `> ⚠ CONTRADICTION: <claim A> [[Source_A]]; <claim B> [[Source_B]]`
   to the disagreeing page(s) — this only RECORDS the disagreement; it never
   resolves it (never edit either claim's value, never delete one, never pick a
   winner). REPORT every contradiction found, pre-existing or newly recorded.
7. **Description cap** — compute each page's entry line
   `- [title](wiki/X.md) — description` from its frontmatter: 200 characters
   or longer is over the cap. FIX: tighten `description` in the page (the
   index shows a cut hook until then). `--check` does not report this; the
   end-of-flow regeneration echoes what is left as
   `WARN: over-cap wiki/X.md (<n> chars)`.
   **Index size** — more than 200 `wiki/*.md` pages while the index is flat
   (the same regeneration echoes `NOTE: <n> entries > 200 …`): REPORT, then
   follow the `lore` skill's **Index regeneration** section's ask-once flow;
   never split or refuse on your own.
8. **Frontmatter validity** — against the `lore` skill's page schema:
   mandatory `type` (one of the allowed five), `title`, `description`, `tags`,
   and `generated` with both `by` and `at`. `group`, when present, must be a
   non-empty string (its absence is check 2's business, not a violation).
   `sources` is validated only when present (each entry needs a `resource`;
   `id` on every entry when the body contains `[^` footnotes) — its absence
   is not a violation. `status`, if present, must be `draft`, `stable`, or
   `deprecated`. FIX missing/typo'd fields when the correct value is obvious
   from content; else REPORT. A page carrying unsupported old-schema fields
   (`source:`, `captured`, `freshness`, `trust`, `verified`, `stale_after`)
   is REPORT only: name it as pre-0.3, suggest re-ingesting its raw source —
   never auto-migrate.
9. **Footnote discipline** — a page with 2+ `sources` entries whose
   nontrivial claims (one substantive, independently falsifiable statement —
   a number, a name, a rule, a behaviour) lack `[^id]` markers. REPORT only
   (attribution needs source knowledge lint doesn't have).
10. **Missing concept pages** — a topic wikilinked or substantively discussed across 2+ pages with no page of its own. REPORT only (suggest the page).
11. **Missing cross-references** — two pages clearly covering the same entity with no wikilink between them. FIX when the connection is unambiguous; else REPORT.
12. **Knowledge gaps** — questions the wiki raises but cannot answer, claims a newer source may have superseded, sources worth finding next. REPORT only, phrased as suggested next questions/sources for the user to investigate.
13. **Discard candidates** — pages that look like dead weight: near-duplicates,
    mis-ingests, pages superseded by newer ones, pages already
    `status: deprecated` for some time (candidates for permanent deletion).
    REPORT only, phrased as the discard flow's triggers: "discard page X" /
    "delete page X permanently".

## Output

- Apply all FIXes, then regenerate the index per the `lore` skill's **Index regeneration** section — this is check 1's FIX, and it also picks up every `group:`/`description:` change made above. Nothing after it touches `wiki/`, so it is this flow's one run.
- Then append to `log.md`: `## [YYYY-MM-DD] lint | <n> fixed, <m> reported`.
  Count each item once: a newly recorded contradiction marker is a FIX, so it belongs in `<n>` and not in `<m>`, even though the user-facing report lists every contradiction. A drift fix counts once, whatever the number of `DRIFT` lines.
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
