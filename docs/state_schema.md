# State schema

Every JSON file under `.dev-factory/runs/<run_id>/` is a serialized pydantic
model defined in `schemas.py`.

| File                                          | Model                            |
|-----------------------------------------------|----------------------------------|
| `input/classification.json`                   | `InputClassification`            |
| `input/repo_scan.json`                        | `RepoScanResult`                 |
| `product/product_brief.json`                  | `ProductBrief`                   |
| `product/prd.json`                            | `PRD`                            |
| `architecture/architecture.json`              | `ArchitectureSpec`               |
| `architecture/module_map.json`                | `list[ModuleSpec]`               |
| `architecture/api_contract.json`              | `ApiContract`                    |
| `architecture/data_model.json`                | `DataModel`                      |
| `architecture/dependency_graph.json`          | `DependencyGraph`                |
| `planning/milestones.json`                    | `list[Milestone]`                |
| `planning/tasks.json`                         | `list[DeliveryTask]`             |
| `planning/scaffold_plan.json`                 | `ScaffoldPlan`                   |
| `execution/execution_calls.jsonl`             | `list[ExecutionResult]`          |
| `execution/codex_calls.jsonl`                 | `list[CodexCallResult]`          |
| `execution/claude_code_calls.jsonl`           | `list[ClaudeCodeCallResult]`     |
| `execution/executor_selection_<task>.json`    | `RouterDecision`                 |
| `execution/milestone_<id>_results.json`       | `ImplementationResult`           |
| `quality/test_plan.json`                      | `TestPlan`                       |
| `quality/quality_gate.json`                   | `list[QualityGateResult]`        |
| `quality/security_review.json`                | `SecurityReviewReport`           |
| `quality/code_review.json`                    | `CodeReviewReport`               |
| `quality/integration_review.json`             | `IntegrationReviewReport`        |
| `verification/verification_report.json`       | `VerificationReport`             |
| `verification/release_check.json`             | `ReleaseCheckReport`             |
| `delivery/delivery_report.md`                 | rendered from `DeliveryReport`   |
| `delivery/final_report.md`                    | rendered from `PipelineRunState` |
| `run_state.json`                              | `PipelineRunState`               |

All models validate on read; any drift surfaces as a pydantic
`ValidationError` rather than a silent mismatch.
