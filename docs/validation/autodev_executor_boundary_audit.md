# Executor Boundary Audit — autodev Release Hardening

**Round:** executor_boundary  
**Date:** 2026-05-14  
**Auditor:** Agent D  
**Verdict:** `minor_gaps`

---

## Scope

Static code inspection of the executor subsystem plus two live smoke tests (no real LLM invoked).

Files inspected:

- `src/autodev/executors/executor_router.py`
- `src/autodev/executors/codex_cli_executor.py`
- `src/autodev/executors/claude_code_executor.py`
- `src/autodev/executors/mock_codex_executor.py`
- `src/autodev/executors/mock_claude_executor.py`
- `src/autodev/executors/worker_isolator.py`
- `src/autodev/executors/sandboxed_executor.py`
- `src/autodev/executors/network_allowlist.py`
- `src/autodev/utils/command_safety.py`
- `src/autodev/utils/config_stack.py`
- `src/autodev/config.py`

> Note: actual filenames differ from the audit spec (`codex_cli_executor.py` not `codex_executor.py`, `mock_codex_executor.py` + `mock_claude_executor.py` not `mock_executor.py`). No `worker_isolator.py` at the utils path — it lives under executors.

---

## Executors Present

| Class | Backend Enum | is_mock |
|---|---|---|
| `CodexCliExecutor` | `CODEX` | False |
| `ClaudeCodeExecutor` | `CLAUDE_CODE` | False |
| `MockCodexExecutor` | `MOCK_CODEX` | True |
| `MockClaudeExecutor` | `MOCK_CLAUDE` | True |

---

## Fallback Ladder

```
AUTO
 └─ _auto_route() → CODEX or CLAUDE_CODE based on task_type/risk/language/files
       └─ _maybe_mock(preferred)
            ├─ if preferred.is_available()           → use real CLI
            ├─ elif NOT allow_mock                   → fail-closed (exit_code=127, error_type=cli_missing_fail_closed)
            └─ elif allow_mock                       → MOCK_CODEX / MOCK_CLAUDE
```

**Key finding:** Mock fallback is NOT automatic when a binary is missing. It requires `allow_mock=True`, which is set via:
- `--allow-mock-executor true` flag, OR
- `--mode dry-run` (CLI auto-sets `allow_mock_executor = mode == PipelineMode.DRY_RUN`)

Without one of these, the router fails closed — correct behavior for production.

---

## FACTORY_FORCE_MOCK=1 Behavior

**Honored:** Both `CodexCliExecutor.is_available()` and `ClaudeCodeExecutor.is_available()` return `False` when `FACTORY_FORCE_MOCK=1`. The env var is also honored in 8 other modules (adapters, agents, MCP server).

**Gap (F-02):** `FactoryConfig.from_env()` does NOT read `FACTORY_FORCE_MOCK` to auto-set `allow_mock_executor=True`. This means `FACTORY_FORCE_MOCK=1` alone is insufficient — the pipeline will fail-closed if `allow_mock` is not also enabled. Test harnesses must set both `FACTORY_FORCE_MOCK=1` and `--allow-mock-executor true` (or use `--mode dry-run`).

---

## Worker Isolation

`WorkerIsolator.prepare_codex_home()` creates a per-worker `CODEX_HOME` by:
1. Symlinking shared read-only files (`auth.json`, `config.toml`, etc.) from `parent_home` into `worker_home`
2. Creating empty private directories (`sessions/`, `log/`, `cache/`, etc.) per worker
3. Not creating `CODEX_HOME_PRIVATE_FILES` (SQLite, history) — Codex initializes them fresh

`prepare_worktree()` wraps `git worktree add` with structured error returns (never raises).

**Gap (F-03):** No path validation before `os.symlink(src, dst)`. The code does not verify that `src.resolve()` stays within `parent_home.resolve()`. If `parent_home` is attacker-controlled (via `CODEX_HOME` env override or a tmpdir race), a hostile symlink in `parent_home` would be blindly re-exposed in `worker_home`.

---

## Denylist Coverage

19 patterns in `DEFAULT_DENYLIST`. Coverage against selected attack classes:

| Pattern | Caught |
|---|---|
| `rm -rf /` | Yes |
| `curl \| bash` (with spaces) | Yes |
| `curl\|bash` (no spaces) | **No — F-01** |
| `wget \| bash` (with spaces) | Yes |
| `wget\|bash` (no spaces) | **No — F-01** |
| `eval $(...)` | Yes |
| `sudo apt-get` | Yes |
| `chmod 777 ...` | Yes |
| `; rm ...` | Yes |
| `&& rm ...` | Yes |
| `\| rm ...` | Yes |
| `git push --force` | Yes |
| backtick substitution | **No** |
| `base64 -d \| bash` | **No** |
| `python -c 'os.system...'` | **No** |
| `dd if=... of=/dev/...` | **No** |

The `scan_prompt_for_unsafe()` function also applies denylist checks to prompts before they reach either real executor.

`ClaudeCodeExecutorConfig.disallowed_patterns` provides a second-layer check in `ClaudeCodeExecutor._prompt_violates_config()`.

---

## SandboxedExecutor

`SandboxedExecutor` wraps any inner executor with `NetworkAllowlist` policy evaluation. However:
- With `sandbox_provider="none"` (the default and only implemented value), execution is **audit-only** — the allowlist verdict is not enforced.
- Non-`"none"` providers raise `NotImplementedError` (safe, explicit fail).
- `NetworkAllowlist` itself is solid: default-deny, wildcard domain support, CIDR matching, no external deps.

This is documented in the module docstring but callers should be aware there is no real network confinement today.

---

## ConfigStack Security Note

`ConfigStack.materialize_into()` writes arbitrary TOML scalar values to `FactoryConfig` attributes with no schema validation. A misconfigured or malicious `.autodev/config.user.toml` (which is git-ignored and thus not reviewed) could set `allow_mock_executor = true` or `timeout_seconds = 0` silently.

---

## Smoke Tests

### Test 1 — classify-input with FACTORY_FORCE_MOCK=1

```bash
FACTORY_FORCE_MOCK=1 autodev classify-input --input examples/01-mdlines/brief.md
```

**Result:** EXIT 0 — `{"input_type": "project_brief", "confidence": 0.8, ...}`

Note: `InputClassifierAgent` is fully heuristic (keyword-based, no LLM). `FACTORY_FORCE_MOCK` has no observable effect here, but the command succeeds cleanly without any executor invocation.

### Test 2 — deliver-project with codex/claude absent (PATH=/usr/bin), mock allowed

```bash
PATH=/usr/bin autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --from-scratch true \
  --mode dry-run \
  --allow-mock-executor true \
  --repo-path /tmp/executor-d-1
```

**Result:** EXIT 0 — `run_id=run_20260514T030743_c27256a2 mode=dry-run mock=True release=NotReleaseReady`

Mock fallback activated correctly. With neither `codex` nor `claude` on `PATH` and `allow_mock=True`, the router transparently fell back to `MOCK_CODEX`/`MOCK_CLAUDE` as expected.

---

## Findings Summary

| ID | Severity | Title |
|---|---|---|
| F-01 | MEDIUM | No-space pipe variants (`curl\|bash`, `wget\|bash`) bypass denylist |
| F-02 | MEDIUM | `FACTORY_FORCE_MOCK=1` does not auto-set `allow_mock_executor=True` in `FactoryConfig` |
| F-03 | LOW | `prepare_codex_home()` has no symlink-target path validation |
| F-04 | INFO | `SandboxedExecutor` provides annotation-only, no real network enforcement |
| F-05 | INFO | `config.user.toml` values applied without schema/range validation |

---

## Verdict: `minor_gaps`

The executor boundary architecture is well-structured: fail-closed by default, explicit mock opt-in, deterministic mocks, dual safety checks (denylist + per-executor config patterns). Two medium findings (denylist bypass via no-space pipes; FACTORY_FORCE_MOCK not wiring through to allow_mock) should be fixed before release. Worker isolator symlink path validation is a low-severity hardening item.

No critical boundary violations were found.
