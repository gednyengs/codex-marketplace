# Sekekama Codex marketplace

Codex CLI plugins for development workflows.

## Install

```bash
codex plugin marketplace add gednyengs/codex-marketplace
codex plugin add session-handoff@sekekama
```

Start a new Codex thread after installation.

For a local checkout, run from this repository:

```bash
codex plugin marketplace add .
codex plugin add session-handoff@sekekama
```

## Plugins

| Plugin | Purpose |
| --- | --- |
| [session-handoff](plugins/session-handoff/README.md) | Explicitly save, browse, and resume portable Markdown handoffs. |

## Development

Session Handoff requires Python 3.9+ on Linux, macOS, or WSL. Git supplies optional
repository snapshots. It uses only the Python standard library.

```bash
python3 -m unittest discover -s plugins/session-handoff/tests -v
```

Marketplace metadata lives in `.agents/plugins/marketplace.json`. Plugin paths
are relative to the repository root. Local plugins are copied into Codex's cache;
source edits require a reinstall and a fresh thread. See the plugin README for
the development loop.
