# Session handoff Codex port

Temporary implementation plan, 2026-09-21. This records the agreed manual-only
design and supersedes the automatic-layer proposals in the research note.

Implementation finding: Codex 0.155.1 exposes the installed skill as
`session-handoff:session-handoff`. Use `$session-handoff:session-handoff` in the
commands below for direct skill selection. The shorter spelling shown in the
original proposal can prompt the model to search rather than select the skill.

## Behavior

```text
$session-handoff save [note] [--topic <slug>]
$session-handoff resume <id|topic>
$session-handoff resume
$session-handoff list
$session-handoff load <id|topic>
```

Only an explicit invocation activates the skill. Set
`policy.allow_implicit_invocation: false` in `agents/openai.yaml`.

- `save` creates a structured handoff from the live conversation and a repository
  snapshot. It binds the thread only after validating the saved file.
- `resume <id|topic>` loads the requested file and binds its topic to the thread.
- `resume` without a selector displays up to five recent choices, even when only
  one exists. Nothing is loaded or recorded until the user chooses. A numbered
  reply resolves to the exact ID originally displayed.
- `list` displays recent handoffs and changes no files or state.
- `load <id|topic>` reads a reference without switching the topic. It records a
  dependency for the next save, so it is not strictly read-only.
- There is no `--auto`, implicit resume, cwd heuristic, or lifecycle activity.
- After automatic or manual compaction, continue normally. Users can save before
  clearing context and explicitly resume after clearing or in another thread.
- Resume recaps the saved work and repository drift. It does not grant permission
  to execute tasks from the saved file.

The discussion used both "five latest handoffs" and "five latest topics". Follow
the user's original request: show the five latest handoffs across the project,
with IDs, dates, topics, titles, and summaries. Explicit topic selectors continue
to resolve to that topic's latest handoff.

## Package

```text
.agents/plugins/marketplace.json
plugins/session-handoff/
  .codex-plugin/plugin.json
  README.md
  LICENSE
  skills/session-handoff/
    SKILL.md
    agents/openai.yaml
    templates/HANDOFF_TEMPLATE.md
  scripts/
    lib.py
    snapshot.py
    new-path.py
    save-record.py
    resume.py
    load.py
    list.py
    migrate.py
  tests/
    test_session_handoff.py
```

Publish version `1.0.0` in this repository marketplace, category `Productivity`,
installation policy `AVAILABLE`, authentication policy `ON_INSTALL`. Use the
Codex plugin scaffold and validators. No hooks, MCP configuration, or apps.

## Storage and compatibility

Keep schema 2 handoffs under
`.claude/sekekama/session-handoff/handoffs/<topic>/` so existing Claude handoffs
remain usable. New files are always `kind: manual`; they have no compaction fields
or automatic suffix. Completed existing Claude snapshots remain readable, while
pending snapshots remain excluded.

Keep Codex thread bindings and pending dependency IDs in an ignored project-local
`.session-handoff/codex-state/` directory. Live testing found that `.codex/` is
protected by the normal workspace sandbox. Use `CODEX_THREAD_ID` as a convenience, with an explicit
state-directory override for tests. Do not use hook-only environment variables.
When the thread ID is missing, use unique provenance for saves and no shared
anonymous binding. Users can still resume by ID and save with an explicit topic.
Never guess continuity from recency or working directory.

Retain explicit legacy migration as a maintenance helper. Discovery commands
must not silently migrate files or run garbage collection, since listing and the
no-selector picker promise no writes. Migration preserves originals.

## Implementation sequence

1. Correct the research recommendation and establish this plan and checklist.
2. Scaffold the marketplace and plugin; validate names and metadata.
3. Adapt the deterministic Python core from the Claude implementation. Preserve
   frontmatter handling, snapshot detection, path containment, atomic writes,
   locking, exact ID and topic resolution, dependencies, and explicit migration.
   Remove clear batons, hooks, transcript processing, and compaction writers.
4. Implement save, resume, list, and reference loading with strict manual
   resolution. Read and validate a selected file before changing bindings. Ensure
   save preparation/finalization cannot lose pending dependencies on failure.
5. Write the Codex skill, explicit invocation policy, and handoff template. Resolve
   helpers relative to the installed skill; pass the project root explicitly.
6. Document installation, Python dependency, storage, compatibility, degraded
   identity behavior, and clear/compaction responsibilities.
7. Adapt the relevant Claude tests and add manual-flow regression tests.
8. Validate the package and exercise local marketplace installation and the
   installed skill/helpers in isolated temporary repositories.

Work through the tasks in order and record outcomes in
`session-handoff-tasks.md`. No commits or publication are implied.

## Verification

- Save twice in one thread; explicitly switch topics; resume by ID and topic.
- Picker returns zero through five entries without writes; one entry never
  auto-loads; selection uses the displayed ID even if newer files appear.
- List has no writes, including in projects containing legacy files.
- Load preserves the active topic and records cross-topic dependencies; later
  successful save consumes only dependencies actually recorded in that file.
- Failed or malformed saves/loads leave state intact.
- Same-second and concurrent saves cannot overwrite each other.
- Traversal and symlink escapes are rejected for both reads and writes.
- Existing schema 2 manual and completed Claude automatic files are readable;
  pending files stay hidden. Explicit migration is idempotent.
- Snapshots work without Git; missing thread identity has no shared state.
- Package and skill validate; implicit invocation is disabled; no hooks ship.
- Local installation resolves helpers from the cache. Where a live CLI session
  is available, smoke-test explicit skill invocation, clear, and compaction.
  Record unavailable checks accurately instead of claiming runtime verification.

## Completion

The package installs, the supported manual workflows pass their tests, existing
handoffs remain readable, and the documentation accurately describes any runtime
limitations. No operation is triggered by clear, compaction, startup, or shutdown.
