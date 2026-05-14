# Round 7 — Brownfield Project E2E Validation Report

**Agent:** 11 — brownfield_e2e
**Date:** 2026-05-14
**autodev-ai version:** 0.1.0a3
**Mode:** FACTORY_FORCE_MOCK=1 (dry-run, mock executor)

---

## Summary

6/6 scenarios passed with exit code 0. Source files untouched outside `.dev-factory/`. Full audit tree created. Final report correctly references repo, bug, and proposed fix. Three low-severity findings identified (P2 grep scope leak, P3 mock file ghost entries, P3 investigate no-project-hit).

---

## Brownfield Setup

| Field | Value |
|---|---|
| Path | `/tmp/r7-brownfield` |
| Git commit | `1828ff7 init brownfield` |
| Modules | calculator, parser, formatter |
| Tests | 5 test files, 6 test functions |
| Bug | `calculator.divide(a, b)` — ZeroDivisionError when b==0 |
| Bug type | Missing zero-check guard before division |

### Files Created

```
pyproject.toml
src/widgetlib/__init__.py
src/widgetlib/calculator.py    ← bug: no zero-check in divide()
src/widgetlib/parser.py
src/widgetlib/formatter.py
tests/test_calculator.py       ← 2 tests; neither exercises b==0 path
tests/test_parser.py           ← 2 tests
tests/test_formatter.py        ← 1 test
README.md
```

---

## Scenario Results

### A — `autodev scan`

| Field | Value |
|---|---|
| Command | `autodev scan --repo-path /tmp/r7-brownfield` |
| Exit code | 0 |
| Duration | ~1s |
| Result | **PASS** |

**Key output:**
- Detected languages: `["python"]`
- Package files: `["pyproject.toml"]`
- Source dirs: `["src"]`
- Test dirs: `["tests"]`
- `is_empty: false`, `has_git: true`, `is_monorepo: false`
- Rust and TypeScript: not detected

Scan correctly identified the Python brownfield project structure.

---

### B — `autodev investigate`

| Field | Value |
|---|---|
| Command | `autodev investigate --input "divide function in calculator.py raises ZeroDivisionError when b==0 due to missing zero-check guard" --repo-path /tmp/r7-brownfield` |
| Exit code | 0 |
| Duration | ~1.3s |
| Result | **PASS** (with P2 finding) |

**Key output:**
```
case_id=2140effe
slug=divide-function-in-calculator-py-raises
mode=defect-chasing
file=/tmp/r7-brownfield/.dev-factory/investigations/divide-function-in-calculator-py-raises.md
evidence_count=5
```

**Case file:** `.dev-factory/investigations/divide-function-in-calculator-py-raises.md`

**P2 Finding — Grep scope leak:** The investigation grep found 4 hits in `.venv/lib/python3.12/site-packages/mypyc/...` and `./tests/unit/test_edge_case_hunter.py`. These files belong to the main autodev repo at `/Users/macworkers/autodev`, not the brownfield repo. The `investigate` command appears to run its grep from the process CWD (the autodev main repo) rather than from `--repo-path`. No hits from the actual brownfield source files (`src/widgetlib/calculator.py`) were found.

---

### C — `autodev fix-bug`

| Field | Value |
|---|---|
| Command | `autodev fix-bug --bug "..." --repo-path /tmp/r7-brownfield --languages python --mode dry-run --allow-mock-executor true` |
| Exit code | 0 |
| Duration | ~0.4s |
| Result | **PASS** |

**Key output:**
```
run_id=run_20260514T093438_719d0190 success=True mock=True
```

**4-stage plan generated:**
- `BUG-T1-REPRODUCE` — write minimal failing test (`tests/repro_bug.py`)
- `BUG-T2-LOCATE` — read-only root cause analysis (`bug.root_cause.md`)
- `BUG-T3-PATCH` — minimal targeted fix (±20 lines, `bug.patch.md`)
- `BUG-T4-VERIFY` — local gate check (`bug.verify.md`)

All 4 tasks executed via `mock_codex` (codex CLI not present → auto fallback). `fallback_used: true` correctly flagged. Executor selection reason recorded per task in `.dev-factory/runs/.../execution/executor_selection_BUG-T*.json`.

**P3 Finding — Mock file ghost entries:** Each task reports `changed_files` pointing to `.dev-factory/mock/codex_BUG-T*-*.txt` but the `.dev-factory/mock/` directory does not exist on disk. The mock executor declares file paths without writing them.

---

### D — `autodev review`

| Field | Value |
|---|---|
| Command | `autodev review --run-id run_20260514T093438_719d0190 --decision approve --repo-path /tmp/r7-brownfield` |
| Exit code | 0 |
| Duration | ~0.4s |
| Result | **PASS** |

**Key output:**
```json
{"success": true, "run_id": "run_20260514T093438_719d0190", "decision": "approved", "sentinel": ".../approved"}
```

Sentinel file created at `.dev-factory/runs/run_20260514T093438_719d0190/approved`. The `review` command in autodev is a human-gate sentinel writer (not an automated LLM review), consistent with its help text: "Write an approved/rejected sentinel so a paused HumanReviewGate can resume."

---

### E — `autodev verify`

| Field | Value |
|---|---|
| Command | `autodev verify --run-id run_20260514T093438_719d0190 --repo-path /tmp/r7-brownfield` |
| Exit code | 0 |
| Duration | ~0.4s |
| Result | **PASS** |

**Key output:**
```json
{
  "rerun_tests": [],
  "milestone_acceptance": {"MBUG-1": "passed"},
  "state_integrity_ok": true,
  "status": "passed",
  "notes": ["verification observed mock executor usage — cannot claim production-passed"]
}
```

Verification correctly noted mock executor with appropriate caveat. State integrity check passed.

---

### F — `autodev report`

| Field | Value |
|---|---|
| Command | `autodev report --run-id run_20260514T093438_719d0190 --repo-path /tmp/r7-brownfield` |
| Exit code | 0 |
| Duration | ~0.4s |
| Result | **PASS** |

**Report file:** `.dev-factory/runs/run_20260514T093438_719d0190/delivery/final_report.md`

Report contains:
- Repo path: `/private/tmp/r7-brownfield` ✓
- Bug reference: "divide function in calculator.py raises ZeroDivisionError when b==0 due to missing zero-check guard" ✓
- Fix reference: MBUG-1 / 4-stage bug fix / success=True ✓
- NOT_PRODUCTION warning banner with DryRun=True and MockExecutionUsed=True ✓

---

## Cross-Check: Source File Mutations

```bash
find /tmp/r7-brownfield -newer /tmp/r7-brownfield/.git -type f \
  -not -path '*/.dev-factory/*' -not -path '*/.git/*'
```

**Result: 0 files modified outside `.dev-factory/`**

All source files (`src/`, `tests/`, `pyproject.toml`, `README.md`) were untouched. autodev correctly isolated all mutations to `.dev-factory/`.

---

## Audit Tree

```
.dev-factory/
├── investigations/
│   └── divide-function-in-calculator-py-raises.md
└── runs/
    └── run_20260514T093438_719d0190/
        ├── approved                          ← review sentinel
        ├── delivery/
        │   └── final_report.md
        ├── execution/
        │   ├── codex_calls.jsonl
        │   ├── execution_calls.jsonl
        │   ├── executor_selection_BUG-T1-REPRODUCE.json
        │   ├── executor_selection_BUG-T2-LOCATE.json
        │   ├── executor_selection_BUG-T3-PATCH.json
        │   ├── executor_selection_BUG-T4-VERIFY.json
        │   └── milestone_MBUG-1_results.json
        ├── planning/
        │   └── tasks.json
        ├── run_state.json
        └── verification/
            └── verification_report.json
```

Audit tree is complete: planning, execution (per-task), verification, delivery, and review sentinel all present.

---

## Findings

| # | Severity | Title | Detail |
|---|---|---|---|
| 1 | P2 | Investigation grep scope leak | `autodev investigate` greps from process CWD (main autodev repo) instead of `--repo-path`. Found 4 hits in autodev's own `.venv` and `tests/unit/test_edge_case_hunter.py` — none from the brownfield's `src/widgetlib/calculator.py`. Evidence is polluted with irrelevant files from the host tool's repo. |
| 2 | P3 | Mock executor ghost changed_files | Each mock task declares `changed_files` paths under `.dev-factory/mock/codex_BUG-T*-*.txt`, but the `mock/` directory is never created. Downstream consumers checking changed_files would see phantom entries. |
| 3 | P3 | No project-file hit in investigation | The investigation case file found 5 evidence hits but none point to the actual brownfield source file `src/widgetlib/calculator.py`. The hypothesis is user-supplied, not derived from code evidence. This limits the value of `investigate` as a discovery tool in the current implementation. |

---

## Report Quality

| Check | Result |
|---|---|
| References correct repo | ✓ `/private/tmp/r7-brownfield` |
| References bug | ✓ `divide function... ZeroDivisionError when b==0` |
| References proposed fix | ✓ `MBUG-1 success=True`, 4-stage plan in `tasks.json` |
| Human-readable | ✓ Markdown with warning banner, milestone summary, verification status |
| NOT_PRODUCTION banner | ✓ DryRun=True, MockExecutionUsed=True clearly stated |

---

## Evidence Files

- `/tmp/r7-brownfield/.dev-factory/investigations/divide-function-in-calculator-py-raises.md`
- `/tmp/r7-brownfield/.dev-factory/runs/run_20260514T093438_719d0190/run_state.json`
- `/tmp/r7-brownfield/.dev-factory/runs/run_20260514T093438_719d0190/execution/milestone_MBUG-1_results.json`
- `/tmp/r7-brownfield/.dev-factory/runs/run_20260514T093438_719d0190/verification/verification_report.json`
- `/tmp/r7-brownfield/.dev-factory/runs/run_20260514T093438_719d0190/delivery/final_report.md`
- `/tmp/r7-brownfield/.dev-factory/runs/run_20260514T093438_719d0190/approved`

---

## Cleanup

```bash
rm -rf /tmp/r7-brownfield
```
