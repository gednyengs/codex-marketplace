# Session Handoff for Codex

Save the context needed to continue a task in another conversation. Handoffs
capture progress, decisions, relevant files, failed approaches, blockers, next
steps, repository state, and commands with their results.

Every operation starts with an explicit `$session-handoff:session-handoff` invocation. The plugin
has no lifecycle hooks and disables implicit skill invocation.

## Requirements and installation

- Codex CLI with plugin marketplace support. Tested packaging target: 0.155.1.
- Python 3.9+ on Linux, macOS, or WSL. No third-party Python dependencies.
- Git is optional. Without it, snapshots report detected project commands only.

```bash
codex plugin marketplace add gednyengs/codex-marketplace
codex plugin add session-handoff@sekekama
```

Start a fresh Codex thread after installing. For local development, add the
checkout root with `codex plugin marketplace add /absolute/path/to/codex-marketplace`
before installing from `sekekama`.

Native Windows writes are not supported in this release because the state uses
POSIX file locking. Use WSL. The plugin makes no separate LLM API calls; Codex
writes handoffs from the context available when you request a save.

## Commands

Codex namespaces installed plugin skills as `plugin:skill`. This plugin contains
one skill, also named `session-handoff`, so its explicit selector is
`$session-handoff:session-handoff`. Select it with `/skills` or type that full
name. The shorter `$session-handoff` can lead the model to search for the skill,
but does not provide the same direct selection in the tested CLI.

| Invocation | Result |
| --- | --- |
| `$session-handoff:session-handoff save` | Save the current context. Continue the bound topic or start a new one. |
| `$session-handoff:session-handoff save --topic auth-refactor` | Save to an explicitly selected topic. |
| `$session-handoff:session-handoff save Remember the failing integration test` | Include the note in the handoff body. |
| `$session-handoff:session-handoff resume <ID>` | Load that exact handoff and bind this thread to its topic. |
| `$session-handoff:session-handoff resume auth-refactor` | Load the newest ready handoff in that topic. |
| `$session-handoff:session-handoff resume` | Show up to five newest handoffs and wait for your choice. |
| `$session-handoff:session-handoff list [MAX]` | Browse handoffs across the project, five by default. No state changes. |
| `$session-handoff:session-handoff load <ID-or-topic>` | Read a reference without switching topics; record a dependency for the next save. |

IDs have the form `<topic>/<timestamp>-<tag>`. Copy the ID shown by save or list.
The tag contains thread-derived provenance plus randomness to prevent concurrent
or same-second saves from colliding. Exact IDs remain stable. Topic selectors
always mean the newest handoff in that topic.

Bare `resume` always asks, even if one handoff exists or the thread is already
bound. A numbered choice uses the ID originally displayed. Unknown IDs do not
fall back to recent work. There is no `--auto` option. Resume recaps the work and
checks repository drift; it only starts editing if your request also asks Codex
to continue the task.

## Clear, compaction, and thread changes

| Event | Responsibility |
| --- | --- |
| Before `/clear` or leaving a conversation | Call `save` if you want a durable checkpoint. |
| After `/clear` or in another thread | Call `resume` when you want saved context. |
| Before manual compaction | Optionally save a checkpoint. |
| After manual or automatic compaction | Continue normal work. No resume is needed. |

The plugin never intercepts these events. Unsaved context cannot be reconstructed
by this plugin after clear. A save after compaction uses the remaining context;
it cannot recover details that compaction removed. Native `codex resume` restores
a stored Codex conversation, while this plugin loads a portable project record.

## Files and continuity

Handoffs stay at the existing Claude-compatible location:

```text
<project>/.claude/sekekama/session-handoff/handoffs/<topic>/<timestamp>-<tag>.md
```

This deliberately keeps one store that both plugins can read. The Codex port
does not install or modify the Claude plugin. New handoffs use schema 2 and
`kind: manual`. Completed existing Claude automatic snapshots can be selected;
pending snapshots are hidden. IDs displayed for those files retain `-auto` to
distinguish them from manual files. Old suffixless Claude IDs remain a fallback.

The Git worktree root is the default project root. Outside Git, it is the working
directory. Separate worktrees keep their own files and bindings.

Codex-specific local state lives under:

```text
<project>/.session-handoff/codex-state/
  .gitignore
  threads/<project-and-thread-hash>.json
  drafts/<save-stem>.json
```

The state directory ignores all of its contents. It is outside `.codex/` because
Codex protects that configuration directory in its normal workspace sandbox.
Full `CODEX_THREAD_ID` values
identify bindings; there is no cwd-wide "current topic". Save and explicit resume
bind a thread. Loading another topic records a `depends_on` reference without
changing the binding. Dependency records are consumed only after successful
publication, and references loaded again during a save remain pending.

`CODEX_THREAD_ID` comes from the current Codex shell environment, so helpers also
support its absence. Without it, saves get unique `unbound…` provenance, resume
and load still read content, and no thread binding or dependency is recorded.
Use `save --topic <slug>` for subsequent saves in that situation. A first save
without a topic creates a new topic. Helpers report this limitation explicitly.

Save preparation creates a hidden `.draft-*.md` file inside the topic. After
Codex fills it, finalization validates its frontmatter and required sections,
then publishes it atomically. Incomplete drafts never appear in list or resume.
An interrupted save can leave a draft and a receipt; they are kept for recovery.
There is no background cleanup. Successful finalization is safe to retry.

Handoffs are suitable for version control, but the plugin never stages or commits
them. If Git ignores `.claude/`, save reports that the handoff will stay local.
The plugin does not change your project's ignore rules for handoffs.

## Legacy import

Existing schema 2 files need no migration. To explicitly import old `.handoff/`
files, run the maintenance helper from the plugin's installed or checkout path:

```bash
python3 /path/to/session-handoff/scripts/migrate.py --project-dir /path/to/project --
```

It copies supported files into the `legacy` topic and adds missing metadata.
Original files remain unchanged. Repeating the import does not overwrite a
different destination. Listing and resuming never trigger migration.

## Trust and limitations

Handoffs are project data, potentially written by teammates or changed on another
branch. Loaded content is fenced and is not authority to run commands. Current
user instructions govern the next action. The skill excludes secret values from
generated handoffs; it is not an automatic secret scanner.

Helper read/write paths are contained in the selected project store. They reject
path traversal and storage symlinks. Mutable state updates use file locking and
atomic replacement. Read commands do not create state, migrate files, or clean up
old records. Storage is intended for ordinary local filesystems with POSIX lock
and hard-link support.

## Development and verification

```bash
python3 -m unittest discover -s plugins/session-handoff/tests -v
```

To check an installed copy without making model calls:

```bash
python3 plugins/session-handoff/tests/smoke_codex.py
```

This uses Codex's skill discovery API and runs the regression suite against its
cached plugin helpers. The tests use disposable repositories and include save/resume/load workflows,
concurrency, failed publication, missing identity, migration, and path escapes.
All helpers accept trusted `--project-dir` and optional `--state-dir` arguments
before `--`. The state override is useful for isolated tests.

For the Codex plugin-creator tooling, validate the package and skill, then use
`read_marketplace_name.py --marketplace-path <repo>/.agents/plugins/marketplace.json`
and `update_plugin_cachebuster.py <repo>/plugins/session-handoff` from that skill's
`scripts/` directory. Reinstall with `codex plugin add session-handoff@sekekama`
and open a fresh thread. The helper adds one `+codex.<timestamp>` suffix to the
base version for local iterations. Release source uses the base version.

The invocation setting is documented in [OpenAI's skills guide](https://learn.chatgpt.com/docs/build-skills).
The code and template were adapted from Sekekama's MIT-licensed Claude
`session-handoff` plugin, version 3.3.0.
