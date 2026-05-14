# Flow Agent Failure Coverage Audit

**Round:** flow_agent_failure_coverage  
**Agent:** Cov-E (Phase 1 — Read-Only)  
**Date:** 2026-05-14  
**Scope:** 15 flows in `src/autodev/flows/` — failure/error/edge-path coverage only

---

## Summary Counts

| Dimension | Count / 15 |
|---|---|
| Happy path tested | 10 |
| Failure path tested | **4** |
| Replay/resume tested | 3 |
| Mock executor tested | 9 |
| External CLI absent tested | 2 |
| Report output structure tested | 9 |
| **Zero dedicated test files** | **3** |

---

## Per-Flow Table

| Flow | Happy | Failure | Replay | Mock | CLI-Absent | Report | Risk |
|---|---|---|---|---|---|---|---|
| issue_pipeline_flow | Y | **N** | N | Y | N | Y | HIGH |
| project_delivery_flow | Y | Y* | N | Y | N | Y | HIGH |
| project_delivery_microfile | Y | **N** | Y | Y | N | Y | HIGH |
| sprint_flow | Y | Y* | N | N | N | Y | MEDIUM |
| bug_fix_flow | Y | **N** | N | Y | N | N | HIGH |
| multi_patch_flow | Y | **N** | N | Y | N | Y | MEDIUM |
| **investigation_flow** | **N** | **N** | **N** | **N** | **N** | **N** | **HIGH** |
| **brownfield_doc_flow** | **N** | **N** | **N** | **N** | **N** | **N** | **HIGH** |
| ux_design_flow | Y | N | N | N | N | Y | LOW |
| **project_context_flow** | **N** | **N** | **N** | **N** | **N** | **N** | **HIGH** |
| release_flow | Y | Y | N | Y | Y | Y | LOW |
| milestone_flow | Y | Y | N | Y | N | Y | MEDIUM |
| replay_flow | Y | Y* | Y | Y | N | N | HIGH |
| issue_pipeline_crewflow | N | N | N | N | Y | N | MEDIUM |
| project_delivery_crewflow | N | N | N | N | Y | N | MEDIUM |

*Y\* = partial failure coverage only*

---

## Top 3 Priority Gaps

### Gap 1 — Three flows with ZERO dedicated tests (CRITICAL)

`investigation_flow`, `brownfield_doc_flow`, `project_context_flow` have no flow-level test files at all. CLI-level tests exist but do not cross the flow class boundary.

**Phase 2 Cov-J recommended test shapes:**

**`tests/unit/test_investigation_flow.py`**
```python
from autodev.flows.investigation_flow import InvestigationFlow
from autodev.schemas import InvestigationInput, CaseFile
from pathlib import Path

# test_investigation_flow_creates_state_dir
# test_investigation_flow_returns_case_file
# test_investigation_flow_invalid_repo_path_auto_created
```

**`tests/unit/test_brownfield_doc_flow.py`**
```python
from autodev.flows.brownfield_doc_flow import BrownfieldDocFlow
from autodev.schemas import BrownfieldDoc, BrownfieldDocInput, Language
from unittest.mock import patch

# test_flow_returns_brownfield_doc
# test_flow_languages_none_passed_as_none (verify None→None conversion)
# test_flow_languages_list_passed_through
```

**`tests/unit/test_project_context_flow.py`**
```python
from autodev.flows.project_context_flow import ProjectContextFlow
from autodev.schemas import ProjectContext, ProjectContextInput
from unittest.mock import patch

# test_flow_returns_project_context
# test_flow_brief_path_missing_silenced (OSError → brief=None, no crash)
# test_flow_permission_error_silenced (PermissionError → brief=None)
# test_flow_product_name_forwarded
```

---

### Gap 2 — Executor failure not tested in high-volume flows (HIGH)

`issue_pipeline_flow` and `bug_fix_flow` have no test that injects a real executor failure and verifies the flow surfaces it correctly in `RunState`. The `any_milestone_failed` branch in `project_delivery_flow` is also untested in the actual-failure direction.

**Recommended additions:**
- `test_issue_pipeline_executor_failure_surfaces_in_state`: patch `ImplementerAgent.run_milestone` to return `success=False`; assert `run.state.errors` is non-empty
- `test_bug_fix_fail_fast_stops_at_reproduce`: force BUG-T1-REPRODUCE to fail; verify `implementation_results[0].success is False`
- `test_delivery_milestone_executor_failure_recorded`: force one milestone to fail; assert `'not-all-milestones-complete' in run.state.errors`

---

### Gap 3 — `replay_flow` defensive error branches untested (HIGH)

`ReplayFlow.replay()` has two guarded `ValueError` raises:
- `replay(from_stage='planning')` without `architecture` in state
- `replay(from_stage='implementation')` without `milestone_plan` in state

Neither is tested. Also, the fine-grained `from_step` path adds a note to `run.state.errors` but no test verifies this.

**Recommended additions:**
- `test_replay_planning_without_architecture_raises`: `pytest.raises(ValueError, match="Cannot replay 'planning'")`
- `test_replay_implementation_without_plan_raises`: `pytest.raises(ValueError, match="Cannot replay 'implementation'")`
- `test_replay_from_step_adds_step_note`: verify `run.state.errors` contains `'replayed from step'`

---

## Notable Coverage Strengths

- **`release_flow`**: 7 tests covering happy path, BLOCKER finding, artifact write, persistence, and no-external-CLI path — model to emulate.
- **`milestone_flow`**: Covers RuntimeError for missing plan, failure surfacing, empty milestone collapse.
- **`sprint_flow`**: Retrospective with failed tasks, health-complete classification.
- **`project_delivery_microfile`**: Resume-from-step semantics tested end-to-end.

---

## Output Files

- JSON: `docs/validation/autodev_flow_agent_failure_coverage_audit.json`
- This report: `docs/validation/autodev_flow_agent_failure_coverage_audit.md`
