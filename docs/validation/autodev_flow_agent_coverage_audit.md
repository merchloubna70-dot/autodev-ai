# autodev Flow & Agent Coverage Audit

**Round:** flow_agent_coverage  
**Date:** 2026-05-14  
**Auditor:** Agent G — Release Hardening  
**Scope:** 17 flows in `src/autodev/flows/`, 41 agents in `src/autodev/agents/`

---

## Summary

| Metric | Value |
|---|---|
| Total flows | 17 |
| Flows covered by test | 12 / 17 (70.6%) |
| Flows covered by docs | 11 / 17 (64.7%) |
| Flows with CLI entry | 12 / 17 |
| Flows with replay support | 5 / 17 |
| Total agents | 41 |
| Agents covered by test | 36 / 41 (87.8%) |
| Agents covered by docs | 20 / 41 (48.8%) |
| Agents with NO test | **5** |
| BMAD markers in schemas.py | **18 / 18** (complete) |

---

## Flow Matrix

| Flow | CLI Entry | Tests | Docs | Replay | Mock | External Deps | Failure Mode | Readiness |
|---|---|---|---|---|---|---|---|---|
| IssuePipelineFlow | `run-issue` | 4 | yes | no | yes | codex/claude, git | exception / ImplementationResult | 4 |
| ProjectDeliveryFlow | `deliver-project` | 7 | yes | yes | yes | codex/claude, git | `any_milestone_failed` flag | 5 |
| SprintFlow | `sprint-start/status/retro/correct` | 1 | yes | no | yes | disk only | FileNotFoundError | 4 |
| BugFixFlow | `fix-bug` | 1 | yes | no | yes | codex/claude | ImplementationResult | 4 |
| MultiPatchFlow | `multi-patch-fix-bug` | 2 | yes | no | yes | codex/claude | per-candidate ImplementationResult | 4 |
| InvestigationFlow | `investigate` | **0** | yes | no | no | disk only | exception propagates | 2 |
| BrownfieldDocFlow | `document-project` | **0** | yes | no | no | disk only | exception propagates | 2 |
| UXDesignFlow | `design-ux` | 1 | yes | no | yes | none (default) | exception propagates | 3 |
| ProjectContextFlow | `generate-context` | **0** | **no** | no | no | disk only | exception propagates | 1 |
| ReleaseFlow | `release-check` | **0** | yes | no | yes | none | exception propagates | 2 |
| MilestoneFlow | `execute-milestone` | **0** | yes | no | yes | codex/claude | RuntimeError / ImplementationResult | 2 |
| ReplayFlow | `replay` | 2 | yes | yes | yes | codex/claude, git | ValueError / exception | 4 |
| IssuePipelineCrewFlow | **none** | 1 | **no** | no | yes | crewai (optional) | RuntimeError if crewai absent | 2 |
| ProjectDeliveryCrewFlow | **none** | 1 | **no** | no | yes | crewai (optional) | RuntimeError if crewai absent | 2 |
| ProjectDeliveryMicroFlow | **none** | 2 | **no** | yes | yes | codex/claude, git | StepRecord.FAILED + re-raise | 3 |
| StepRunner | **none** | 1 | **no** | yes | yes | none | StepRecord.FAILED + re-raise | 4 |
| step_definitions/project_delivery_steps | **none** | 1 | **no** | yes | yes | codex/claude, git | StepRecord.FAILED + re-raise | 3 |

---

## Agent Matrix

| Agent | Has Test | Has Docs | Requires LLM | Internal Only |
|---|---|---|---|---|
| _activation | yes | no | no | yes |
| _crewai_bridge | **no** | no | yes | yes |
| _menu | yes | no | no | yes |
| _scaffold_verification | yes | no | no | yes |
| adversarial_reviewer | yes | no | yes | no |
| clarification_gate | yes | no | yes | no |
| code_reviewer | yes | yes | yes | no |
| commit_agent | yes | yes | yes | no |
| context_generator | yes | no | no | no |
| critic | yes | no | yes | no |
| doc_writer | **no** | yes | yes | no |
| document_project | yes | no | yes | no |
| edge_case_hunter | yes | no | no | no |
| editorial_reviewer | yes | no | no | no |
| elicitation_methods | yes | no | yes | no |
| failure_cluster_reviewer | yes | no | yes | no |
| human_review_gate | yes | no | no | no |
| implementer | yes | yes | yes | no |
| input_classifier | yes | yes | yes | no |
| integration_reviewer | yes | yes | yes | no |
| investigator | yes | no | yes | no |
| issue_analyst | yes | yes | yes | no |
| milestone_planner | yes | yes | yes | no |
| navigator | yes | no | yes | no |
| next_step_advisor | yes | yes | no | no |
| opus_consult | yes | no | no | no |
| parallel_section_reviewer | yes | no | yes | no |
| prd_writer | yes | yes | yes | no |
| product_manager | yes | yes | yes | no |
| property_test_designer | yes | no | no | no |
| quality_gate | yes | yes | yes | no |
| release_manager | **no** | yes | yes | no |
| repo_explorer | **no** | yes | yes | no |
| requirement_analyst | yes | yes | yes | no |
| roundtable | yes | yes | yes | no |
| scaffolder | yes | yes | yes | no |
| security_reviewer | yes | yes | yes | no |
| sprint_manager | **no** | **no** | no | no |
| system_architect | yes | yes | yes | no |
| task_decomposer | yes | yes | yes | no |
| test_designer | yes | yes | yes | no |
| ux_designer | yes | no | yes | no |
| verifier | yes | yes | yes | no |

**Agents with NO test (5):** `_crewai_bridge`, `doc_writer`, `release_manager`, `repo_explorer`, `sprint_manager`

---

## BMAD Marker Inventory

All 18 markers present in `src/autodev/schemas.py`:

| Marker | Tag |
|---|---|
| BMAD1 | SCALE |
| BMAD2 | ADV-EDGE |
| BMAD3 | NEXT-ADVISOR |
| BMAD4 | CLARIFY-EDITORIAL |
| BMAD5 | SHARD-DISTILL |
| BMAD6 | CONFIG-PRFAQ |
| BMAD7 | SPRINT |
| BMAD8 | UX-SALLY |
| BMAD9 | READINESS-GATE |
| BMAD10 | INVESTIGATE |
| BMAD11 | PROJECT-CONTEXT |
| BMAD12 | TASK-READINESS |
| BMAD13 | DOC-PROJECT |
| BMAD14 | ELICITATION |
| BMAD15 | MICROFILE |
| BMAD16 | HOOKS |
| BMAD17 | AGENT-MENU |
| BMAD18 | SKILL-CUSTOMIZE |

---

## Findings

### HIGH — F-001: MilestoneFlow has zero tests (execute-milestone CLI)
`flows/milestone_flow.py` is the only way to re-run a single milestone independently but has no test file. The `RuntimeError` raised on missing `milestone_plan` is untested.  
**Fix:** Add `tests/unit/test_milestone_flow.py` covering success path and RuntimeError path with a mock RunState.

### HIGH — F-002: ReleaseFlow has zero tests (release-check CLI)
`flows/release_flow.py` calls `ReleaseManagerAgent.check()` and writes two artefacts. No test exercises this path.  
**Fix:** Add `tests/unit/test_release_flow.py`; mock `ReleaseManagerAgent`.

### HIGH — F-003: ProjectContextFlow has zero tests AND zero docs (generate-context CLI)
The `generate-context` CLI entry maps to `ProjectContextFlow` → `ContextGeneratorAgent`. Neither flow tests nor documentation exist.  
**Fix:** Add `tests/unit/test_project_context_flow.py` and a `docs/usage.md` section.

### MEDIUM — F-004: InvestigationFlow and BrownfieldDocFlow have zero tests
Thin wrapper flows — agent tests exist but flow wiring is unverified.  
**Fix:** Add integration smoke tests using `FACTORY_FORCE_MOCK=1`.

### MEDIUM — F-005: 5 flows have no CLI entry (CrewFlows, MicroFlow, StepRunner, step_definitions)
`IssuePipelineCrewFlow`, `ProjectDeliveryCrewFlow`, `ProjectDeliveryMicroFlow`, `StepRunner`, and `step_definitions/project_delivery_steps` are not reachable from the `autodev` CLI directly.  
**Fix:** Either expose a `--engine` flag on `run-issue`/`deliver-project` or document these as library-only. CrewFlow readiness is blocked by optional crewai dependency.

### MEDIUM — F-006: sprint_manager agent has zero tests and zero docs
`sprint_manager.py` is not referenced in `SprintFlow` (which uses pure Python). Possibly a dead module.  
**Fix:** Remove if dead. If intentional, add tests and docs.

### MEDIUM — F-007: repo_explorer agent has zero tests despite being in every major flow
`RepoExplorerAgent` is called by 3 flows and the `scan` CLI. No dedicated test file exists; only transitive coverage.  
**Fix:** Add `tests/unit/test_repo_explorer.py` with filesystem fixtures.

### MEDIUM — F-008: _crewai_bridge has zero tests
The `make_crew()` factory and StubCrew fallback path have no direct unit tests.  
**Fix:** Add `tests/unit/test_crewai_bridge.py`.

### LOW — F-009: 12 of 17 flows lack replay support
Single-purpose flows restart from scratch on failure.  
**Fix:** Consider stage checkpoints for BugFixFlow (4 explicit stages already defined) and MultiPatchFlow (per-candidate checkpoints).

### LOW — F-010: BMAD markers complete — all 18 present in schemas.py
No action required.

### LOW — F-011: doc_writer agent has zero tests
`DocWriterAgent` writes critical delivery artefacts (`README.generated.md`, `usage.generated.md`) but has no tests.  
**Fix:** Add `tests/unit/test_doc_writer.py` with a minimal PRD fixture.

---

## Top Gaps Priority List

| Priority | Item |
|---|---|
| P0 | Add tests for MilestoneFlow, ReleaseFlow, ProjectContextFlow |
| P0 | Add docs + tests for generate-context |
| P1 | Add tests for InvestigationFlow, BrownfieldDocFlow |
| P1 | Add tests for repo_explorer agent |
| P1 | Clarify/remove sprint_manager (dead or untested) |
| P2 | Expose MicroFlow via CLI --engine flag or document as library-only |
| P2 | Add tests for doc_writer and _crewai_bridge |
| P3 | Add replay support to BugFixFlow (4-stage checkpoints) |
