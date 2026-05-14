# Round 7 — Mock Full Pipeline Validation Report

**Agent:** 4 — mock_full_pipeline  
**Date:** 2026-05-14  
**Sandbox:** `/tmp/r7-mock-sandbox`  
**Environment:** `FACTORY_FORCE_MOCK=1`, secrets unset  
**Overall Result:** PASS — 8/8 scenarios passed

---

## Environment

| Variable | Value |
|---|---|
| FACTORY_FORCE_MOCK | 1 |
| OPENAI_API_KEY | unset |
| ANTHROPIC_API_KEY | unset |
| GITHUB_TOKEN | unset |

---

## Scenario Results

### A — brief_to_prd (`create-prd`)
- **Command:** `autodev create-prd --project-brief brief.txt --output .dev-factory/prd.md`
- **Exit Code:** 0
- **Duration:** ~430ms
- **Artifacts Created:** `.dev-factory/prd.md`, `.dev-factory/prd.json`
- **Result:** PASS
- **Notes:** `--project-brief` expects a FILE path (not inline string). Brief file created at `/tmp/r7-mock-sandbox/brief.txt`. PRD correctly generated with mock ProductManagerAgent + RequirementAnalystAgent + PRDWriterAgent chain.

### B — prd_to_project_plan (`plan-project`)
- **Command:** `autodev plan-project --repo-path . --prd .dev-factory/prd.md --languages python`
- **Exit Code:** 0
- **Duration:** ~430ms
- **Artifacts Created:** JSON printed to stdout (no run-state files; standalone helper)
- **Result:** PASS
- **Notes:** SystemArchitectAgent produces architecture JSON with `core_python` module, empty endpoints, design decisions. Output to stdout only — not persisted to audit tree. This is by design for this standalone helper command.

### C — prd_to_milestones (`plan-milestones`)
- **Command:** `autodev plan-milestones --repo-path . --prd .dev-factory/prd.md --max-milestones 3`
- **Exit Code:** 0
- **Duration:** ~420ms
- **Artifacts Created:** JSON printed to stdout (no run-state files; standalone helper)
- **Result:** PASS
- **Notes:** MilestonePlannerAgent generated M0 (Product & Architecture), M1 (Project Scaffold), M2 (Core Domain). Output to stdout only — not persisted. Standalone helper command.

### D — milestone_to_tasks (`plan-tasks`)
- **Command:** `autodev plan-tasks --repo-path . --milestone-id M1`
- **Exit Code:** 0
- **Duration:** ~430ms
- **Artifacts Created:** JSON printed to stdout
- **Result:** PASS
- **Notes:** `plan-tasks` requires `RunState.latest()` to return a run with `milestone_plan`. Must be run AFTER `deliver-project` or `run-issue` has populated the audit tree. Returns task M1-T1 (Scaffold python skeleton) with full codex_prompt, claude_prompt, target_files, accepted_criteria.

### E — run_issue (`run-issue`)
- **Command:** `autodev run-issue --repo-path . --issue-file issue.txt --languages python --mode dry-run --allow-mock-executor true --no-fail-fast`
- **Exit Code:** 0
- **Duration:** ~800ms
- **Run ID:** `run_20260514T093309_ecee3960`
- **Artifacts Created:** Full audit tree under `.dev-factory/runs/run_20260514T093309_ecee3960/`
- **Result:** PASS
- **Notes:** Issue pipeline flow executed correctly with mock executors. `product/` directory is empty for issue flows (expected — issue mode doesn't create PRD artifacts). All 8 subdirs created.

### F — deliver_project (`deliver-project`)
- **Command:** `autodev deliver-project --repo-path . --project-brief brief.txt --languages python --mode dry-run --allow-mock-executor true --scale small --no-fail-fast`
- **Exit Code:** 0
- **Duration:** ~476ms
- **Run ID:** `run_20260514T093218_e5f8c91d` (first), `run_20260514T093354_ead6fe55` (second)
- **Artifacts Created:** Full audit tree with all 8 subdirs, 44 files
- **Result:** PASS
- **Notes:** Full project delivery pipeline executed with mock backends (mock_codex + mock_claude). 5 milestones (M0-M5), 6 tasks, quality gates, security review, verification, release check, delivery report all generated. Release decision: `NotReleaseReady` (expected — mock mode cannot claim production-ready).

### G — verify (`verify`)
- **Command:** `autodev verify --run-id run_20260514T093218_e5f8c91d --repo-path .`
- **Exit Code:** 0
- **Duration:** ~474ms
- **Artifacts Created:** Outputs JSON to stdout; `verification/verification_report.json` already present in run
- **Result:** PASS
- **Notes:** Verification status: `passed`. All milestone acceptance checks: M0/M1/M2/M4/M5 = passed. state_integrity_ok: true. Correctly notes: "verification observed mock executor usage — cannot claim production-passed".

### H — report (`report`)
- **Command:** `autodev report --run-id run_20260514T093218_e5f8c91d --repo-path .`
- **Exit Code:** 0
- **Duration:** ~426ms
- **Artifacts Created:** Returns path to `delivery/final_report.md`
- **Result:** PASS
- **Notes:** Report correctly generated at `.dev-factory/runs/run_20260514T093218_e5f8c91d/delivery/final_report.md`. Contains dry-run/mock warnings, milestone summary, quality gate status, verification, release decision.

---

## Audit Tree Verification

### Required Subdirs per Run

| Subdir | run_20260514T093218 (deliver) | run_20260514T093309 (issue) | run_20260514T093354 (deliver) |
|---|---|---|---|
| input | YES | YES | YES |
| product | YES | YES (empty) | YES |
| architecture | YES | YES | YES |
| planning | YES | YES | YES |
| execution | YES | YES | YES |
| quality | YES | YES | YES |
| verification | YES | YES | YES |
| delivery | YES | YES | YES |

All 8 required subdirs present in all 3 runs. No missing subdirs.

---

## State Machine Observations

The state machine is implicit in `PipelineRunState` — there is no explicit `status` enum field. State is inferred from:
- `started_at` set at run init
- `finished_at` set when `RunState.finish()` is called
- `mock_execution_used=True` confirms mock path was taken

All 3 runs show `finished_at` populated (completed state), `mock_execution_used=True`.

Observed state progression: **init → running (via flow steps) → finished (finished_at populated)**

Release decision for all deliver-project runs: `NotReleaseReady` — correct behavior as mock execution cannot claim release readiness.

---

## Findings

### P2 — `create-prd` accepts file path only, not inline strings
- **Detail:** The `--project-brief` flag calls `Path(p).read_text()`, so passing a string like "Build a hello-world REST API" raises `FileNotFoundError`. The help text shows `TEXT` type without clarifying it must be a file path.
- **Evidence:** First invocation failed with `FileNotFoundError: [Errno 2] No such file or directory: 'Build a hello-world REST API in Python'`
- **Impact:** UX friction — users unfamiliar with the pattern will fail on first try.

### P3 — `plan-project` / `plan-milestones` produce stdout-only output without run-state persistence
- **Detail:** These standalone commands do not create `.dev-factory/runs/<run_id>/` audit trees. They are pipeline-prep helpers. This is likely by design but means scenarios B and C don't contribute to the audit tree unless called through `deliver-project`.
- **Evidence:** After running both commands, `.dev-factory/` only contained `prd.json` and `prd.md`.

### P3 — `plan-tasks` requires existing run with milestone_plan
- **Detail:** `plan-tasks` uses `RunState.latest()` which scans `.dev-factory/runs/` for the most recent run with `milestone_plan`. If called before `deliver-project`, it returns "no run with milestone_plan found" and exits 2.
- **Evidence:** First invocation (before deliver-project) returned 0 tasks; after deliver-project it correctly returned M1-T1.

### P4 — `PipelineRunState` has no explicit `status` field (draft/running/done enum)
- **Detail:** The run state schema tracks completion via `started_at`/`finished_at` rather than an explicit status enum. There is no `status: "done"` field in `run_state.json`. The `errors: []` array and `finished_at` together indicate success.
- **Impact:** Minor — state inference is functional but less explicit than a status field would be.

---

## Summary

All 8 pipeline scenarios passed with exit code 0 under `FACTORY_FORCE_MOCK=1` with no API keys. The mock infrastructure is fully operational. The deliver-project flow produces a complete 8-subdir audit tree with 44 artifacts in under 500ms. The run-issue flow also produces a complete audit tree. The release decision correctly reports `NotReleaseReady` in mock mode.

**P0:** 0  **P1:** 0  **P2:** 1  **P3:** 2  **P4:** 1
