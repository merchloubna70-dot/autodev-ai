# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- R3 hardening: `AUTODEV_MCP_ALLOW_APPLY` and `AUTODEV_MCP_AUDIT_LOG` env vars
  for MCP apply-mode gate and audit trail (see R3 hardening docs).
- `docs/configuration.md` — comprehensive environment and TOML config reference.
- `docs/troubleshooting.md` — 12-scenario problem-solving guide.
- `CHANGELOG.md` — this file.

---

## [0.1.0a1] — 2026-05-14 (Pre-Release)

### Added

#### Core agent pipeline
- CrewAI multi-agent base: 12-agent graph from `InputClassifier` through
  `ReleaseManager` covering PRD, architecture, milestones, tasks, quality gates,
  security review, verification, and doc writing.
- Full audit-trail artifact tree written under
  `<repo>/.dev-factory/runs/<run_id>/` (input / product / architecture /
  planning / execution / quality / verification / delivery).
- Run state machine: `draft → running → paused → done | failed`; runs are
  resumable (`continue-run`) and replayable (`replay`).

#### Multi-CLI executor router
- `ExecutorRouter` — the single entry point for all CLI traffic; routes tasks
  to Codex CLI, Claude Code CLI, or mock executor based on task type, risk
  level, and file count.
- `CodexCliExecutor` — wraps `codex` binary, passes SAFETY BOUNDARY prompt,
  parses JSONL `--json` output into `CodexInnerStep` records.
- `ClaudeCodeExecutor` — wraps `claude` binary for architecture, security,
  long-context refactors, release roll-ups.
- `MockExecutor` / `MockCodexExecutor` — deterministic stand-ins that produce
  realistic artifacts without API keys; engaged automatically when both CLIs are
  absent or via `--allow-mock-executor true`.
- Executor selection: `--executor codex|claude|auto|mock`; `auto` (default)
  picks the best CLI per task type.

#### A2A protocol and roundtable
- A2A HTTP transport with SSRF guard: blocks RFC-1918 / loopback addresses by
  default; override with `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=1` (test-only).
- Bearer-auth via `AUTODEV_A2A_TOKEN` environment variable.
- `AgentRoster` with persistent JSON file at `~/.autodev/a2a-roster.json`.
- `autodev a2a-serve` — JSON-RPC 2.0 HTTP server accepting tasks from external
  agents on a configurable port.
- `autodev a2a-register` / `autodev a2a-call` — register a remote card and
  dispatch tasks.
- `autodev roundtable` (party mode) — recruit N specialist agents by skill,
  collect independent analyses, synthesize into a consensus report.

#### MCP server (9 tools)
- `autodev mcp-serve` — JSON-RPC 2.0 MCP server over stdio; compatible with
  Claude Desktop and Claude Code.
- Tools: `scan`, `classify_input`, `create_prd`, `deliver_project`,
  `run_issue`, `report`, `roundtable`, `release_check`, `list_runs`.
- Apply-mode gate: `mode=apply` requires both `allow_apply=true` in the request
  **and** `AUTODEV_MCP_ALLOW_APPLY=1` in the server environment.
- Audit log: every tool invocation appended to `AUTODEV_MCP_AUDIT_LOG` file
  when the env var is set.

#### BMAD sprint mode
- `autodev sprint-start` / `sprint-status` / `sprint-retro` / `sprint-correct`
  — open, monitor, close, and course-correct multi-week sprints.
- BMAD-Sally UX workflow via `autodev design-ux`.

#### Configuration
- `ConfigStack` — 4-layer TOML deep-merge: user-global →
  project-team → project-user → runtime; array-of-tables merging by `code/id`
  key.
- `FACTORY_FORCE_MOCK=1` — forces deterministic mock across all executors and
  agents.
- `FACTORY_LOG` — sets log level (default `INFO`).

#### CLI surface
- 35 CLI subcommands via Typer; every command is fully documented with
  `--help`.
- Shell safety: blocks `rm -rf`, `sudo`, `cat .env`, `curl | bash`, etc. in all
  executor modes.

#### R1 audit + R2 P0 hardening
- R1 documentation audit: identified CHANGELOG, configuration, and
  troubleshooting as missing docs; recorded in
  `docs/validation/autodev_documentation_onboarding_audit.md`.
- R2 P0 closure: SSRF guard on A2A HTTP transport; HMAC-signed MCP audit log
  entries; `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS` env var; recorded in
  `docs/validation/autodev_r2_*`.

### Notes
- PyPI not yet published; install from the GitHub Release wheel or source.
  See [README § Install](README.md#install).
- `pip install --upgrade autodev-ai==0.1.0a1` requires the `--pre` flag
  because `0.1.0a1` is a pre-release version marker.
- Homebrew tap formula is blocked until the PyPI `0.1.0a1` sha256 is available
  after the first `twine upload`.
- Docker image `ghcr.io/merchloubna70-dot/autodev-ai:0.1.0-alpha` ships Codex
  CLI and Claude Code CLI pre-installed; ~2 GB compressed.

[Unreleased]: https://github.com/merchloubna70-dot/autodev-ai/compare/v0.1.0-alpha...HEAD
[0.1.0a1]: https://github.com/merchloubna70-dot/autodev-ai/releases/tag/v0.1.0-alpha
