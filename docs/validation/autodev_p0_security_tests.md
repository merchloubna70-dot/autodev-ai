# P0 Security Test Expansion — Cov-H (Phase 2)

**Round:** coverage-phase-2  
**Agent:** Cov-H  
**Date:** 2026-05-14  
**File:** `tests/integration/test_security_p0_coverage.py`  
**Scope:** Build on R3-B's 19 MCP guardrail tests; add coverage for gaps identified by Cov-C

---

## Summary

| Metric | Value |
|--------|-------|
| Tests added | 14 |
| Passed | 9 |
| Xfailed (as intended) | 5 |
| Unexpected failures | 0 |
| Full suite (post-add) | 1178 passed, 10 xfailed, 0 failed |
| Regressions | 0 |

---

## Test Groups

### Group A — Audit Log Path (2 tests, 2 PASS)

| Test | Result | Notes |
|------|--------|-------|
| `test_mcp_audit_log_default_path_is_under_tmp` | PASS | Documents world-writable risk of `/tmp/autodev_mcp_audit.log` |
| `test_mcp_audit_log_overridable_via_env` | PASS | `AUTODEV_MCP_AUDIT_LOG` env var redirects writes correctly |

**Security gaps closed:** The `/tmp` placement risk is now documented in the test suite. The overridability is verified.

---

### Group B — Denylist Completeness (4 tests, 4 PASS)

| Test | Result | Notes |
|------|--------|-------|
| `test_denylist_catches_cat_env` | PASS | `cat .env` denied by DEFAULT_DENYLIST |
| `test_denylist_catches_source_env` | PASS | `source .env` denied |
| `test_denylist_catches_printenv` | PASS | `printenv` denied |
| `test_denylist_catches_printenv_with_args` | PASS | `printenv PATH` denied (substring match) |

**Security gaps closed:** All three Cov-C-identified denylist patterns verified.

---

### Group C — MCP Path-arg .env Denial (1 test, 1 XFAIL)

| Test | Result | Notes |
|------|--------|-------|
| `test_mcp_rejects_path_argument_containing_dot_env` | XFAIL (strict) | Guard not yet implemented — tracked for R4 |

**Gap remains:** MCP handlers accept any `repo_path` value including `.env` paths without sanitisation. An attacker controlling the MCP call arguments could supply `/repo/.env` as repo_path.

---

### Group D — Executor Secret Scrubbing (2 tests, 2 XFAIL)

| Test | Result | Notes |
|------|--------|-------|
| `test_executor_result_does_not_leak_pypi_api_token_in_stderr` | XFAIL (strict) | No output scrubbing exists — tracked for R4 |
| `test_executor_result_does_not_leak_anthropic_api_key` | XFAIL (strict) | Same root cause — tracked for R4 |

**Gap remains:** `ClaudeCodeExecutor` and `CodexCliExecutor` pass `request.env` directly to `subprocess.run()` with no post-processing of stdout/stderr. If the subprocess echoes environment variables in error output, secrets appear verbatim in `ExecutionResult.stderr`. Remediation: scrub known secret env-var values from executor output before returning.

---

### Group E — Executor is_mock Attribute (3 tests, 3 PASS)

| Test | Result | Notes |
|------|--------|-------|
| `test_claude_code_executor_is_mock_is_false` | PASS | `ClaudeCodeExecutor.is_mock == False` confirmed |
| `test_codex_executor_is_mock_is_false` | PASS | `CodexCliExecutor.is_mock == False` confirmed |
| `test_mock_executor_is_mock_is_true` | PASS | `MockClaudeExecutor.is_mock == True` confirmed |

**Security gaps closed:** Real vs mock executor discrimination is now tested. Prevents a misconfiguration where a mock executor silently replaces a real one in production.

---

### Group F — WorkerIsolator Branch Name Shell Injection (2 tests, 2 XFAIL)

| Test | Result | Notes |
|------|--------|-------|
| `test_worker_isolator_branch_name_rejects_dollar_paren` | XFAIL (strict) | `feat$(whoami)` not rejected — tracked for R4 |
| `test_worker_isolator_branch_name_rejects_backtick` | XFAIL (strict) | `` feat`whoami` `` not rejected — tracked for R4 |

**Gap remains:** `_validate_branch_name` only rejects NUL bytes, `/`, and `..` sequences. Shell meta-characters `$(` and backtick pass through silently. If such a branch name reaches a shell-interpolated git command, substitution could execute. Fix: add `$` and backtick to the rejected character set.

Note: `feat$(rm -rf /)` IS incidentally caught because it contains `/`. The gap only applies to $() expressions without a slash component (e.g. `feat$(whoami)`) and backtick forms.

---

## Production Code Changes

None. All `is_mock` attributes were already present on the executor classes (`ClaudeCodeExecutor.is_mock = False`, `CodexCliExecutor.is_mock = False`, `MockClaudeExecutor.is_mock = True`, `MockCodexExecutor.is_mock = True`). No src/ modifications were required.

---

## R4 Tracked Gaps

| Gap | File | Priority |
|-----|------|----------|
| MCP path-arg .env denial | `autodev/mcp_server/tools.py` | P1 |
| Executor output secret scrubbing | `autodev/executors/base_executor.py` or each executor | P1 |
| Branch name `$(` rejection | `autodev/executors/worker_isolator.py:_validate_branch_name` | P1 |
| Branch name backtick rejection | same | P1 |
| Audit log world-writable path | `autodev/mcp_server/tools.py:_DEFAULT_AUDIT_LOG` | P2 |
