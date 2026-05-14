# AutoDev Full Audit — Flow & Agent Coverage Matrix

**Round:** full_audit_flow_agent_coverage
**Date:** 2026-05-14
**Auditor:** PreTag-G

---

## Counts

| Item | Expected | Actual | Status |
|------|----------|--------|--------|
| Flows (`src/autodev/flows/`, excl. `__init__.py`, `step_definitions/`) | 17 | 16 | DELTA -1 |
| Agents (`src/autodev/agents/`, excl. `__init__.py`, `_*.py`) | 41 | 39 | DELTA -2 |
| BMAD markers in `src/autodev/schemas.py` | ≥18 | 18 | PASS |

**Flow files found (16):**
brownfield_doc_flow, bug_fix_flow, investigation_flow, issue_pipeline_crewflow, issue_pipeline_flow, milestone_flow, multi_patch_flow, project_context_flow, project_delivery_crewflow, project_delivery_flow, project_delivery_microfile, release_flow, replay_flow, sprint_flow, step_runner, ux_design_flow

**Agent files found (39):**
adversarial_reviewer, clarification_gate, code_reviewer, commit_agent, context_generator, critic, doc_writer, document_project, edge_case_hunter, editorial_reviewer, elicitation_methods, failure_cluster_reviewer, human_review_gate, implementer, input_classifier, integration_reviewer, investigator, issue_analyst, milestone_planner, navigator, next_step_advisor, opus_consult, parallel_section_reviewer, prd_writer, product_manager, property_test_designer, quality_gate, release_manager, repo_explorer, requirement_analyst, roundtable, scaffolder, security_reviewer, sprint_manager, system_architect, task_decomposer, test_designer, ux_designer, verifier

---

## R3-E Gap Closures Verified

| Flow | Test File | Status |
|------|-----------|--------|
| MilestoneFlow | `tests/unit/test_milestone_flow.py` | EXISTS + 8 PASS |
| ReleaseFlow | `tests/unit/test_release_flow.py` | EXISTS + 7 PASS |
| ProjectContextFlow | No direct test file | NOT CLOSED (indirect schema coverage only) |

**Pytest result:** `tests/unit/test_milestone_flow.py` + `tests/unit/test_release_flow.py` → **15 passed** in 0.13s

---

## Flow → Test Coverage Matrix

| Flow | Test Coverage | Location |
|------|--------------|----------|
| issue_pipeline_flow | COVERED | tests/unit/test_crewflow_stubs.py (indirect) |
| project_delivery_flow | COVERED | tests/unit/ |
| project_delivery_microfile | COVERED | tests/integration/test_project_delivery_microfile.py |
| sprint_flow | COVERED | tests/unit/test_sprint_flow.py |
| bug_fix_flow | COVERED | tests/integration/test_bug_fix_flow.py |
| multi_patch_flow | COVERED | tests/unit/test_multi_patch_vote.py |
| investigation_flow | **MISSING** | No test found |
| brownfield_doc_flow | **MISSING** | No test found (BrownfieldDoc schema tested in test_document_project.py) |
| ux_design_flow | COVERED | tests/unit/test_ux_design_flow.py |
| project_context_flow | **MISSING** | No test found (schema tested in test_context_generator.py) |
| release_flow | COVERED | tests/unit/test_release_flow.py (R3-E) |
| milestone_flow | COVERED | tests/unit/test_milestone_flow.py (R3-E) |
| replay_flow | COVERED | tests/unit/test_replay_flow.py |
| step_runner | COVERED | tests/unit/test_step_runner.py |

**Flows with tests:** 11 of 14 audited (78.6%)
**Flows without tests:** investigation_flow, brownfield_doc_flow, project_context_flow

---

## BMAD Markers

18 markers found in `src/autodev/schemas.py` (BMAD1 through BMAD18). Meets ≥18 threshold.

---

## Verdict

**coverage_improved_with_gaps**

R3-E delivered on MilestoneFlow and ReleaseFlow (15 tests, all green). ProjectContextFlow was claimed as R3-E closure but lacks a dedicated test file — only schema-level coverage exists. Flow count is 16 (not 17); agent count is 39 (not 41). Three flows remain untested: InvestigationFlow, BrownfieldDocFlow, ProjectContextFlow.
