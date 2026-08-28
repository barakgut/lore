# lore

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root, both created lazily. See `docs/agents/domain.md`.

## Git commits

Write commit messages that end at their last content line: subject, optional body, nothing after. Attribution trailers (`Co-Authored-By`, `Generated with`) are omitted here — authorship is the committer's.

Keep the subject line at 100 characters or fewer, and the body (everything below it) at 200 characters or fewer.
