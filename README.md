# LORE - **L**ong-term **O**rganized **R**eference

a Claude Code plugin that maintains
a persistent, human-readable knowledge base ("the lore") on your disk. Drop any
file into an inbox folder; Claude distills it
into an interlinked markdown wiki with a catalog index — file types it cannot
read are skipped with a note in the log, never silently dropped. Link any
project to the lore with one command.

Zero dependencies: markdown + ripgrep, plus git for the undo history (optional,
via `--no-git`) and python3 for reading spreadsheets and for the optional
dashboard. No databases, no APIs, no models.

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

    /lore:lore-init [path] [--no-git]   # once — creates the lore (default ~/lore); git-inits it unless --no-git
    # drop files into <lore>/raw/   (PDF, images, xlsx/csv, md, txt, saved HTML)
    cd <lore> && /lore:lore-ingest      # distill new raw files into the wiki
    /lore:lore-link <path>              # once per project — point it at the lore
    /lore:lore-lint                     # periodic health check (after ~5 ingests or monthly)

Then just ask questions in linked projects; answers cite their sources.

Replaced a file in `raw/` with a newer version? The next `/lore:lore-ingest`
notices — each ingest records the file's content hash in the log — and updates
only the pages that cite that file, flagging contradictions where another
source still disagrees. Files ingested before v0.3 carry no recorded hash, so
change detection can't see a replacement for them yet — name such a file
explicitly once (`/lore:lore-ingest spec.pdf`) to start tracking it.

A lore is self-describing — nothing about it is stored anywhere else. Commands
find it in this order: a path you name (`/lore:lore-ingest ~/wikis/hardware`),
the folder you are standing in, or the `lore:start` block that
`/lore:lore-link` wrote into a project's `CLAUDE.md`. If none of those apply the
command stops and says so rather than guessing at your notes. Moved a lore?
Re-run `/lore:lore-link <new-path>` in the projects that point at it.

Because nothing is global, you can keep as many separate lores as you like — one
per domain, per client, per machine.

`/lore:lore-init --no-git` skips `git init`, for a lore that lives inside a
folder already synced by Obsidian Sync, iCloud, or Dropbox, or nested in another
repo. Ingest and lint then write pages without committing and tell you so — you
lose the undo, so prefer the default.

## Bootstrapping existing notes

Already have a pile of notes? Copy the source documents into `<lore>/raw/` and
any already-distilled notes into `<lore>/wiki/`, then run `/lore:lore-ingest`:
raw files are distilled as usual, and wiki pages without frontmatter get
frontmatter, an index entry, and a log entry. One-time copy — the pages belong
to the lore from then on.

## Upgrading a pre-0.3 lore

Nothing is migrated automatically. Pages written under the old schema
(`captured`, `freshness`, `trust`, singular `source:`) are reported by
`/lore:lore-lint` as schema violations every run, by design — that's expected,
not a bug, and the only way to clear it is to re-ingest the page's raw source
by name. Likewise, files already ingested before v0.3 carry no recorded content
hash, so `/lore:lore-ingest` can't tell whether they've since been replaced;
name each one explicitly once (`/lore:lore-ingest <file>`) to start tracking
it.

## The folder

    <lore>/
      CLAUDE.md       # the schema — full rules; evolve it with the agent, it wins over defaults
      index.md        # catalog — read this first
      log.md          # append-only history / processed-file ledger
      raw/            # your originals — never modified
      wiki/           # the distilled lore — plain markdown, yours to read and edit

Notes for humans: sections headed `## My Take` are never touched by the agent;
contradictions between sources are flagged, never silently resolved; a plugin
hook blocks the agent from editing anything under `raw/`; retire a wiki page by
telling Claude "discard page X" (or "delete page X permanently" for true junk —
git history is the undo); every change is a git commit you can review or
revert, unless the lore was created with `--no-git`.

By default the lore is its own git repository — back it up like any other repo,
or add a remote and push it to carry your knowledge base between machines.

## Dashboard (for humans)

    python3 scripts/lore_dashboard.py <lore>          # writes <lore>/dashboard.html
    python3 scripts/lore_dashboard.py <lore> -o ~/dash.html

One self-contained HTML file — no server, no dependencies, no network — with
tabs for an overview, a mechanical health score, statistics, the wikilink
graph, the index as a topic tree, full-text search, the log, and the `raw/`
inbox. Open it in any browser; it is a snapshot, so re-run the script after
ingesting to refresh it. Links back into `wiki/` and `raw/` are relative to
where the file was written, so keep the dashboard and the lore together.

It is a human view only. Claude never runs the script and never reads the
file: the plugin's hook denies reading `<lore>/dashboard.html`. When the
output file lands inside the lore — the default, though not the `-o
~/dash.html` form above — the script also adds it to the lore's `.ignore`
(and to `.gitignore` too, when the lore is a git repository) so neither
ripgrep nor git picks it up. Deleting it costs nothing — re-run the script.

## License

MIT — see [LICENSE](LICENSE).
