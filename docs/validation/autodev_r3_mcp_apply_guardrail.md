# R3 MCP Apply-Mode Guardrail — Validation Report

## What Changed

Two MCP tools — `autodev_deliver_project` and `autodev_run_issue` — previously accepted `mode="apply"` without any server-side check, allowing any MCP caller to trigger arbitrary code execution (codex/claude in apply mode) on the host.

### Changes to `src/autodev/mcp_server/tools.py`

1. **New guardrail helpers** (`_write_audit_log`, `_check_apply_mode_allowed`) added at module top.
2. **`autodev_deliver_project`**:
   - Added `allow_apply: bool` parameter (schema + handler) defaulting to `False`.
   - Added `commit`, `push`, `tag` parameters all defaulting to `False`.
   - Invalid mode value returns `isError: true` immediately.
   - When `mode="apply"`: both `allow_apply=True` (caller) AND `AUTODEV_MCP_ALLOW_APPLY=1` (server env) required; either missing returns denial response and writes audit log.
3. **`autodev_run_issue`**: identical guardrail logic applied.
4. **Audit log**: on every apply-mode attempt (allowed or denied), a JSON entry is appended to `$AUTODEV_MCP_AUDIT_LOG` (default `/tmp/autodev_mcp_audit.log`) and emitted to stderr. Entry fields: `timestamp`, `tool`, `params` (secrets redacted), `repo_path`, `decision` (`allowed`/`denied`), `reason` (denied only).

No changes to `server.py` — the env var is read directly inside the handler, requiring no glue code.

## Threat Model

| Threat | Before | After |
|---|---|---|
| MCP caller triggers apply mode with no consent | Allowed | Denied (missing `allow_apply` param) |
| Operator deploys server without intending apply | Allowed | Denied (missing `AUTODEV_MCP_ALLOW_APPLY=1`) |
| No evidence of apply attempts in logs | No log | Structured JSON audit log per attempt |
| Accidental commit/push/tag in apply mode | Defaulted to caller input | Default `False`; must explicitly pass `True` |

## ENV Vars

| Variable | Purpose | Required for Apply |
|---|---|---|
| `AUTODEV_MCP_ALLOW_APPLY` | Server-side permit gate; must be `"1"` | Yes |
| `AUTODEV_MCP_AUDIT_LOG` | Override audit log path (default `/tmp/autodev_mcp_audit.log`) | No |

## Test Results

**File**: `tests/integration/test_mcp_apply_guardrail.py`

19 tests, 0 failures:

| # | Test | Result |
|---|---|---|
| 1 | `test_deliver_project_default_mode_is_dry_run` | PASS |
| 2 | `test_run_issue_default_mode_is_dry_run` | PASS |
| 3 | `test_deliver_project_apply_without_allow_apply_denied` | PASS |
| 4 | `test_run_issue_apply_without_allow_apply_denied` | PASS |
| 5 | `test_deliver_project_apply_with_explicit_false_denied` | PASS |
| 6 | `test_deliver_project_apply_no_env_var_denied` | PASS |
| 7 | `test_run_issue_apply_no_env_var_denied` | PASS |
| 8 | `test_env_var_value_zero_not_enough` | PASS |
| 9 | `test_deliver_project_apply_allowed_defaults` | PASS |
| 10 | `test_run_issue_apply_allowed_defaults` | PASS |
| 11 | `test_audit_log_allowed_fields` | PASS |
| 12 | `test_audit_log_denial_no_param` | PASS |
| 13 | `test_audit_log_denial_no_env_var` | PASS |
| 14 | `test_run_issue_apply_only_param_no_env_denied` | PASS |
| 15 | `test_run_issue_apply_only_env_no_param_denied` | PASS |
| 16 | `test_run_issue_apply_both_flags_allowed` | PASS |
| 17 | `test_deliver_project_invalid_mode` | PASS |
| 18 | `test_run_issue_invalid_mode` | PASS |
| 19 | `test_default_audit_log_path_used` | PASS |

Full suite: **1019 passed, 4 xfailed** — no regressions.

mypy `src/autodev/mcp_server`: **0 errors**.

## Caveats

- **Audit log not authenticated**: the log file at `/tmp/autodev_mcp_audit.log` is world-writable by default on most systems. A malicious local process can inject or truncate entries. Mitigation: set `AUTODEV_MCP_AUDIT_LOG` to a path writable only by the server process.
- **Env var is process-level**: `AUTODEV_MCP_ALLOW_APPLY` is read from the server's environment at call time; it does not authenticate the caller identity. Any caller that can reach the MCP endpoint can trigger apply if the server was started with the env var set.
- **No rate-limiting on apply attempts**: repeated denied attempts are logged but not throttled.
- **commit/push/tag defaults are advisory**: the flow implementations do not yet consume these parameters. They are returned in the response for auditability but the underlying flows use their own config. Full enforcement requires plumbing into flow config.

## Verdict

The primary RCE vector (unauthenticated `mode="apply"`) is closed. Both a caller-side explicit opt-in and a server-side environment gate must be satisfied simultaneously. Audit trail is present. Full test suite passes. Residual risk is limited to audit log spoofing on shared hosts and absence of caller authentication — both are documented above and are acceptable for v1.
