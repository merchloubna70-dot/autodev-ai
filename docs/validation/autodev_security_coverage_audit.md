# Security Control Test Coverage Audit

**Round:** security_coverage  
**Audited by:** Cov-C  
**Date:** 2026-05-14  
**Scope:** 13 security controls — positive, negative, bypass-attempt coverage assessment

---

## Summary

| Metric | Count |
|--------|-------|
| Controls audited | 13 |
| Fully covered (no gap) | 4 |
| Gaps found | 9 |
| High-severity gaps | 3 |
| Medium-severity gaps | 2 |
| Low-severity gaps | 4 |

---

## Control-by-Control Results

### 1. A2A SSRF Guard (`A2AHttpSSRFError` / `_validate_url`)
**File:** `tests/unit/test_a2a_http_ssrf_hardening.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | YES |

**Coverage:** 13 tests cover file/ftp scheme rejection, all RFC-1918 ranges, link-local (169.254/8), loopback IPv4/IPv6 literals, DNS-resolves-to-loopback, redirect-to-private blocked (status=0,body=b''), and `allow_private=True` bypass documented.  
**Gap:** none  
**Severity:** info

---

### 2. DNS Rebinding Guard (`_resolve_and_pin_host` / `_PinnedHTTPHandler`)
**File:** `tests/unit/test_a2a_dns_rebinding_hardening.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | YES |

**Coverage:** 10 tests cover IP-pinning TOCTOU prevention (DNS flip from public to private after pin), redirect to private hostname rejected, redirect to public hostname allowed, max_redirects=5 enforced, HTTPS SNI hostname stored correctly, and `allow_private_networks=True` verified to skip `_build_pinned_opener`.  
**Gap:** none  
**Severity:** info

---

### 3. MCP Apply Guardrail (`AUTODEV_MCP_ALLOW_APPLY` + `allow_apply` dual-gate)
**File:** `tests/integration/test_mcp_apply_guardrail.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | YES |

**Coverage:** 9 test classes, 20+ cases. Default dry-run verified; each gate tested in isolation and combined; `AUTODEV_MCP_ALLOW_APPLY=0` denied; audit log fields (timestamp/tool/repo/decision/reason) verified for both allowed and denied paths; invalid mode string rejected; default audit log path fallback tested.  
**Gap:** No test verifies that non-canonical truthy values (e.g., `"yes"`, `"true"`) for the env var are rejected (only `"1"` is allowed).  
**Severity:** low  
**Recommended test:** `test_apply_env_var_non_canonical_truthy_denied`

---

### 4. WorkerIsolator Symlink Escape (`WorkerIsolatorPathEscapeError`)
**File:** `tests/unit/test_worker_isolator_symlink_hardening.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | YES |

**Coverage:** 9 tests covering symlink target outside `parent_home` rejected; pre-placed malicious symlink blocked; cleanup path outside root refused (and target not deleted); valid symlink inside root succeeds; full lifecycle happy path.  
**Gap:** none  
**Severity:** info

---

### 5. WorkerIsolator Branch-Name Validation
**File:** `tests/unit/test_worker_isolator_symlink_hardening.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | YES |

**Coverage:** `..`, bare `..`, `/` in middle, NUL byte all tested.  
**Gap:** No test for branch names with shell metacharacters (`$()`, backtick, `;`) or leading `-` (CLI injection risk if branch name is passed to git subprocess without `--`).  
**Severity:** medium  
**Recommended test:** `test_branch_name_shell_metacharacters_rejected`

---

### 6. CommandSafety Denylist (`DEFAULT_DENYLIST`)
**Files:** `tests/unit/test_shell_safety.py`, `tests/unit/test_executor_boundary_smoke.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | YES (xfail gaps documented) |

**Coverage:** `rm -rf`, `curl | bash` (spaced), `wget | bash` (spaced), `eval`, `sudo`, `--force` covered. Known F-01 gap: `curl|bash` and `wget|bash` WITHOUT spaces bypass the denylist (marked `xfail strict=True` but not fixed). `source .env` and `cat .env` are in `DEFAULT_DENYLIST` but have NO dedicated test verifying they are caught by `is_command_denied()` or `scan_prompt_for_unsafe()`.  
**Gap:** F-01 unfixed bypass; `.env` denylist entries not test-verified.  
**Severity:** HIGH  
**Recommended tests:** `test_denylist_catches_source_env`, `test_denylist_catches_cat_env`, `test_denylist_catches_nospace_pipe_variants`

---

### 7. CODEX_HOME Isolation
**File:** `tests/unit/test_worker_isolator_symlink_hardening.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | YES |

**Coverage:** `test_codex_home_env_outside_worktree_root_raises()` directly tests `CODEX_HOME` env override pointing outside narrow `worktree_root`. Raises `WorkerIsolatorPathEscapeError` with `"CODEX_HOME"` in the message. Happy-path lifecycle also verified.  
**Gap:** none  
**Severity:** info

---

### 8. Mock vs Real Executor Distinction
**Files:** `tests/unit/test_mocks_and_executors.py`, `tests/unit/test_sandboxed_executor.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | NO |

**Coverage:** Mock executors assert `mock_used=True`. `SandboxedExecutor` inherits `is_mock` from inner. Real executors (`ClaudeCodeExecutor`, `CodexCliExecutor`) have `is_mock = False` in source — verified by inspection — but no test explicitly asserts `ClaudeCodeExecutor().is_mock is False`. No test attempts to spoof a real executor as mock and verifies the router catches it.  
**Gap:** No assertion on `is_mock=False` for real executors; no bypass test.  
**Severity:** medium  
**Recommended tests:** `test_real_executors_have_is_mock_false`, `test_router_rejects_spoofed_mock_executor`

---

### 9. Token Leakage Avoidance (Runtime Redaction)
**File:** `tests/unit/test_release_workflow_policy.py` (workflow policy only, not runtime)

| | |
|-|-|
| Positive test | NO |
| Negative test | NO |
| Bypass-attempt test | NO |

**Coverage:** `test_pypi_upload_gated_on_secret()` verifies the CI workflow gates the upload step on the `PYPI_API_TOKEN` secret being present — this is a workflow policy test, not a runtime redaction test. No test verifies that `PYPI_API_TOKEN`, `ANTHROPIC_API_KEY`, or any other secret value is scrubbed from executor result `stderr`, MCP response content, or exception messages at runtime.  
**Gap:** Zero runtime token redaction tests. Secrets could leak in log output, tracebacks, or MCP `content` fields.  
**Severity:** HIGH  
**Recommended tests:** `test_executor_result_scrubs_env_token_from_stderr`, `test_mcp_response_does_not_contain_secret_value`

---

### 10. Temporary Directory Cleanup
**File:** `tests/unit/test_worker_isolator_symlink_hardening.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | NO |

**Coverage:** `test_happy_path_full_lifecycle()` verifies `cleanup_worktree` removes `worker_home`. `test_cleanup_nonexistent_path_is_idempotent()` is a no-op on missing paths. `test_cleanup_outside_root_raises()` confirms boundary is not crossed. No test verifies cleanup occurs when `prepare_codex_home` raises mid-way (exception-safety / finally path).  
**Gap:** No exception-path cleanup test.  
**Severity:** low  
**Recommended test:** `test_cleanup_called_on_prepare_exception`

---

### 11. `.env` / Secret Path Denial in MCP/CLI
**File:** None dedicated

| | |
|-|-|
| Positive test | NO |
| Negative test | NO |
| Bypass-attempt test | NO |

**Coverage:** `DEFAULT_DENYLIST` in `src/autodev/utils/command_safety.py` contains `"source .env"` and `"cat .env"`, but no test in the suite explicitly calls `is_command_denied("source .env")` or `is_command_denied("cat .env")` to assert they are blocked. No test verifies MCP tool arguments containing `.env` or `/etc/passwd` paths are rejected.  
**Gap:** Denylist entries for secret file access exist in source but are entirely untested.  
**Severity:** HIGH  
**Recommended tests:** `test_denylist_catches_source_env`, `test_denylist_catches_cat_env`, `test_mcp_rejects_secret_file_path_arg`

---

### 12. Docker Digest Pin Check
**File:** `tests/unit/test_docker_digest_pinning.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | NO |

**Coverage:** 6 tests: `Dockerfile` exists, all `FROM` lines contain `@sha256:`, digest is 64 hex chars, `UPDATE.md` exists and mentions `"digest"`, both builder and runtime stages use the same digest, no floating `python:3.12-slim` tag.  
**Gap:** No test that provides a deliberately malformed Dockerfile (floating tag) to verify the assertion logic itself would catch it.  
**Severity:** low  
**Recommended test:** `test_floating_tag_dockerfile_fails_digest_check`

---

### 13. Release Workflow Pytest Gate
**File:** `tests/unit/test_release_workflow_policy.py`

| | |
|-|-|
| Positive test | YES |
| Negative test | YES |
| Bypass-attempt test | NO |

**Coverage:** 7 tests: workflow file exists, valid YAML, contains `pytest` step, `publish` needs `test`, no `if: false` bypass shortcuts, PyPI upload gated on `PYPI_API_TOKEN`, test job includes `ruff` and `mypy`.  
**Gap:** No test verifies a workflow with `needs: []` (empty) or `needs: build` (missing `test`) fails the `needs: test` assertion — the check logic is not itself regression-tested against adversarial inputs.  
**Severity:** low  
**Recommended test:** `test_workflow_without_test_dependency_fails_needs_check`

---

## Top 3 Security Gaps for Phase 2 (Cov-H)

### Gap 1 — HIGH: CommandSafety Denylist No-Space Pipe Bypass + Untested .env Entries (Controls 6 & 11)
`curl|bash` and `wget|bash` without spaces bypass `DEFAULT_DENYLIST` (documented as `xfail strict=True` in F-01 but not fixed). Additionally, `source .env` and `cat .env` are in the denylist but have no test asserting they are caught. Phase 2 must: (a) fix no-space normalization in `scan_prompt_for_unsafe`, and (b) add explicit tests for all `.env`-related denylist entries.

### Gap 2 — HIGH: Zero Runtime Token Redaction Tests (Control 9)
No test verifies that `PYPI_API_TOKEN`, `ANTHROPIC_API_KEY`, or any environment secret is redacted from executor `stderr`, MCP `content`, or exception messages at runtime. This is a blind spot: a prompt injection or subprocess error could expose secrets to calling clients without any test catching it. Phase 2 must add redaction smoke tests for all secret-shaped env vars.

### Gap 3 — HIGH: `.env` / Secret File Path Denial Untested End-to-End (Control 11)
Although `DEFAULT_DENYLIST` contains `"source .env"` and `"cat .env"`, these entries have zero test coverage — no unit test calls `is_command_denied("source .env")` and no integration test verifies the MCP layer rejects a tool argument containing a secret file path. If the denylist were accidentally truncated during a refactor, no test would catch the regression.
