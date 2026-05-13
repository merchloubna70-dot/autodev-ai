# autodev

A CrewAI + **Codex CLI** + **Claude Code CLI** software factory that supports
two delivery modes against any Python / Rust / TypeScript repository:

- **Issue Mode** — turn a GitHub issue / local `issue.md` into a structured
  change with audit trail, gates, and PR-ready artifacts.
- **Project Delivery Mode** — from project brief / PRD (or even an empty
  repo) to milestone-driven, gate-protected delivery.

All CLI traffic is funneled through one `ExecutorRouter` that automatically
chooses between Codex CLI (small patches, scaffolds, tests, lint fixes) and
Claude Code CLI (architecture, cross-language, security, release, docs), with
deterministic mock fall-backs for CI environments.

## Install

```
pip install -e ".[dev]"
# optional: real CrewAI runtime
pip install -e ".[crewai]"
```

## Quick examples

```bash
autodev scan --repo-path .

autodev run-issue \
  --repo-path . \
  --issue-file tests/fixtures/issue_project/issue.md \
  --languages python \
  --mode dry-run \
  --executor auto \
  --allow-mock-executor true

autodev deliver-project \
  --repo-path tests/fixtures/empty_project \
  --project-brief tests/fixtures/prd_project/project_brief.md \
  --from-scratch true \
  --languages python,typescript \
  --mode dry-run

autodev execute-milestone \
  --run-id <latest_run_id> \
  --milestone-id M2 \
  --executor claude-code \
  --allow-mock-executor true

autodev report --run-id <latest_run_id>
```

## Multi-CLI executor routing

| Task type      | Default backend      | Why                                                      |
|----------------|----------------------|----------------------------------------------------------|
| scaffold       | Codex                | small mechanical writes; deterministic templates         |
| test           | Codex                | targeted unit-test additions                             |
| feature (small)| Codex                | ≤5 files, low risk                                       |
| feature (big)  | Claude Code          | many files OR high risk OR cross-language                |
| refactor       | Claude Code          | requires long-context reasoning                          |
| architecture   | Claude Code          | system design / contracts                                |
| integration    | Claude Code if cross-language, else Codex | API / schema contracts |
| docs           | Claude Code          | tone & cohesion                                          |
| security       | Claude Code          | deeper review                                            |
| release        | Claude Code          | rolls up evidence                                        |

If the chosen CLI is not installed and `--allow-mock-executor true`, the
router substitutes the matching `MockCodexExecutor` / `MockClaudeExecutor`
**and records `mock_used=true`** in every audit record so downstream gates
can refuse to mark the run release-ready off mock evidence alone.

If `--allow-mock-executor false` and the CLI is missing, the run **fails
closed**.

## Audit trail

Every run lives at `<repo>/.dev-factory/runs/<run_id>/`:

```
input/         classification.json, raw_input.md
product/       product_brief.json, prd.md, prd.json
architecture/  architecture.md, module_map.json, api_contract.json, ...
planning/      milestones.json, tasks.json, delivery_plan.md
execution/     executor_selection_*.json, execution_calls.jsonl,
               codex_calls.jsonl, claude_code_calls.jsonl,
               milestone_*_results.json
quality/       test_plan.json, quality_gate.json, security_review.json,
               code_review.json, integration_review.json
verification/  verification_report.json, release_check.json
delivery/      README.generated.md, usage.generated.md, release_notes.md,
               delivery_report.md, final_report.md
run_state.json
```

See `docs/architecture.md` and `docs/multi_cli_executor.md` for details.

## Safety rules baked in

- No business code calls `codex` or `claude` directly — only `ExecutorRouter`.
- Shell executor is allowlist-only; dangerous patterns (`rm -rf`, `sudo`,
  `cat .env`, `curl|bash`, …) are denied in **all** modes.
- `commit`, `push`, `tag`, `release` are off by default and require explicit
  flags.
- `final_report.md` refuses to relabel `skipped` / `failed` gates as `passed`.
- `release_check` returns `NotReleaseReady` when any of `dry_run`,
  `mock_execution_used`, or a failed gate are observed.

## License

MIT.
