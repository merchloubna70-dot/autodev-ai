# Project Delivery Mode

The Project Delivery Mode handles delivery of a complete project from
an idea or PRD or empty repo all the way to a release-ready report.

Stages:

1. **InputClassifier** — picks the right flow based on the input shape.
2. **ProductManager** — turns the brief into a `ProductBrief`.
3. **RequirementAnalyst** — derives functional, non-functional, and
   acceptance criteria.
4. **PRDWriter** — emits `prd.md` and `prd.json`.
5. **RepoExplorer** — scans the target repo (empty / existing).
6. **SystemArchitect** — produces an `ArchitectureSpec`,
   `architecture.md`, `module_map.json`, `api_contract.json`,
   `data_model.json`, `dependency_graph.json`.
7. **MilestonePlanner** — 3–8 milestones with acceptance + gates.
8. **TaskDecomposer** — DeliveryTasks (≤5 files each typically).
9. **Scaffolder** — for from-scratch or empty repos.
10. **Implementer** — executes each milestone through `ExecutorRouter`.
11. **TestDesigner** — emits `TestPlan` (unit/integration/e2e/smoke).
12. **QualityGate** — runs language gates.
13. **SecurityReviewer** — secrets / unsafe shell / dependency hygiene.
14. **CodeReviewer** — task results vs. acceptance criteria.
15. **IntegrationReviewer** — cross-language consistency.
16. **Verifier** — independent acceptance verification.
17. **DocWriter** — README/usage/architecture for the *delivered* project.
18. **ReleaseManager** — release_check, release notes, delivery report.
19. **CommitAgent** — branch / commit message / PR body (no push by default).

Each milestone produces:

- `execution/milestone_<id>_results.json`
- per-task `execution/executor_selection_<task_id>.json`
- audit lines on `execution/execution_calls.jsonl`, `codex_calls.jsonl`,
  `claude_code_calls.jsonl`.

`final_report.md` cannot relabel any skipped/failed gate as passed; the
`ReleaseGate` enforces `NotReleaseReady` whenever mocks were used or the
mode was dry-run.
