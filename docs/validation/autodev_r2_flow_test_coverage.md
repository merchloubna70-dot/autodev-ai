# R2 Flow Test Coverage — MilestoneFlow + ReleaseFlow

**Round:** autodev-ai R2 PyPI Release Blocker Closure  
**Date:** 2026-05-14  
**Blocker IDs:** HIGH-COV-01, HIGH-ORPHAN-01  
**Verdict:** `closed`

---

## Tests Added

### `tests/unit/test_milestone_flow.py` — 8 tests

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `test_milestone_flow_initialization` | `MilestoneFlow()` constructs with default `FactoryConfig` |
| 2 | `test_milestone_flow_initialization_custom_config` | accepts custom `FactoryConfig` |
| 3 | `test_milestone_flow_happy_path_mock` | single milestone, mock executor → `ImplementationResult.success=True` |
| 4 | `test_milestone_flow_failure_path` | executor returns failure → `success=False`, `failed_task_ids` populated |
| 5 | `test_milestone_flow_report_artifact` | `run_state.json` is updated with `implementation_results` after `.run()` |
| 6 | `test_milestone_flow_empty_milestone_list` | milestone with no tasks → `success=True`, `task_results=[]` |
| 7 | `test_milestone_flow_skip_m0_collapse` | M0 architecture milestone with no tasks collapses to `success=True` |
| 8 | `test_milestone_flow_raises_when_no_plan` | `RuntimeError("no milestone_plan")` when plan absent |

**Mock strategy:** `unittest.mock.patch` on `ImplementerAgent.run_milestone`. The full `MilestoneFlow.run()` path (including `RunState.load`, state mutation, and `run.save()`) executes for real; only the agent call is mocked.

### `tests/unit/test_release_flow.py` — 7 tests

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `test_release_flow_initialization` | `ReleaseFlow()` constructs with non-None `release_manager` and `reporter` |
| 2 | `test_release_flow_release_check_happy_path` | all gates pass → `decision == RELEASE_READY` |
| 3 | `test_release_flow_blocker_finding_blocks_release` | security `GateStatus.FAILED` in run state → `decision == BLOCKED` (real ReleaseGate) |
| 4 | `test_release_flow_writes_release_report` | real `Reporter.write_final_report` called → `delivery/final_report.md` exists on disk |
| 5 | `test_release_flow_no_external_cli_required` | end-to-end with fully mocked manager + reporter; no codex/claude binary touched |
| 6 | `test_release_flow_persists_release_check_to_run_state` | `run.state.release_check` populated and persisted to `run_state.json` |
| 7 | `test_release_flow_saves_release_check_json_artifact` | `verification/release_check.json` artifact written to disk |

**Mock strategy:** `patch.object` on `flow.release_manager.check` and/or `flow.reporter.write_final_report`. Test 3 uses the real `ReleaseGate` to exercise the security-blocked code path. Tests 4, 6, 7 use the real `Reporter` to verify disk writes.

---

## Flow Init Signatures Observed

```python
# MilestoneFlow
class MilestoneFlow:
    def __init__(self, config: FactoryConfig | None = None): ...
    def run(self, inp: MilestoneFlowInput) -> ImplementationResult: ...

# MilestoneFlowInput (dataclass)
@dataclass
class MilestoneFlowInput:
    run_id: str
    milestone_id: str
    repo_path: str
    mode: PipelineMode = PipelineMode.DRY_RUN
    backend: ExecutionBackend = ExecutionBackend.AUTO
    allow_mock: bool = True
    concurrency: int = 3
    fail_fast: bool = True

# ReleaseFlow
class ReleaseFlow:
    def __init__(self) -> None: ...
    def check(self, run: RunState) -> ReleaseCheckReport: ...
```

`ReleaseFlow.__init__` takes no arguments. Mock must be applied after construction via `patch.object`.

---

## Tests Skipped

None. All 6 spec-required MilestoneFlow tests and all 5 spec-required ReleaseFlow tests were implemented. Three additional tests were added (2 MilestoneFlow, 2 ReleaseFlow) for coverage depth.

---

## Test Pass Counts

| Scope | Passed | Failed | Skipped |
|-------|--------|--------|---------|
| `test_milestone_flow.py` | 8 | 0 | 0 |
| `test_release_flow.py` | 7 | 0 | 0 |
| **New tests total** | **15** | **0** | **0** |
| Full suite (before additions) | 951 | 3 | 0 |
| Full suite (after additions) | 966 | 3 | 0 |

Pre-existing failures (unrelated, pre-dating this round):
- `tests/integration/test_a2a_http_roundtrip.py` — 2 tests (HTTP port binding)
- `tests/unit/test_homebrew_formula_metadata.py` — 1 test (org URL check)
- `tests/unit/test_a2a_http_ssrf_hardening.py` — 1 test (SSRF redirect, flaky)

Note: the integration run shows 3 unique test failures (not 4) because one SSRF test passes intermittently.

---

## Verdict: `closed`

MilestoneFlow and ReleaseFlow had zero direct tests before this round. Both now have comprehensive deterministic unit test coverage. Zero-coverage gap is closed.
