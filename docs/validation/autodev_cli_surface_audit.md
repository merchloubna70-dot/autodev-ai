# autodev CLI Surface Audit

**Round:** cli_surface_audit  
**Date:** 2026-05-14  
**Auditor:** Agent C — Release Hardening  
**Scope:** All 35 registered CLI subcommands

---

## Summary

| Metric | Value |
|---|---|
| Total commands audited | 35 |
| `--help` exit_code 0 | **35 / 35** |
| `Usage:` string present | **35 / 35** |
| Help failures | 0 |
| New test file | `tests/unit/test_cli_help_surface.py` |
| Tests written | 37 (35 subcommands + root_help + root_version) |
| Tests passing | 37 |

---

## Command Table

| Command | exit_code | has_help | requires_args | requires_external_cli | supports_mock | smoke_status | doc_path (primary) |
|---|---|---|---|---|---|---|---|
| run-issue | 0 | true | false | codex, claude | true | requires_repo | docs/usage.md |
| deliver-project | 0 | true | false | codex, claude | true | requires_repo | docs/quickstart.md |
| classify-input | 0 | true | true (`--input`) | — | false | smoke_runnable | docs/usage.md |
| create-prd | 0 | true | true (`--project-brief`) | — | false | smoke_runnable | docs/usage.md |
| plan-project | 0 | true | true (`--prd`) | — | false | requires_repo | docs/usage.md |
| plan-milestones | 0 | true | true (`--prd`) | — | false | requires_repo | docs/usage.md |
| plan-tasks | 0 | true | true (`--milestone-id`) | — | false | requires_repo | docs/usage.md |
| execute-milestone | 0 | true | true (`--run-id`, `--milestone-id`) | codex, claude | true | requires_repo | docs/usage.md |
| continue-run | 0 | true | true (`--run-id`) | codex, claude | false | requires_repo | docs/usage.md |
| replay | 0 | true | true (`--run-id`) | codex, claude | false | requires_repo | docs/usage.md |
| scan | 0 | true | false | — | false | requires_repo | docs/usage.md |
| verify | 0 | true | true (`--run-id`) | — | false | requires_repo | docs/usage.md |
| release-check | 0 | true | true (`--run-id`) | — | false | requires_repo | docs/usage.md |
| report | 0 | true | true (`--run-id`) | — | false | requires_repo | docs/usage.md |
| export-delivery | 0 | true | true (`--run-id`) | — | false | requires_repo | docs/usage.md |
| push | 0 | true | true (`--run-id`) | git | false | requires_repo | docs/usage.md |
| create-pr | 0 | true | true (`--run-id`) | gh, git | false | external_only | docs/usage.md |
| fix-bug | 0 | true | true (`--bug`) | codex, claude | true | requires_repo | docs/tutorials/01-bug-fix.md |
| multi-patch-fix-bug | 0 | true | true (`--bug`) | codex, claude | true | requires_repo | docs/architecture.md |
| review | 0 | true | true (`--run-id`, `--decision`) | — | false | requires_repo | docs/quickstart.md |
| roundtable | 0 | true | true (`--topic`) | claude | true | smoke_runnable | docs/tutorials/05-roundtable.md |
| mcp-serve | 0 | true | false | — | false | help_only | docs/tutorials/06-mcp-server.md |
| a2a-serve | 0 | true | false | — | false | help_only | docs/tutorials/07-a2a-server.md |
| a2a-register | 0 | true | true (`--endpoint`) | — | false | external_only | docs/tutorials/07-a2a-server.md |
| a2a-call | 0 | true | true (`--endpoint`) | — | false | external_only | docs/tutorials/07-a2a-server.md |
| next | 0 | true | true (`--run-id`) | — | false | requires_repo | docs/architecture.md |
| design-ux | 0 | true | false | — | false | smoke_runnable | docs/architecture.md |
| investigate | 0 | true | true (`--input`) | — | false | smoke_runnable | docs/architecture.md |
| generate-context | 0 | true | false | — | false | requires_repo | *(no tutorial doc)* |
| document-project | 0 | true | false | — | false | requires_repo | docs/architecture.md |
| sprint-start | 0 | true | false | — | false | smoke_runnable | docs/tutorials/04-sprint-mode.md |
| sprint-status | 0 | true | false | — | false | requires_repo | docs/tutorials/04-sprint-mode.md |
| sprint-retro | 0 | true | true (`--sprint-id`) | — | false | requires_repo | docs/tutorials/04-sprint-mode.md |
| sprint-correct | 0 | true | true (`--sprint-id`, `--change`) | — | false | requires_repo | docs/tutorials/04-sprint-mode.md |
| dashboard | 0 | true | false | — | false | external_only | *(no tutorial doc)* |

### smoke_status legend

- **help_only** — invocation blocks (server); only `--help` can be smoke-tested
- **smoke_runnable** — can run with minimal args in a temp dir without a real executor
- **requires_repo** — needs an existing `.dev-factory/` run state or real repo scan
- **external_only** — requires external service/CLI (gh, live A2A endpoint, textual TUI)

---

## Findings

### F-001 (low) — `generate-context` has no tutorial doc
`generate-context` is referenced only in `docs/architecture.md`. No quickstart or tutorial page
mentions it, making it undiscoverable to new users.

### F-002 (low) — `dashboard` has no tutorial doc
`dashboard` has no doc references at all. At runtime it exits with code 1 if the `textual`
optional extra is not installed (`pip install autodev-ai[tui]`).

### F-003 (info) — `mcp-serve` is a blocking server
`mcp-serve` calls `MCPServer().run()` which reads from stdin indefinitely. The `--help` path works
(exit 0), but live invocation cannot be smoke-tested without piping JSON-RPC input.

### F-004 (info) — `a2a-serve` is a blocking server
`a2a-serve` calls `server.serve_forever()`. Same constraint as `mcp-serve`; classified
`help_only`.

### F-005 (info) — `create-pr` gracefully guards missing `gh`
`create-pr` checks `GitHubAdapter().gh_available()` before attempting a PR and emits a JSON
failure message if `gh` is absent. Graceful failure confirmed.

---

## Test File

`tests/unit/test_cli_help_surface.py` — 37 tests:

- `test_root_help` — asserts `Usage:` and exit 0 on `autodev --help`
- `test_root_version` — asserts `0.` in output and exit 0 on `autodev --version`
- `test_help_<cmd>` × 35 — one per subcommand, asserts exit 0 and `Usage:` substring

All 37 tests pass as of audit date.
