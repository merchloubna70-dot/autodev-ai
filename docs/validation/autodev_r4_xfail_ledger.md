# R4 xfail Ledger — Clean

> **xfail before R4: 10 · xfail after R4: 0 · stale xfails: 0**
> All known xfails closed by real code fixes (or by removal of a genuinely stale annotation).

## Closures

| ID | Test | Closed by | Fix |
|---|---|---|---|
| F-01a | `test_denylist_catches_curl_pipe_bash_no_space` | Coverage Cov-G | `_normalize_pipe_whitespace` in `command_safety.py` |
| F-01b | `test_denylist_catches_wget_pipe_bash_no_space` | Coverage Cov-G | same as F-01a |
| F-02 | `test_factory_force_mock_overrides_apply_mode_fail_closed` | Coverage Cov-G | `FactoryConfig.from_env` auto-allows mock |
| F-03 | `test_worker_isolator_rejects_escaped_symlink_in_parent_home` | Coverage Cov-G | stale annotation; R3-H code was already correct |
| TWINE-1..4 | `test_release_workflow_twine_password_policy.py` (×4) | R4-E | release.yml `-p` flag → `TWINE_PASSWORD` env |
| MCP-ENV-PATH | `test_mcp_rejects_path_argument_containing_dot_env` | R4-A | `_validate_safe_path` preflight in 6 MCP handlers |
| MCP-SCHEMA | `test_mcp_tools_call_missing_required_param_returns_error` | R4-D | `_validate_required_params` pre-dispatch in server.py |
| EXEC-REDACT-PYPI | `test_executor_result_does_not_leak_pypi_api_token_in_stderr` | R4-B | `secret_redaction.py` integrated in 3 executors |
| EXEC-REDACT-ANTHROPIC | `test_executor_result_does_not_leak_anthropic_api_key` | R4-B | same as above |
| BRANCH-DOLLAR-PAREN | `test_worker_isolator_branch_name_rejects_dollar_paren` | R4-C | `_validate_branch_name` extended to 11 injection patterns |
| BRANCH-BACKTICK | `test_worker_isolator_branch_name_rejects_backtick` | R4-C | same as above |

## Remaining xfails

**0** — none.

## Invariants Upheld

- No xfail was deleted without a real code fix or genuine stale-annotation cleanup
- No xfail was converted to pass without verifying behavior
- All previously-failing tests now pass under normal pytest run (no xfail decorator)
- Stale xfail count: 0

**Verdict: `ledger_clean_all_known_xfails_closed_by_real_fix`**
