# LORE - **L**ong-term **O**rganized **R**eference

a Claude Code plugin that maintains
a persistent, human-readable knowledge base ("the lore") on your disk. Drop any
file into an inbox folder; Claude distills it
into an interlinked markdown wiki with a catalog index — file types it cannot
read are skipped with a note in the log, never silently dropped. Link any
project to the lore with one command.

Zero dependencies: markdown + git + ripgrep, plus python3 for reading
spreadsheets. No databases, no APIs, no models.

## Install

This repo is its own Claude Code marketplace: `.claude-plugin/marketplace.json`
advertises the `lore` plugin that lives alongside it. So installing is always
the same two steps — point Claude at the repo, then install the plugin the repo
advertises.

### From GitHub

    claude plugin marketplace add barakgut/lore
    claude plugin install lore@lore-marketplace

The first command clones this repo into
`~/.claude/plugins/marketplaces/lore-marketplace/`. The second installs the
plugin from it — `lore` is the plugin name, `lore-marketplace` the marketplace
it comes from. Start a new Claude Code session afterwards; skills are loaded at
startup.

The same thing from inside a running session:

    /plugin marketplace add barakgut/lore
    /plugin install lore@lore-marketplace

### From any git URL

Anything git can clone works — a fork, a mirror, SSH, or a private host:

    claude plugin marketplace add https://github.com/barakgut/lore.git
    claude plugin marketplace add git@github.com:barakgut/lore.git
    claude plugin install lore@lore-marketplace

### From a local clone

Best when you want to read or edit the skills. Add the working copy by path
instead of by URL:

    git clone https://github.com/barakgut/lore.git
    claude plugin marketplace add ./lore
    claude plugin install lore@lore-marketplace

After editing a skill, run `claude plugin marketplace update lore-marketplace`
and start a new session to pick the change up. `claude plugin validate .` inside
the clone checks both manifests before you publish.

### Scope

Installs go to your user account by default. Use `--scope project` instead to
record the plugin in the current project, so anyone working in that repo gets
it:

    claude plugin install lore@lore-marketplace --scope project

### Verify, update, remove

    claude plugin list                                   # is lore installed and enabled?
    claude plugin marketplace update lore-marketplace    # pull the latest repo state
    claude plugin update lore                            # move to the new version (restart to apply)
    claude plugin uninstall lore                         # remove it

To confirm it took: start a session and type `/lore:` — the commands listed
below should be offered.

## Use

    /lore:lore-init [path]   # once — creates the lore (default ~/lore), git-inits it
    # drop files into <lore>/raw/   (PDF, images, xlsx/csv, md, txt, saved HTML)
    /lore:lore-ingest        # distill new raw files into the wiki
    /lore:lore-link          # once per project — point it at the lore
    /lore:lore-lint          # periodic health check (after ~5 ingests or monthly)

Then just ask questions in linked projects; answers cite their sources.

The lore's location is stored in `~/.claude/lore.json`. If that file is lost or
you move the folder, `/lore:lore-init <path>` on the existing lore just
re-points the config — it never touches your notes.

## Bootstrapping existing notes

Already have a pile of notes? Copy the source documents into `<lore>/raw/` and
any already-distilled notes into `<lore>/wiki/`, then run `/lore:lore-ingest`:
raw files are distilled as usual, and wiki pages without frontmatter get
frontmatter, an index entry, and a log entry. One-time copy — the pages belong
to the lore from then on.

## The folder

    <lore>/
      CLAUDE.md       # the schema — full rules; evolve it with the agent, it wins over defaults
      index.md        # catalog — read this first
      log.md          # append-only history / processed-file ledger
      raw/            # your originals — never modified
      wiki/           # the distilled lore — plain markdown, yours to read and edit

Notes for humans: sections headed `## My Take` are never touched by the agent;
contradictions between sources are flagged, never silently resolved; every
change is a git commit you can review or revert.

The lore is its own git repository — back it up like any other repo, or add a
remote and push it to carry your knowledge base between machines.

## License

MIT — see [LICENSE](LICENSE).
