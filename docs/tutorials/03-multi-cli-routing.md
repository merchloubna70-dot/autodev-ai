# Tutorial 03 — Multi-CLI Routing

autodev never calls Codex CLI or Claude Code CLI directly from business logic.
All execution is funneled through a single `ExecutorRouter` that decides which
CLI to use per task — and falls back to deterministic mocks when neither CLI
is available.

---

## The three executor modes

### `--executor codex`

Forces all tasks in this run to Codex CLI.

```bash
autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --from-scratch true \
  --repo-path /tmp/demo \
  --executor codex \
  --allow-mock-executor true
```

Use when: you want fast mechanical writes (scaffolding, test generation, small
patches) and you know the project does not require cross-file architectural
reasoning.

### `--executor claude`

Forces all tasks to Claude Code CLI.

```bash
autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --from-scratch true \
  --repo-path /tmp/demo \
  --executor claude \
  --allow-mock-executor true
```

Use when: the project involves complex multi-file refactors, cross-language
integration, security review, or release roll-up.

### `--executor auto` (default)

The router applies per-task heuristics to pick the best CLI automatically.
This is the recommended setting for most workloads.

```bash
autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --from-scratch true \
  --repo-path /tmp/demo \
  --executor auto
```

---

## Routing rules

The `ExecutorRouter` evaluates each `DeliveryTask` object and selects a backend
based on `task_type`, `risk_level`, and `files_affected`:

| Condition | Backend |
|-----------|---------|
| `--executor codex` (explicit) | Codex |
| `--executor claude` (explicit) | Claude Code |
| `task_type == scaffold` | Codex |
| `task_type == test` | Codex |
| `task_type == feature` AND ≤5 files AND risk ≤ medium | Codex |
| `task_type == feature` AND (>5 files OR risk > medium) | Claude Code |
| `task_type == refactor` | Claude Code |
| `task_type == architecture` | Claude Code |
| `task_type == integration` AND single-language | Codex |
| `task_type == integration` AND cross-language | Claude Code |
| `task_type == security` | Claude Code |
| `task_type == docs` | Claude Code |
| `task_type == release` | Claude Code |

---

## Reading the routing decision

Every task records its routing decision in:

```
.dev-factory/runs/<run_id>/execution/executor_selection_<task_id>.json
```

Example:

```json
{
  "task_id": "T-scaffold-001",
  "task_type": "scaffold",
  "files_affected": 2,
  "risk_level": "low",
  "selected_backend": "codex",
  "reason": "scaffold tasks always go to Codex",
  "fallback_used": false,
  "mock_used": true
}
```

`mock_used: true` means the CLI was not found and the mock executor was
substituted. This fact propagates to `release_check.json` so the run is never
incorrectly marked `ReleaseReady`.

---

## Mock fall-back semantics

1. Router picks best real CLI for the task.
2. If that CLI binary is found in `PATH` → runs it (`mock_used=false`).
3. If CLI is missing AND `--allow-mock-executor true` → runs the matching
   `MockCodexExecutor` or `MockClaudeExecutor` and sets `mock_used=true`.
4. If CLI is missing AND `--allow-mock-executor false` → the task fails closed:
   `error_type=cli_missing_fail_closed`. The run continues but records failure.

Force mock mode globally (useful in CI):

```bash
export FACTORY_FORCE_MOCK=1
autodev deliver-project ...
```

---

## Tuning the policy

The routing thresholds are configurable via `ExecutorSelectionPolicy` in code,
but the two most useful knobs are exposed as CLI flags:

| Flag | Default | Effect |
|------|---------|--------|
| `--executor codex\|claude\|auto` | `auto` | Override per-run backend |
| `--allow-mock-executor true\|false` | `true` in dry-run, `false` in apply | Allow mock fall-back |
| `--fail-fast / --no-fail-fast` | `--fail-fast` | Stop on first failure vs continue |
| `--continue-and-report` | off | Continue past failures, report at end |

---

## Audit: see which CLI was called

```bash
# All executor calls in JSONL format
cat .dev-factory/runs/<run_id>/execution/execution_calls.jsonl | python -m json.tool

# Codex-specific calls
cat .dev-factory/runs/<run_id>/execution/codex_calls.jsonl

# Claude Code-specific calls
cat .dev-factory/runs/<run_id>/execution/claude_code_calls.jsonl
```

---

## See also

- [Architecture reference](../architecture.md)
- [FAQ — Does it actually call the Codex CLI?](../faq.md)
- [Tutorial 04 — Sprint mode](04-sprint-mode.md)
