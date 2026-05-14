# Round 7 — Agent 5: Continue-Run / Replay E2E Validation Report

**Date:** 2026-05-14  
**Agent:** 5 — continue_replay  
**Project:** autodev-ai v0.1.0a3 @ main HEAD 0a227d4  
**Sandbox:** /tmp/r7-replay-sandbox (git-inited, cleaned after)  

---

## Summary

`continue-run` is an incomplete stub that only lists remaining milestones but performs no execution or state transition. `replay` executes successfully but is **non-deterministic** across runs and **mutates** the original run's artifacts. Neither command handles errors gracefully — all failures surface as raw Python tracebacks with exit code 1 rather than user-friendly error messages.

**Overall result: partial**

---

## RunState Disk Layout

| Field | Value |
|---|---|
| Runs directory | `<repo_path>/.dev-factory/runs/` |
| State file | `<runs_dir>/<run_id>/run_state.json` |
| Subdirectories | `input/`, `product/`, `architecture/`, `planning/`, `execution/`, `quality/`, `verification/`, `delivery/` |
| Execution logs | `execution/execution_calls.jsonl`, `execution/codex_calls.jsonl`, `execution/claude_code_calls.jsonl` |
| Key fields in run_state.json | `run_id`, `started_at`, `finished_at`, `mode`, `flow`, `repo_path`, `languages`, `classification`, `product_brief`, `prd`, `architecture`, `milestone_plan`, `implementation_results`, `quality_gates`, `security_review`, `code_review`, `verification`, `release_check`, `backends_used`, `mock_execution_used`, `errors` |

---

## Scenario A — Happy Path

**Result: PASS**

- Command: `FACTORY_FORCE_MOCK=1 autodev deliver-project --repo-path /tmp/r7-replay-sandbox --project-brief brief.txt --project-name hello-world --languages python --mode dry-run --allow-mock-executor true`
- Exit code: 0
- Run ID created: `run_20260514T093202_513070cc`
- Artifacts produced: 38 files across all 8 subdirs
- `run_state.json` correctly persists all pipeline fields; `finished_at` is set; `mock_execution_used=true`
- `backends_used: ["mock_codex"]`

---

## Scenario B — Paused State Construction

**Result: PASS (technique documented)**

**Technique used:** Direct JSON mutation of `run_state.json`

```python
# Set implementation_results=[] and finished_at=None to simulate interrupted run
d['implementation_results'] = []
d['finished_at'] = None
```

- This correctly makes `continue-run` see M2 as remaining
- Limitation: no native "pause" mechanism exists in the framework; interruption must be simulated via JSON mutation
- There is no `status` or `state` field in `PipelineRunState` — "paused" is inferred from empty `implementation_results`

---

## Scenario C — continue-run

**Result: FAIL (P1)**

- Command: `autodev continue-run --run-id run_20260514T093202_513070cc --repo-path /tmp/r7-replay-sandbox`
- Exit code: 0
- Output: `remaining milestones: ['M2']`
- **Critical finding:** `continue-run` is a stub — it only prints remaining milestones but does NOT re-execute them, does NOT resume execution, and does NOT transition state to "done". The CLI command body (cli.py:332-341) contains only a `typer.echo` with no actual resumption logic.
- State remains "paused" (implementation_results=[]) after running continue-run.

---

## Scenario D — Replay Stability

**Result: FAIL (P2)**

- Command: `autodev replay --run-id <id> --repo-path /tmp/r7-replay-sandbox --from-stage planning`
- Exit code: 0 (both runs)
- Replay appends audit note to `state.errors`: `"replayed from stage planning at <timestamp>"`
- `run_state.json` is mutated (replay appends to `errors[]` and updates `implementation_results`)

**Hash stability check (2 consecutive replays):**
- `planning/milestones.json`: changed between replays
- `planning/tasks.json`: changed between replays
- `execution/milestone_M*.json`: all change between replays (different task IDs, timestamps)
- `execution/execution_calls.jsonl`: changed
- `verification/verification_report.json`: changed
- `verification/release_check.json`: changed
- `run_state.json`: changed

**Conclusion:** Replay is non-deterministic. LLM-backed agents generate different content on each call, and timestamps in artifacts differ. Additionally, replay mutates the original run's artifacts in-place — there is no snapshot-before-replay protection.

---

## Scenario E1 — Missing File Handling

**Result: FAIL (P1)**

- Test: Delete `input/classification.json` then run `continue-run`
- Finding: `continue-run` loads state from `run_state.json` only (not from individual artifact files), so deleting a sidecar JSON file does NOT cause failure — state is self-contained.
- However, deleting the run directory or using a non-existent run_id causes:
  ```
  FileNotFoundError: run not found: /private/tmp/r7-replay-sandbox/.dev-factory/runs/nonexistent_run_id
  ```
  This bubbles up as a **raw Python traceback** (Rich-formatted) with exit code 1.
- **No graceful error handling** — raw `FileNotFoundError` surfaces to the user.

---

## Scenario E2 — Corrupt JSON Handling

**Result: FAIL (P1)**

- Test: Write `{garbage` to `run_state.json`, then run `autodev replay`
- Result:
  ```
  JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
  ```
- Surfaces as raw Python traceback (Rich-formatted) with exit code 1.
- No graceful error handling, no user-friendly message like "run_state.json is corrupt, cannot load run".

---

## Scenario E3 — Invalid State Value Handling

**Result: FAIL (P1)**

- Test: Set `mode` to `"invalid_state_value"` in `run_state.json`, then run `autodev continue-run`
- Result:
  ```
  ValidationError: 1 validation error for PipelineRunState
  mode
    Input should be 'dry-run' or 'apply' [type=enum, input_value='invalid_state_value', ...]
  ```
- Surfaces as raw Pydantic `ValidationError` traceback with exit code 1.
- The error message from Pydantic is informative but the full traceback is user-unfriendly.

**Note:** `replay --from-stage invalid_stage` raises a `ValueError` with a useful message (`Unknown stage 'invalid_stage'. Valid stages: [...]`) but also surfaces as raw traceback.

---

## Findings

| Severity | Title | Detail |
|---|---|---|
| P0 | `continue-run` is a stub with no execution logic | cli.py:332-341 only prints remaining milestones; does not resume pipeline; no execution, no state transition, no "done" signal |
| P1 | Missing file / nonexistent run_id raises raw `FileNotFoundError` traceback | `RunState.load()` raises unhandled exception; should be caught at CLI layer with friendly message and non-zero exit |
| P1 | Corrupted `run_state.json` raises raw `JSONDecodeError` traceback | `read_json()` raises unhandled exception; should be caught at CLI layer |
| P1 | Invalid enum value in `run_state.json` raises raw Pydantic `ValidationError` traceback | `model_validate()` raises unhandled exception; should be caught at CLI layer |
| P2 | `replay` is non-deterministic — artifacts differ between runs | Milestones, tasks, execution results all regenerated with new timestamps and LLM-generated content each replay |
| P2 | `replay` mutates original run artifacts in-place | No snapshot-before-replay; `milestones.json`, `tasks.json`, `execution/` all overwritten; original state lost |
| P3 | No native "paused" state concept | Simulating paused requires JSON mutation; no first-class interrupt/resume checkpoint mechanism |
| P3 | Pydantic `UserWarning` for `model_hint`/`model_settings` namespace conflict printed on every CLI invocation | Minor UX pollution; `model_config['protected_namespaces'] = ()` should be set on affected models |

---

## Commands Run

| Command | Exit | Duration (ms) |
|---|---|---|
| `autodev deliver-project --mode dry-run --allow-mock-executor true ...` | 0 | ~510 |
| `autodev continue-run --run-id <id> ...` (paused state) | 0 | ~350 |
| `autodev replay --run-id <id> --from-stage planning` (run 1) | 0 | ~457 |
| `autodev replay --run-id <id> --from-stage planning` (run 2) | 0 | ~420 |
| `autodev continue-run --run-id nonexistent_run_id` | 1 | ~300 |
| `autodev replay --run-id <id>` (corrupt JSON) | 1 | ~290 |
| `autodev continue-run --run-id <id>` (invalid mode enum) | 1 | ~310 |
| `autodev replay --run-id <id> --from-stage invalid_stage` | 1 | ~300 |

---

## Evidence Files

- `/tmp/r7-hashes-before.txt` — MD5 hashes of all run artifacts before any replay
- `/tmp/r7-hashes-after-replay.txt` — MD5 hashes after first replay
- `/tmp/r7-hashes-after-replay2.txt` — MD5 hashes after second replay (instability evidence)
- Sandbox cleaned: `rm -rf /tmp/r7-replay-sandbox`
