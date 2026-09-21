# Porting `session-handoff` to Codex CLI

Research date: 2026-09-21

> Superseded design recommendation: the agreed Codex port is strictly manual,
> with no hooks, automatic snapshots, journals, startup suggestions, or clear
> linking. See [implementation plan](session-handoff-implementation-plan.md) and
> [task checklist](session-handoff-tasks.md). The automatic architecture below is
> retained as historical research only. Packaging follows the Codex scaffold's
> `.codex-plugin/plugin.json`; implicit skill invocation is disabled.

This note checks the proposed marketplace commands, maps the Claude Code plugin's dependencies onto current Codex features, and recommends a Codex port architecture. Public product claims come from current OpenAI documentation. Local checks used the installed `codex-cli 0.155.1`. The Claude repository was inspected read-only.

## Bottom line

The marketplace claim is correct. All four proposed forms are documented and present in the installed CLI:

```bash
codex plugin marketplace add owner/repo
codex plugin marketplace add owner/repo --ref main
codex plugin marketplace add https://github.com/example/plugins.git --sparse .agents/plugins
codex plugin marketplace add ./local-marketplace-root
```

Codex accepts GitHub shorthand, Git URLs, SSH URLs, and local marketplace roots. `--ref` pins a Git ref. `--sparse` is repeatable and applies only to Git sources. The CLI reference marks plugin marketplace management as stable. [Marketplace packaging guide](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli), [CLI command reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli#cli-codex-plugin-marketplace)

The sparse command is valid syntax, but its checkout still has to contain every path used by the marketplace. If `.agents/plugins/marketplace.json` points to `./plugins/session-handoff`, use a second `--sparse plugins/session-handoff` or choose a layout where the plugin is already under the selected subtree.

The core manual handoff workflow can be ported cleanly. The Python snapshot, topic, handoff-file, resolution, migration, and concurrency logic is mostly reusable. Codex also supports plugin-bundled lifecycle hooks and supplies `session_id`, `cwd`, `transcript_path`, `PLUGIN_ROOT`, and `PLUGIN_DATA` in the relevant hook contexts. [Hook input fields](https://learn.chatgpt.com/docs/hooks#common-input-fields), [plugin-bundled hooks](https://learn.chatgpt.com/docs/hooks#plugin-bundled-hooks)

The automatic Claude behavior cannot be copied literally:

- Codex `SessionEnd.reason` is currently always `other`. It cannot write Claude's exact old-session `/clear` baton.
- Codex `PostCompact` receives `trigger`, but not Claude's `compact_summary`. `PreCompact` plain stdout is ignored, so it cannot shape Codex's compaction summary the way the Claude plugin does.
- Codex exposes `transcript_path`, but explicitly says its format is not a stable hook interface.

The recommended first port is therefore a faithful manual handoff system plus a conservative automatic journal built from structured hook fields. It should surface recent topics after `/clear`, not claim that it knows the exact cleared topic. Exact fork ancestry can be a later app-server enhancement.

## What the Claude plugin actually depends on

The current plugin has more machinery than the four prompt commands suggest. Its continuity model depends on specific Claude hook payloads and hook ordering.

The implementation lives under `../claude-marketplace/plugins/session-handoff/`:

- `commands/{save,resume,load,list}.md` are agent-facing prompt commands. They call deterministic Python helpers, then ask the model to compose or interpret the handoff.
- `skills/session-handoff/SKILL.md` exposes the same workflow to natural-language requests.
- `scripts/` owns path validation, snapshotting, topic selection, migration, atomic writes, locking, and garbage collection.
- `hooks/hooks.json` installs `SessionStart`, `SessionEnd`, `PreCompact`, and `PostCompact` command hooks.
- `docs/V2-SPEC.md` records the lifecycle assumptions behind the design.

### Durable and ephemeral state

Durable handoffs are Markdown files grouped by topic. A topic, not a Claude session ID, is the continuity unit:

```text
.claude/sekekama/session-handoff/handoffs/<topic>/
  YYYY-MM-DD-HHMMSS-<short-session-id>.md
  YYYY-MM-DD-HHMMSS-<short-session-id>-auto.md
```

The frontmatter is authoritative. It records topic, title, source session, creation time, kind, optional dependencies, and compaction metadata. Filenames include the session tag to avoid same-second collisions.

Ephemeral state maps a session to its topic and records pending cross-topic dependencies, compaction markers, and per-directory clear records. The code uses atomic replacement and locked read-modify-write for shared records. An age-based sweep removes stale ephemeral state without touching committed handoffs.

### How cross-session linking works in Claude

There are four distinct links:

1. Normal continuation uses `sessions/<sid>.topic`.
2. Claude `--resume` keeps the same session ID, so the same mapping still applies.
3. `/clear` produces `SessionEnd(reason=clear)` for the old session and `SessionStart(source=clear)` for the new session. The old hook appends a cwd-scoped baton containing the old session's topic. The new hook claims one fresh unclaimed baton. If several clears are concurrent, it refuses to guess and shows a picker.
4. Loading another topic records a `depends_on` edge for the next save without changing the current topic.

This is careful code. In particular, the `/clear` bridge does not come from a magical parent ID. It is a short-lived cwd correlation protocol built because Claude supplies a clear-specific end reason.

These links are logical topic links, not links to raw Claude transcripts. The committed handoff is what a new session or teammate consumes. The session ID binds local state and avoids filename collisions, while `depends_on` records topic-to-topic references.

### How the automatic compaction handoff works in Claude

`PreCompact` writes a pending deterministic snapshot and prints instructions that Claude appends to its compaction summarizer. `PostCompact` then receives `compact_summary`, extracts the summary body, and finishes the pending file. `SessionStart(source=compact)` nudges an automatic compaction to continue its in-flight work.

Two Claude-specific behaviors carry most of that feature:

- `PreCompact` stdout can shape the summarizer.
- `PostCompact` receives the generated summary.

Those are the precise points that need a new design in Codex.

## Codex capability map

| Need | Verified Codex support | Port consequence |
| --- | --- | --- |
| Git or local plugin marketplace | Yes, stable CLI commands | The proposed repository model is valid. |
| Portable plugin package | Yes, root `plugin.json`, `skills/`, optional hooks and scripts | Use the current Agent Plugins format rather than copying only the Claude manifest. |
| Reusable save/resume workflow | Yes, skills with explicit `$skill-name` or implicit activation | Convert Claude commands to one focused skill or a small set of skills. |
| Bundled command hooks | Yes, default `hooks/hooks.json` or manifest-declared hooks | Keep lifecycle scripts in the plugin. Users must trust them. |
| Session identity in hooks | Yes, `session_id` on stdin | Use this as the supported identity source. |
| Writable plugin state for hooks | Yes, `PLUGIN_DATA` | Store the hook registry there. Do not hardcode a cache path. |
| Startup/resume/clear/compact distinction | Yes, `SessionStart.source` | Startup topic lists and post-clear suggestions are possible. |
| Old-session `/clear` reason | No, `SessionEnd.reason` is currently only `other` | The exact Claude clear baton is unavailable. |
| Pre/post compaction events | Yes, both include `trigger=manual|auto` | Deterministic checkpointing is possible. |
| Generated compaction summary in `PostCompact` | No documented field | Do not port Claude's summary parser as if it still has input. |
| Stable transcript schema | No | Parsing JSONL can only be an opt-in compatibility fallback. |
| Structured latest user and assistant messages | Yes, `UserPromptSubmit.prompt` and `Stop.last_assistant_message` | Build a bounded automatic journal without parsing the transcript. |
| Native resume and fork | Yes | Prefer native resume for the same chat; use handoffs for new chats, teammates, or durable project records. |
| Exact fork ancestry | Yes through app-server thread objects, not hook input | Keep it out of the MVP or add a companion app-server client later. |

### Packaging and marketplace format

New packages should use a root `plugin.json` with the Agent Plugins schema. Skills live in `skills/`; OpenAI-specific hooks can be declared under `extensions.com.openai`. `.codex-plugin/plugin.json` remains a compatibility fallback, and Claude-compatible manifests are accepted, but the official recommendation for new work is the portable root format. [Plugin structure](https://developers.openai.com/plugins/build/plugins#plugin-structure)

A repository marketplace belongs at `.agents/plugins/marketplace.json`. Codex still recognizes the legacy `.claude-plugin/marketplace.json`, which is useful for migration, but this repository should publish the current location. Marketplace paths are relative to the marketplace root and must start with `./`. Local installs are copied into Codex's plugin cache, so testing changes requires a refresh, upgrade, or reinstall rather than assuming the source directory is live. [Marketplace metadata](https://developers.openai.com/plugins/build/plugins#marketplace-metadata), [local marketplace behavior](https://developers.openai.com/plugins/build/plugins#how-local-marketplaces-work)

OpenAI's Claude conversion guidance says Claude commands and agents should become skills, while command hooks need adaptation to the Codex hook runtime. [Claude plugin conversion guide](https://developers.openai.com/plugins/guides/submit-claude-plugin#submit-a-skills-only-plugin)

### Skills instead of packaged slash commands

Codex skills can be invoked explicitly with `$session-handoff` or chosen implicitly from their description. Custom prompts can create `/prompts:*` commands, but they are deprecated, live in the user's Codex home, and are not the right distribution mechanism for a marketplace plugin. [Skills](https://learn.chatgpt.com/docs/build-skills), [custom prompts](https://learn.chatgpt.com/docs/custom-prompts)

The proposed user interface is:

```text
$session-handoff save [note] [--topic slug]
$session-handoff resume [--auto] [topic-or-id]
$session-handoff load topic-or-id
$session-handoff list [--any]
```

Natural phrases such as "save a handoff" and "resume the auth refactor" should activate the same skill implicitly. The skill can preserve the Claude trust boundary: loaded handoff text is data from a file, not instructions that override the current user.

### Hook inputs and output behavior

Every command hook gets JSON on stdin with `session_id`, nullable `transcript_path`, `cwd`, `hook_event_name`, and `model`. Turn-scoped hooks add `turn_id`. For subagent hooks, `session_id` is the parent session ID. The transcript path is convenient, but its contents may change between Codex releases. [Common hook input](https://learn.chatgpt.com/docs/hooks#common-input-fields)

The useful events for this port are:

- `SessionStart`: `source` is `startup`, `resume`, `clear`, or `compact`. It can add developer context. The port should emit the documented JSON envelope with `hookSpecificOutput.hookEventName` and `hookSpecificOutput.additionalContext`, not depend on permissive plain-stdout handling. After automatic root-session compaction, that context reaches the immediate continuation. This is the right place to show recent topics or a pending handoff. [SessionStart](https://learn.chatgpt.com/docs/hooks#sessionstart)
- `UserPromptSubmit`: supplies the submitted `prompt`. A lightweight hook can append a bounded record of user intent to the session journal. [UserPromptSubmit](https://learn.chatgpt.com/docs/hooks#userpromptsubmit)
- `Stop`: supplies `last_assistant_message`. It can update the journal after a completed turn. It can also force continuation, but doing that every turn would add cost and surprise users, so the port should not use it as an automatic model-summarization loop. [Stop](https://learn.chatgpt.com/docs/hooks#stop)
- `Interrupt`: can mark an active turn as interrupted. Its output cannot prevent the interruption or restart the turn. [Interrupt](https://learn.chatgpt.com/docs/hooks#interrupt)
- `PreCompact` and `PostCompact`: both supply `trigger=manual|auto`. Plain stdout is ignored. Neither documented payload includes the generated compacted summary. [PreCompact](https://learn.chatgpt.com/docs/hooks#precompact), [PostCompact](https://learn.chatgpt.com/docs/hooks#postcompact)
- `SessionEnd`: is advisory, does not run for subagents, may occur after a 30-minute idle period, and currently reports only `reason=other`. Switching away from a chat does not end it immediately. Use it for cleanup, not continuity. [SessionEnd](https://learn.chatgpt.com/docs/hooks#sessionend)

Plugin hooks are not silently trusted. Users must review their exact definitions through `/hooks`, and changed hook definitions require review again. Administrators can disable hooks or permit only managed hooks. The skill must remain useful when the automatic layer is unavailable. [Hook trust](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)

### Session, resume, fork, and storage semantics

`codex resume <id>` continues a stored interactive chat. `--last` is scoped to the current working directory unless `--all` is supplied. `codex fork <id>` copies stored history into a new chat with a new ID while preserving the original. The TUI exposes the same actions through `/resume` and `/fork`. [Resume](https://learn.chatgpt.com/docs/developer-commands?surface=cli#cli-codex-resume), [fork](https://learn.chatgpt.com/docs/developer-commands?surface=cli#cli-codex-fork)

For a same-user restart, native resume is better than reconstructing context from a handoff. The plugin still adds value when the user deliberately starts a new chat, clears context, forks work into separate topics, hands work to a teammate, or wants a reviewable Markdown checkpoint in the repository.

Codex keeps local state under `CODEX_HOME`, which defaults to `~/.codex`; session transcripts are normally under `$CODEX_HOME/sessions`, with archived sessions under `$CODEX_HOME/archived_sessions`. History persistence can be disabled, and hook `transcript_path` may be null, so the port must not depend on scanning those directories. [Environment variables](https://learn.chatgpt.com/docs/config-file/environment-variables), [advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced#config-and-state-locations), [troubleshooting paths](https://learn.chatgpt.com/docs/reference/troubleshooting#feedback-and-logs)

No current public environment-variable page documents a session or thread ID variable. The current Codex source does, however, inject `CODEX_THREAD_ID` into shell-tool environments, and local `0.155.1` tool shells confirmed it. `CODEX_SESSION_ID` was also present in this hosted agent environment, but it is not part of that CLI source contract. In the root agent shell the two values were equal; in a spawned subagent shell they were different. The port may use `CODEX_THREAD_ID` for a root skill's helper process, with an explicit degraded fallback when it is missing. Hook code should continue to use the supported stdin `session_id`. Neither value should authorize access to another session's data. [Codex shell environment source](https://github.com/openai/codex/blob/main/codex-rs/core/src/exec_env.rs)

The app server is the documented structured option for deeper integration. `thread/resume` keeps the same thread ID, while `thread/fork` returns a new thread with `forkedFromId`. Thread objects also expose `sessionId`, which identifies the root of a fork tree. `thread/read` can inspect a stored thread without resuming it, and `thread/list` can filter by cwd. [App-server API overview](https://learn.chatgpt.com/docs/app-server#api-overview), [resume](https://learn.chatgpt.com/docs/app-server#resume-a-thread), [fork](https://learn.chatgpt.com/docs/app-server#fork-a-thread), [read without resuming](https://learn.chatgpt.com/docs/app-server#read-a-stored-thread-without-resuming)

That API is useful for a later companion process, but it is more machinery than a skills-and-hooks MVP needs. Hook payloads do not expose `forkedFromId` or the root `sessionId`.

## Recommended port architecture

### Package layout

```text
.agents/plugins/marketplace.json
plugins/session-handoff/
  plugin.json
  README.md
  LICENSE
  hooks/
    hooks.json
  skills/
    session-handoff/
      SKILL.md
      templates/HANDOFF_TEMPLATE.md
  scripts/
    lib.py
    snapshot.py
    new_path.py
    save_record.py
    resume.py
    load.py
    list.py
    session_start.py
    user_prompt_submit.py
    stop.py
    interrupt.py
    precompact.py
    postcompact.py
    session_end.py
  tests/
```

Use a root portable `plugin.json`. Declare the lifecycle configuration through `extensions.com.openai.hooks`, or rely on the default `hooks/hooks.json` lookup. Hook commands should use `${PLUGIN_ROOT}` and `${PLUGIN_DATA}`. Codex also defines the Claude aliases for hook compatibility, but new code should use the Codex names. [Bundled lifecycle hooks](https://developers.openai.com/plugins/build/plugins#bundled-mcp-servers-and-lifecycle-hooks)

Keep Python's standard-library-only implementation for the first port if Linux and macOS are the initial targets. For Windows, define `commandWindows` hook commands and decide whether requiring Python is acceptable. Codex itself does not document Python as a bundled runtime.

### Authoritative files and state

Use committed handoff files as the source of truth. For the first Codex release, keep the existing path and schema:

```text
.claude/sekekama/session-handoff/handoffs/<topic>/<timestamp>-<sid>.md
```

That name is provider-specific, but preserving it avoids a split history and lets Claude and Codex exchange the same committed handoffs immediately. A later coordinated release can move both plugins to a neutral path such as `.agents/sekekama/session-handoff/handoffs`. Do not maintain two writable stores. If a migration happens, both plugins should read the legacy path and write to one documented canonical path.

Use `PLUGIN_DATA` for the hook-owned registry:

```text
$PLUGIN_DATA/
  sessions/<session-id>.topic
  sessions/<session-id>.journal.jsonl
  sessions/<session-id>.deps
  cwd/<cwd-hash>.recent
  gc.stamp
```

Only hook processes are documented as receiving `PLUGIN_DATA`. A skill-invoked shell helper should not assume that variable or that directory is writable from the model's sandbox. There are three implementation choices:

1. Keep skill helpers workspace-only and make hook state advisory. The skill passes the topic explicitly and scans durable handoff files.
2. Have `SessionStart` inject a small, bounded developer-context record containing the current supported `session_id`; use a post-tool hook to commit any registry update inside the hook process.
3. Add a narrowly matched `PreToolUse`/`PostToolUse` bridge for this plugin's helper command. The hook receives the supported `session_id` and can update `PLUGIN_DATA`, but this adds a hook invocation to relevant tool calls and needs careful command matching.

For the MVP, use `CODEX_THREAD_ID` only as a convenience for root skill helpers, retain explicit-topic and picker fallbacks, and keep durable files authoritative. Before settling the state bridge, test whether a root skill's `CODEX_THREAD_ID` equals hook `session_id` across startup, resume, clear, compact, and fork. Choice 3 is reasonable only after dedicated tests for quoting, sandbox modes, concurrent sessions, and Windows.

### Manual workflow

Reuse the Claude two-phase save:

1. `snapshot.py` records branch, worktree state, recent commits, and detected build/test/run commands.
2. `new_path.py` validates or chooses the topic and prints an exact collision-safe path and frontmatter.
3. The model writes the structured handoff from the current conversation.
4. `save_record.py` validates the written file before committing session metadata or clearing pending dependencies.

Preserve the existing frontmatter grammar, path containment checks, fenced untrusted handoff output, atomic writes, and session-qualified IDs. Those are independent of Claude.

For resume, prefer an explicit ID or topic. If there is no session binding, load the sole recent topic or show a picker. Do not silently adopt a cwd-wide topic when several sessions may be active.

### Automatic safety net

Build the automatic layer from documented fields:

1. `SessionStart` registers `{session_id, cwd}` in hook-owned state and injects a short list of recent topics. On `source=resume`, stay quiet. On `source=clear`, say that context was cleared and show the latest topics. If exactly one topic was touched very recently, it may be highlighted as a suggestion, never silently adopted.
2. `UserPromptSubmit` appends a bounded, sanitized prompt record to the session journal.
3. `Stop` appends `last_assistant_message` and a timestamp. Cap journal size and exclude obvious credential material. Do not force another model turn.
4. `Interrupt` marks the current turn incomplete.
5. `PreCompact` writes an auto-checkpoint from the recent structured journal plus the deterministic repo snapshot. Mark it as `journal` or `partial`, not as a persisted Codex compaction summary.
6. `PostCompact` only marks timing/completion metadata. It cannot fill the file from a nonexistent `compact_summary` field.
7. `SessionEnd` performs bounded cleanup only. Age-based garbage collection should remain the main crash-recovery mechanism.

This produces a useful safety record without depending on private transcript JSON. It will be less semantically complete than Claude's model-generated compaction handoff. The file must say so.

An optional experimental mode may parse `transcript_path` to recover more detail. Keep it disabled by default, version-gate it, validate every field, and fall back to the structured journal. OpenAI explicitly warns that the transcript format may change. The current `0.155.1` transcript inspected during this research reinforces that warning: a `type=compacted` record had an empty plaintext `payload.message`, while compaction material appeared in encrypted replacement history. A transcript parser cannot assume that Codex stores the compacted summary as recoverable plaintext.

### Cross-session delivery

For the MVP, delivery is pull-based:

- A new or cleared session receives a recent-topic list through `SessionStart`.
- `$session-handoff resume <topic>` loads the durable handoff and verifies repository drift.
- The handoff records the source Codex session ID, so the recap may also offer `codex resume <id>` when the original transcript still exists.
- Forking and exact ancestry stay native to `codex fork` unless a later app-server companion is added.

Hooks cannot asynchronously push a handoff into an idle peer conversation. Background hook output is delivered only at the next safe conversation boundary, and completion of a background hook does not start a new turn. [Background hooks](https://learn.chatgpt.com/docs/hooks#run-hooks-in-the-background)

## Gaps and risks

1. Exact `/clear` baton is unavailable. `SessionStart` says that a clear occurred, but `SessionEnd` cannot identify it and the start payload has no prior session ID. Cwd recency is a suggestion heuristic, not a proof.
2. Automatic compaction parity is unavailable through documented hooks. There is no `compact_summary`, and `PreCompact` stdout cannot shape the summary.
3. Transcript parsing is brittle and may expose sensitive conversation content. Keep it optional.
4. Hooks require trust and may be disabled by policy. Manual skills must still work.
5. `PLUGIN_DATA` is guaranteed to hook commands, not documented for arbitrary skill-launched shell commands. Test the state bridge instead of assuming shared environment or sandbox access.
6. `CODEX_THREAD_ID` is injected by the current shell runtime but is missing from the public environment-variable reference. `CODEX_SESSION_ID` appears to be specific to this hosted environment. They differ inside subagents, so root skill helpers need a tested fallback.
7. Concurrent sessions in one cwd make "most recent topic" ambiguous. Keep the Claude pick-don't-guess rule.
8. Auto journals and handoffs can capture secrets that appeared in conversation. Bound data, avoid claiming that pattern-based redaction is complete, warn before committing auto files, and make the automatic layer configurable.
9. Session transcripts may not exist when history persistence is disabled. The durable handoff store must stand alone.
10. Python is an external runtime dependency, especially on Windows. Document it or replace it before claiming broad portability.

## Suggested delivery phases

Phase 0 should be a disposable lifecycle probe, not product code. Log hook names and field shapes without conversation contents, then test startup, resume, `/clear`, manual and automatic compaction, fork, interruption, two concurrent sessions in one cwd, hook trust, and disabled hooks. Confirm that the root skill's `CODEX_THREAD_ID` matches hook `session_id`, and measure when `SessionStart(source=clear)` fires. Use those results to choose the state bridge and the exact user-facing promises.

Phase 1 should ship the marketplace catalog, portable manifest, one skill, the existing deterministic helpers, manual save/resume/load/list, migration tests, and a `SessionStart` recent-topic list. This covers the durable core with the least platform risk.

Phase 2 should add the documented-field journal using `UserPromptSubmit`, `Stop`, `Interrupt`, and conservative pre-compaction snapshots. Test hook trust, disabled hooks, concurrency, history-off mode, sandboxed writes, and subagents.

Phase 3 can evaluate an app-server companion for exact fork-tree links and structured thread reads. It should earn its complexity with a concrete workflow. Do not add it only to mimic an internal Claude detail.

## Verification record

Local checks on 2026-09-21:

- `codex --version` returned `codex-cli 0.155.1`.
- `codex plugin marketplace add --help` accepted a local path, `owner/repo[@ref]`, HTTPS Git URL, or SSH Git URL, with `--ref`, repeatable `--sparse`, and `--json`.
- `codex resume --help` accepted a UUID or session name and exposed `--last`, `--all`, and `--include-non-interactive`.
- `codex fork --help` accepted a session UUID and exposed `--last` and `--all`.
- Root tool shells exposed equal `CODEX_SESSION_ID` and `CODEX_THREAD_ID`; a subagent shell exposed both with different values. This is empirical behavior, not a public compatibility promise.
- A current transcript's `type=compacted` record did not expose a plaintext compaction summary in `payload.message`; its replacement history was encrypted.
- The existing Claude implementation's 90 unit and integration tests passed unchanged.

The official documentation is sufficient to approve the marketplace approach and a skills-plus-hooks port. It is also sufficient to reject a line-for-line hook port: the Claude clear baton and compaction-summary capture depend on payload fields that Codex does not currently provide.
