# Configuration Reference

This page covers every configurable knob in autodev-x: TOML layers, environment
variables, CLI flags, and external tool (Codex CLI / Claude Code CLI / MCP / A2A)
integration settings.

---

## 1. ConfigStack — 4-layer TOML deep-merge

autodev loads configuration from up to four TOML files, merged in priority order
(lowest → highest):

| # | Layer | Path | Purpose |
|---|-------|------|---------|
| 1 | **user-global** | `~/.config/autodev/config.toml` | Personal defaults for all projects |
| 2 | **project-team** | `<repo>/.autodev/config.toml` | Shared project settings; checked in |
| 3 | **project-user** | `<repo>/.autodev/config.user.toml` | Personal overrides for this project; **git-ignored** |
| 4 | **runtime** | CLI flags / env injection | Highest priority; set by `--executor`, `--codex-timeout`, etc. |

Each layer is merged recursively: nested dicts are merged key-by-key, arrays-of-tables
are merged by their `code` or `id` key (later entries override earlier ones with the
same key), and plain arrays are concatenated. Scalars in a higher layer unconditionally
win.

### Minimal example

```toml
# <repo>/.autodev/config.toml  (project-team layer)
allow_mock_executor = false
concurrency = 4

[codex]
timeout_seconds = 600
model = "o4-mini"

[claude_code]
timeout_seconds = 900

[[agents]]
code = "product_manager"
max_rpm = 10
```

```toml
# <repo>/.autodev/config.user.toml  (project-user layer — git-ignored)
allow_mock_executor = true     # personal override for local dev
```

Supported top-level scalar keys: `state_dir`, `allow_mock_executor`, `fail_fast`,
`continue_and_report`, `concurrency`, `commit`, `push`, `tag`, `release`.

`[codex]` and `[claude_code]` sub-sections support any field present on the
corresponding `CodexCliExecutorConfig` / `ClaudeCodeExecutorConfig` dataclasses.

---

## 2. Environment variables

### 2.1 Mock and logging

| Variable | Values | Default | Effect |
|----------|--------|---------|--------|
| `FACTORY_FORCE_MOCK` | `1` / `0` | `0` | When set to `1`, all executor calls and agent LLM calls fall back to deterministic mock implementations. Ideal for CI pipelines that have no API keys. |
| `FACTORY_LOG` | `DEBUG` / `INFO` / `WARNING` / `ERROR` | `INFO` | Sets the autodev log level. For test runs the test suite sets this to `WARNING` via `tests/conftest.py`. |
| `FACTORY_CODEX_CMD` | Shell command template string | _(unset)_ | Overrides the `command_template` used by the Codex CLI executor (see `config.py`). Useful for swapping in a wrapper script or custom binary path without modifying `config.toml`. |
| `FACTORY_CLAUDE_CMD` | Shell command template string | _(unset)_ | Overrides the `command_template` used by the Claude Code CLI executor (see `config.py`). Same purpose as `FACTORY_CODEX_CMD` but for the Claude Code backend. |

Quick usage:

```bash
# Run a full delivery in pure mock mode (no Codex / Claude / API keys needed)
FACTORY_FORCE_MOCK=1 autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --from-scratch true \
  --mode dry-run \
  --allow-mock-executor true \
  --repo-path /tmp/demo
```

### 2.2 MCP server

| Variable | Values | Default | Effect |
|----------|--------|---------|--------|
| `AUTODEV_MCP_ALLOW_APPLY` | `1` / `0` | `0` | Enables `mode=apply` in MCP tool calls. Both this env var **and** `allow_apply=true` in the request body must be set. See [R3 hardening notes](#r3-hardening). |
| `AUTODEV_MCP_AUDIT_LOG` | `/path/to/audit.log` | _(unset)_ | When set, every MCP tool invocation is appended as a JSON line to this file (tool name, args, repo_path, outcome, timestamp). |

### 2.3 A2A networking

| Variable | Values | Default | Effect |
|----------|--------|---------|--------|
| `AUTODEV_A2A_TOKEN` | Bearer token string | _(unset)_ | Sent as `Authorization: Bearer <token>` on outgoing A2A HTTP requests and validated on `a2a-serve` incoming requests. |
| `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS` | `1` / `0` | `0` | Disables the SSRF guard that blocks RFC-1918 and loopback addresses. **Set only in test environments.** Never set in production. |

---

## 3. Codex CLI configuration

Codex CLI reads its configuration from `~/.codex/` by default. The root directory
can be overridden with the `CODEX_HOME` environment variable (useful in CI where
`$HOME` may be ephemeral):

```bash
export CODEX_HOME=/opt/codex-config
```

The `CODEX_HOME` directory typically contains:

```
~/.codex/
├── auth.json          # OpenAI/Azure API key + org (read by codex CLI)
├── config.json        # model selection, sandbox defaults
└── instructions.md    # optional global system prompt
```

autodev's `WorkerIsolator` creates isolated per-worker `CODEX_HOME` directories
for concurrent runs. It symlinks the immutable shared files (`auth.json`,
`config.json`, `instructions.md`) from the parent `CODEX_HOME` and creates
private working directories for each worker, preventing cross-task contamination.

**Model selection** — set the model in `~/.codex/config.json`:

```json
{
  "model": "o4-mini",
  "provider": "openai"
}
```

Or pass it on the command line (autodev forwards the flag):

```bash
autodev deliver-project ... --executor codex
# codex model is read from CODEX_HOME/config.json
```

---

## 4. Claude Code CLI configuration

Claude Code CLI reads Anthropic credentials from the environment or from its own
session state. Set your API key before the first run:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or run the interactive login flow:
claude auth login
```

**Model selection** — Claude Code CLI defaults to the latest Claude model; you
can pin a model via the `ANTHROPIC_MODEL` environment variable or the
`claude config set model` command:

```bash
claude config set model claude-opus-4-7   # persistent
# or per-invocation:
ANTHROPIC_MODEL=claude-sonnet-4-5 autodev deliver-project ...
```

---

## 5. Executor selection logic

The `--executor` flag (or the `executor` key in `config.toml`) determines which
CLI backend handles each task:

| Value | Behaviour |
|-------|-----------|
| `auto` (default) | Routes scaffold / test / small-patch → Codex; architecture / refactor / security / docs / release → Claude Code. Falls back to mock if both CLIs are absent and `allow_mock_executor=true`. |
| `codex` | Forces every task to Codex CLI. |
| `claude` | Forces every task to Claude Code CLI. |
| `mock` | Forces deterministic mock for every task (equivalent to `FACTORY_FORCE_MOCK=1`). |

The routing table in `ExecutorRouter` maps task types to backends:

| Task type | Default backend |
|-----------|----------------|
| scaffold, test, small patch (≤5 files, low risk) | Codex CLI |
| feature (>5 files or high risk), refactor, architecture | Claude Code CLI |
| security review, docs, release | Claude Code CLI |
| any, when chosen CLI is missing | mock (requires `allow_mock_executor=true`) |

---

## 6. Timeout configuration

Set timeouts via CLI flags or `config.toml`:

```bash
# CLI flags (override config file)
autodev deliver-project \
  --codex-timeout 600 \
  --claude-timeout 900 \
  ...
```

```toml
# config.toml equivalent
[codex]
timeout_seconds = 600      # default 600 s

[claude_code]
timeout_seconds = 900      # default 900 s
```

---

## 7. MCP server configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "autodev": {
      "command": "autodev",
      "args": ["mcp-serve"],
      "env": {
        "AUTODEV_MCP_ALLOW_APPLY": "0",
        "AUTODEV_MCP_AUDIT_LOG": "/tmp/autodev-mcp-audit.jsonl"
      }
    }
  }
}
```

### Claude Code (project-level MCP)

Add to `.claude/settings.json` (or use `claude mcp add`):

```json
{
  "mcpServers": {
    "autodev": {
      "command": "autodev",
      "args": ["mcp-serve"]
    }
  }
}
```

Or via the CLI:

```bash
claude mcp add autodev -- autodev mcp-serve
```

The server communicates via **JSON-RPC 2.0 over stdio**.  The 9 available tools
are: `scan`, `classify_input`, `create_prd`, `deliver_project`, `run_issue`,
`report`, `roundtable`, `release_check`, `list_runs`.

---

## 8. A2A roster and bearer auth

The A2A roster file records known remote agent cards:

```
~/.autodev/a2a-roster.json
```

Override the roster path with `--save-to` when registering:

```bash
autodev a2a-register \
  --endpoint http://agent.example.com:8421 \
  --save-to /shared/team-roster.json
```

Authenticate outgoing calls with a bearer token:

```bash
export AUTODEV_A2A_TOKEN=my-secret-token
autodev a2a-call --endpoint http://agent.example.com:8421 --skill fix-bug \
  --task-json '{"text": "Fix the off-by-one bug in aggregate.py"}'
```

The `a2a-serve` server reads the same `AUTODEV_A2A_TOKEN` env var and rejects
requests whose `Authorization` header does not match.

---

## 9. R3 hardening

The following variables were added or hardened during R3 RC hardening:

- **`AUTODEV_MCP_ALLOW_APPLY`** — MCP `mode=apply` double gate. The tool
  refuses to apply changes unless both the request sets `allow_apply=true`
  **and** the server process has `AUTODEV_MCP_ALLOW_APPLY=1` in its environment.
  This prevents accidental writes from clients that do not explicitly opt in.

- **`AUTODEV_MCP_AUDIT_LOG`** — Append-only JSONL audit trail for every MCP
  tool call: `{"ts": "...", "tool": "...", "args": {...}, "repo_path": "...",
  "outcome": "allowed|denied", "reason": "..."}`. Rotate with `logrotate` or
  an equivalent mechanism in production.

Both variables default to off (empty / unset) so existing deployments are
unaffected by the upgrade.
