# autodev Test Coverage Baseline

**Round:** test_coverage_baseline  
**Date:** 2026-05-14  
**Source of truth:** `coverage.json` (branch coverage enabled, pre-existing run)

---

## Overall Coverage

| Metric | Value |
|---|---|
| Line coverage (statements) | **81%** (8,830 / 10,884 statements hit) |
| Combined line+branch (percent_covered) | **79%** |
| Missing statements | 2,054 |
| Branches total | 3,018 |
| Partial branches | 492 |
| Branch coverage | 70% |
| Total tests | **1,062 passed, 4 xfailed, 0 skipped** |

---

## Zero-Coverage Files (19 files)

All are either optional-dep-gated or an untested thin shim:

| File | Reason |
|---|---|
| `src/autodev/release_readiness_gate.py` | Thin shim (13 stmts) — no test imports it; delegates to `scripts/` |
| `src/autodev/tasks/__init__.py` | crewai optional dep not installed |
| `src/autodev/tasks/architecture_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/commit_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/documentation_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/implementation_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/input_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/issue_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/milestone_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/product_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/quality_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/release_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/requirement_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/review_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/security_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/test_tasks.py` | crewai optional dep not installed |
| `src/autodev/tasks/verification_tasks.py` | crewai optional dep not installed |
| `src/autodev/tui/dashboard.py` | textual optional dep not installed |
| `src/autodev/tui/widgets.py` | textual optional dep not installed |

---

## Top 10 Lowest-Coverage Non-Gated Files

| File | Coverage |
|---|---|
| `src/autodev/adapters/a2a/handlers.py` | 14.7% |
| `src/autodev/adapters/git_adapter.py` | 25.4% |
| `src/autodev/flows/project_delivery_crewflow.py` | 39.1% |
| `src/autodev/flows/issue_pipeline_crewflow.py` | 42.6% |
| `src/autodev/adapters/filesystem_adapter.py` | 43.8% |
| `src/autodev/adapters/mcp_client.py` | 44.3% |
| `src/autodev/cli.py` | 46.2% |
| `src/autodev/context_providers/search_provider.py` | 48.6% |
| `src/autodev/gates/post_edit_lint_gate.py` | 49.5% |
| `src/autodev/adapters/github_adapter.py` | 50.5% |

16 files total are below 60%. 40 files total are below 80% (excluding gated).

---

## Critical Uncovered Modules (below 80%)

| File | Coverage | Category |
|---|---|---|
| `src/autodev/release_readiness_gate.py` | 0.0% | release |
| `src/autodev/cli.py` | 46.2% | protocol |
| `src/autodev/flows/replay_flow.py` | 57.0% | release |
| `src/autodev/mcp_server/server.py` | 64.5% | protocol |
| `src/autodev/mcp_server/tools.py` | 75.7% | protocol |
| `src/autodev/adapters/a2a/transports/http.py` | 76.8% | protocol |

Critical modules at or above 80%: `command_safety.py` (93.2%), `a2a/server.py` (85.4%), `executor_router.py` (87.3%), `worker_isolator.py` (89.2%), `a2a/client.py` (97.1%), `release_flow.py` (100%), `milestone_flow.py` (100%).

---

## xfail Tests (4)

All 4 are in `tests/unit/test_executor_boundary_smoke.py`, documenting confirmed gaps from the executor boundary audit:

| Test | Reason |
|---|---|
| `test_denylist_catches_curl_pipe_bash_no_space` | F-01: denylist misses `curl\|bash` (no spaces) |
| `test_denylist_catches_wget_pipe_bash_no_space` | F-01: denylist misses `wget\|bash` (no spaces) |
| `test_factory_force_mock_overrides_apply_mode_fail_closed` | F-02: `FACTORY_FORCE_MOCK=1` does not override `allow_mock_executor` in apply mode |
| `test_worker_isolator_rejects_escaped_symlink_in_parent_home` | F-03: `prepare_codex_home()` does not validate symlink targets stay within `parent_home` |

---

## Top 5 Slowest Tests

| Test | Duration |
|---|---|
| `test_wheel_installs_in_clean_venv` (setup) | 7.22s |
| `test_send_task_unreachable_returns_failed` | 3.09s |
| `test_blocking_mode_timeout` | 1.01s |
| `test_investigate_prose_description` | 0.93s |
| `test_get_task_events_sse` | 0.89s |

Full top-10 is in the JSON companion file.

---

## Verdict

**baseline_recorded**

The suite is green (1,062 passed, 4 xfailed as expected). Line coverage is 81%; combined line+branch is 79%. The 4 xfails are intentional defect markers (F-01 denylist gap, F-02 mock override gap, F-03 symlink path-escape gap) and must remain xfail until the underlying issues are fixed. Six critical-path modules remain below 80% and are the primary targets for the next coverage improvement round: `cli.py` (46%), `mcp_server/server.py` (65%), `flows/replay_flow.py` (57%), `mcp_server/tools.py` (76%), `a2a/transports/http.py` (77%), and `release_readiness_gate.py` (0%).
