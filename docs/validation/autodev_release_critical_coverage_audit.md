# Release-Critical Coverage Audit — Cov-B Phase 1

**Date:** 2026-05-14  
**Agent:** Cov-B  
**Status:** BLOCK_RELEASE — 5 high-risk modules with critical gaps identified

---

## Summary

18 modules audited across CLI, flows, executors, MCP, A2A adapters, and utilities.

| Risk     | Count |
|----------|-------|
| High     | 5     |
| Medium   | 8     |
| Low      | 5     |

---

## Top 5 Highest-Risk Modules

| Rank | Module | Coverage | Priority |
|------|--------|----------|----------|
| 1 | `src/autodev/release_readiness_gate.py` | **0.0%** (13/13 stmts missing) | P0 |
| 2 | `scripts/release_readiness_gate.py` | **absent from coverage.json** (36-check script never instrumented) | P0 |
| 3 | `src/autodev/executors/claude_code_executor.py` | **59.5%** (key failure branches: FileNotFoundError, Timeout, JSONL parse) | P0 |
| 4 | `src/autodev/flows/replay_flow.py` | **57.0%** (58 stmts missing; fine-grained resume + 4/8 stages uncovered) | P0 |
| 5 | `src/autodev/cli.py` | **46.2%** (242/466 stmts missing; 8 commands partially or fully uncovered) | P0 |

---

## P0 Release-Critical Gaps for Phase 2 (Cov-G)

### Gap 1 — `release_readiness_gate.py` shim + script: 0% / absent

`src/autodev/release_readiness_gate.py` has **zero executed statements** despite an existing test file referencing it. The `_load()` function and `__main__` guard are completely untested. More critically, `scripts/release_readiness_gate.py` — which contains all 36 release-gate check functions — is **not included in coverage collection at all**. This means the primary release decision engine has no coverage evidence. Phase 2 must add the script to `.coveragerc` sources and write tests for `_load()`, the `ImportError` paths, and key gate checks (strict-rc, --include-r2, --include-r3, check_no_dangerous_release_claims, build_report aggregation).

### Gap 2 — `claude_code_executor.py`: 59.5%, missing all error branches

The `ClaudeCodeExecutor` is the only real-world executor for Claude Code CLI tasks. The uncovered 40% includes: `FileNotFoundError` (returns exit 127), `TimeoutExpired` (returns exit 124), `FACTORY_FORCE_MOCK=1` disabling `is_available()`, `_prompt_violates_config()` disallowed-patterns enforcement, and `_parse_claude_inner_steps()` returning `[]` for non-JSONL output (legacy claude binary). All of these are error branches that matter at runtime. Phase 2 must patch `subprocess.run` and `shutil.which` to drive all branches; `FACTORY_FORCE_MOCK` env must be set/unset in fixtures.

### Gap 3 — `cli.py` + `replay_flow.py`: 46% / 57%, major command and stage paths dark

`cli.py` has 242 missing statements across commands including `run-issue`, `deliver-project` (with `--style prfaq` and `--scale` validation), `execute-milestone`, `replay`, and `plan-tasks`. The `deliver_project` invalid-scale exit-1 path and `_parse_tri_bool` edge cases are untested. `replay_flow.py` misses the entire fine-grained `from_step` branch (lines 66-112) and 4 of 8 coarse stages (`quality`, `verification`, `release`, `implementation`), plus all `ValueError` guards for missing state. Phase 2 should use `typer.testing.CliRunner` for CLI and a stubbed `RunState` with temp directories for ReplayFlow.

---

## Module Detail

### `src/autodev/cli.py` — 46.2% (P0 / High)

**Existing tests:** 10 integration test files, 1 unit file.  
Many tests invoke `--help` or single commands in smoke mode; the full command bodies with mock executors are not traversed.

**Recommended tests (Phase 2):**
- `test_cli_deliver_project_unknown_scale_exits_1`
- `test_cli_run_issue_with_issue_file_mock_mode`
- `test_cli_replay_from_step_resumes_correct_step`
- `test_cli_parse_tri_bool_all_edge_cases`
- `test_cli_create_prd_with_prfaq_style_writes_correct_sections`
- `test_cli_version_callback_prints_and_exits`

---

### `src/autodev/release_readiness_gate.py` — 0.0% (P0 / High)

**Existing tests:** `tests/unit/test_release_readiness_gate.py` (exists but not exercising this shim).

**Recommended tests (Phase 2):**
- `test_release_readiness_gate_shim_load_calls_main`
- `test_release_readiness_gate_shim_missing_script_raises_import_error`
- `test_release_readiness_gate_shim_none_loader_raises_import_error`
- `test_release_readiness_gate_module_main_guard_invokes_load`

---

### `scripts/release_readiness_gate.py` — NOT IN COVERAGE (P0 / High)

**Recommended tests (Phase 2):**
- `test_rrgate_main_strict_exits_1_on_failure`
- `test_rrgate_build_report_counts_all_36_checks`
- `test_rrgate_check_no_dangerous_release_claims_detects_forbidden`
- `test_rrgate_mock_executor_works_with_force_mock_env`
- `test_rrgate_run_timeout_returns_minus_one`
- `test_rrgate_strict_rc_excludes_homebrew_publish_checks`

---

### `src/autodev/executors/claude_code_executor.py` — 59.5% (P0 / High)

**Existing tests:** `tests/unit/test_executor_boundary_smoke.py`, `tests/unit/test_mocks_and_executors.py`.

**Recommended tests (Phase 2):**
- `test_claude_executor_file_not_found_returns_127`
- `test_claude_executor_timeout_returns_124`
- `test_claude_executor_factory_force_mock_disables_availability`
- `test_claude_executor_unsafe_prompt_rejected_before_subprocess`
- `test_parse_claude_inner_steps_returns_empty_on_non_jsonl`
- `test_claude_executor_disallowed_pattern_in_config_blocks_execution`

---

### `src/autodev/flows/replay_flow.py` — 57.0% (P0 / High)

**Existing tests:** `tests/unit/test_replay_flow.py`, `tests/integration/test_project_delivery_microfile.py`.

**Recommended tests (Phase 2):**
- `test_replay_flow_unknown_stage_raises_value_error`
- `test_replay_flow_planning_without_architecture_raises_value_error`
- `test_replay_flow_from_step_resumes_at_correct_step`
- `test_replay_flow_quality_stage_skips_earlier_stages`
- `test_replay_flow_from_stage_classification_full_run`
- `test_replay_flow_implementation_without_milestone_plan_raises`

---

### `src/autodev/mcp_server/server.py` — 64.5% (P1 / Medium)

**Recommended tests (Phase 2):**
- `test_mcp_server_handle_invalid_json_returns_parse_error`
- `test_mcp_server_tools_call_unknown_tool_returns_method_not_found`
- `test_mcp_server_tools_call_exception_returns_is_error_true`
- `test_mcp_server_handle_notification_returns_none`
- `test_mcp_server_run_processes_sequential_requests`
- `test_mcp_server_unknown_method_returns_32601`

---

### `src/autodev/mcp_server/tools.py` — 75.7% (P1 / Medium)

**Recommended tests (Phase 2):**
- `test_mcp_tools_apply_guardrail_blocks_when_env_not_set`
- `test_mcp_tools_apply_guardrail_blocks_when_allow_apply_false`
- `test_mcp_tools_get_tools_returns_valid_schemas`
- `test_mcp_tools_run_issue_handler_dry_run_returns_json`
- `test_mcp_tools_dual_gate_env_false_blocks_even_if_param_true`

---

### `src/autodev/adapters/a2a/transports/http.py` — 76.8% (P1 / Medium)

**Recommended tests (Phase 2):**
- `test_a2a_http_ssrf_link_local_raises_ssrf_error`
- `test_a2a_http_dns_rebinding_second_resolve_private_rejected`
- `test_a2a_http_transport_send_task_happy_path`
- `test_a2a_http_ssrf_ipv6_loopback_rejected`
- `test_a2a_http_timeout_propagates_correctly`

---

### `src/autodev/adapters/a2a/server.py` — 85.4% (P1 / Medium)

**Recommended tests (Phase 2):**
- `test_a2a_server_executor_exception_returns_error_response`
- `test_a2a_server_malformed_jsonrpc_request_returns_parse_error`
- `test_a2a_server_unknown_task_id_returns_not_found`
- `test_a2a_server_concurrent_tasks_no_race_condition`

---

### `src/autodev/executors/executor_router.py` — 87.3% (P1 / Medium)

**Recommended tests (Phase 2):**
- `test_executor_router_fail_closed_when_no_real_executor_and_no_mock`
- `test_executor_router_selects_claude_for_critical_risk`
- `test_executor_router_fallback_codex_to_claude_when_codex_unavailable`
- `test_executor_router_mock_never_selected_when_allow_mock_false`

---

### `src/autodev/executors/codex_cli_executor.py` — 82.6% (P1 / Medium)

**Recommended tests (Phase 2):**
- `test_codex_executor_file_not_found_returns_127`
- `test_codex_executor_timeout_returns_124`
- `test_codex_executor_unsafe_prompt_rejected`
- `test_codex_executor_disallowed_pattern_blocks_execution`
- `test_codex_executor_apply_mode_returns_changed_files`

---

### `src/autodev/executors/worker_isolator.py` — 89.2% (P1 / Medium)

**Recommended tests (Phase 2):**
- `test_worker_isolator_nested_symlink_escape_raises_error`
- `test_worker_isolator_absolute_symlink_outside_sandbox_raises_error`
- `test_worker_isolator_cleanup_handles_oserror`
- `test_worker_isolator_run_executes_in_temp_dir`

---

### `src/autodev/utils/config_stack.py` — 82.9% (P1 / Medium)

**Recommended tests (Phase 2):**
- `test_config_stack_tomllib_none_returns_empty`
- `test_config_stack_malformed_toml_handled_gracefully`
- `test_config_stack_deep_merge_aot_duplicate_code_key`
- `test_config_stack_four_layer_priority_order`

---

### Low-Risk / Well-Covered Modules (No Action Required in Phase 2)

| Module | Coverage | Notes |
|--------|----------|-------|
| `src/autodev/adapters/a2a/client.py` | 97.1% | Effectively full coverage |
| `src/autodev/executors/mock_executor.py` (mock_claude) | 78.4% | Non-critical mock; mock_codex at 100% |
| `src/autodev/utils/command_safety.py` | 93.2% | 2 minor edge paths missing |
| `src/autodev/flows/release_flow.py` | 100.0% | Complete |
| `src/autodev/flows/milestone_flow.py` | 100.0% | Complete |

---

## Verdict

**BLOCK_RELEASE.** Four P0 modules (cli.py at 46%, claude_code_executor.py at 60%, replay_flow.py at 57%, release_readiness_gate shim at 0%) must reach at least 80% before a PyPI release tag is applied. The scripts/release_readiness_gate.py exclusion from coverage collection is itself a process defect that must be corrected in `pyproject.toml` / `.coveragerc` as a prerequisite for Phase 2.
