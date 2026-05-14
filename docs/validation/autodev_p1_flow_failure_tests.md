# Coverage Round Phase 2 — P1 Flow Failure Tests

**Agent**: Cov-J  
**Date**: 2026-05-14  
**Status**: PASS — 18/18 new tests pass, 0 regressions

---

## New Test Files

### 1. `tests/unit/test_investigation_flow.py` — 4 tests, 4 passed

Flow under test: `src/autodev/flows/investigation_flow.py`

Real call shape investigated:
- `InvestigationFlow()` — instantiates `InvestigatorAgent()` as `self.agent`
- `InvestigationFlow.run(inp: InvestigationInput) -> CaseFile`
- `InvestigationInput(input_token: str, repo_path: str = ".")`
- The agent writes `<repo_path>/.dev-factory/investigations/<slug>.md` and sets `CaseFile.file_path`

Tests:
| Test | Result |
|---|---|
| `test_investigation_flow_initialization` | PASS |
| `test_investigation_flow_happy_path_with_minimal_input` | PASS |
| `test_investigation_flow_state_dir_created_under_run` | PASS |
| `test_investigation_flow_missing_evidence_handled` | PASS |

---

### 2. `tests/unit/test_brownfield_doc_flow.py` — 4 tests, 4 passed

Flow under test: `src/autodev/flows/brownfield_doc_flow.py`

Real call shape investigated:
- `BrownfieldDocFlow()` — instantiates `DocumentProjectAgent()` as `self._agent`
- `BrownfieldDocFlow.run(inp: BrownfieldDocInput) -> BrownfieldDoc`
- `BrownfieldDocInput(repo_path: str = ".", languages: list[Language] = [])`
- Note: `languages=None` is NOT valid (pydantic list field); `languages=[]` is the correct empty form
- Always produces exactly 7 sections under `<repo_path>/.autodev/brownfield-docs/`

Tests:
| Test | Result |
|---|---|
| `test_brownfield_doc_flow_initialization` | PASS |
| `test_brownfield_doc_flow_happy_path_python` | PASS |
| `test_brownfield_doc_flow_languages_none_passthrough` | PASS |
| `test_brownfield_doc_flow_output_dir_writable` | PASS |

---

### 3. `tests/unit/test_project_context_flow.py` — 4 tests, 4 passed

Flow under test: `src/autodev/flows/project_context_flow.py`

Real call shape investigated:
- `ProjectContextFlow()` — instantiates `ContextGeneratorAgent()` as `self._agent`
- `ProjectContextFlow.run(inputs: ProjectContextInput) -> ProjectContext`
- `ProjectContextInput(repo_path: str = ".", product_name: str = "", brief_path: str | None = None)`
- `OSError`/`PermissionError` on `brief_path` is silenced in the flow; `brief=None` is passed to agent
- Outputs: `<repo_path>/_autodev/project-context.md` and `.json`

Tests:
| Test | Result |
|---|---|
| `test_project_context_flow_initialization` | PASS |
| `test_project_context_flow_happy_path` | PASS |
| `test_project_context_flow_brief_path_oserror_silenced` | PASS |
| `test_project_context_flow_with_product_name` | PASS |

---

### 4. `tests/unit/test_flow_executor_failure_surface.py` — 6 tests, 6 passed

Covers executor-failure propagation via `unittest.mock.patch` on `ImplementerAgent.run_milestone`.

Real shapes investigated:
- `ImplementationResult(milestone_id, task_results, success, mock_used, failed_task_ids)`
- `IssuePipelineFlow.run()` appends impl result; flow tolerates `success=False` and continues to reporting
- `BugFixFlow.run()` uses `concurrency=1, fail_fast=True` hardcoded
- `MultiPatchFlow.run()` votes on candidates; all-fail still writes `vote.json`
- `ProjectDeliveryFlow.run()` tracks `any_milestone_failed` locally; first fail can early-break with `fail_fast`
- `ReplayFlow.replay()` raises `ValueError` for unknown stage AND for replaying `planning` without architecture

Tests:
| Test | Result |
|---|---|
| `test_issue_pipeline_flow_executor_failure_surfaces_in_run_state` | PASS |
| `test_bug_fix_flow_reproduce_failure_aborts_subsequent_stages` | PASS |
| `test_multi_patch_flow_all_candidates_fail_returns_no_winner` | PASS |
| `test_project_delivery_flow_any_milestone_failed_propagates` | PASS |
| `test_replay_flow_invalid_from_step_raises_value_error` | PASS |
| `test_replay_flow_planning_without_architecture_raises_value_error` | PASS |

---

## Regression Summary

| Scope | Before | After |
|---|---|---|
| Full suite passed | 1160 | 1178 (+18) |
| xfailed | 10 | 10 |
| Failed | 0 | 0 |
| New test files | 0 | 4 |
| New tests | 0 | 18 |

0 regressions introduced.
