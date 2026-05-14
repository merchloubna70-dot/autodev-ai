# R3-C Ruff Lint Closure

**Date:** 2026-05-14  
**Round:** R3-C  
**Result:** CLEAN — 0 ruff errors

## Error Count

| State  | Count |
|--------|-------|
| Before | 55    |
| After  | 0     |

- Auto-fixed (ruff --fix): 46
- Manual fixes: 9
- `# noqa` added: 0 (no blanket suppressions used)

## Per-File Fix Categories

### scripts/
**`scripts/release_readiness_gate.py`**
- Auto: I001 (import sort), F541 ×3 (f-strings without placeholders)
- Manual: RUF059 ×3 — renamed `stdout2`, `stderr2`, `stdout` to `_stdout2`, `_stderr2`, `_stdout`

### src/
**`src/autodev/adapters/a2a/transports/http.py`**
- Auto: I001 (import sort)

**`src/autodev/executors/worker_isolator.py`**
- Manual: B904 ×2 — added `from exc` to both `except ValueError` handlers so exception chaining is explicit

### tests/
**`tests/integration/test_mcp_server_smoke.py`**
- Manual: RUF059 — `stdout` → `_stdout`

**`tests/unit/test_a2a_dns_rebinding_hardening.py`**
- Manual: RUF059 ×3 — `body` → `_body` in three call sites

**`tests/unit/test_executor_boundary_smoke.py`**
- Manual: RUF059 — `decision` → `_decision`

**`tests/unit/test_milestone_flow.py`**
- Manual: F841 — dropped assignment `result = flow.run(inp)` → `flow.run(inp)`

**`tests/unit/test_release_flow.py`**
- Auto: F401 ×7 (unused imports), F811 ×1 (GateStatus redefinition)

**`tests/unit/test_release_readiness_gate.py`**
- Auto: F401 ×2 (sys, MagicMock)

**`tests/unit/test_release_workflow_policy.py`**
- Auto: F401 (pytest)

**`tests/unit/test_version_consistency.py`**
- Auto: I001 (import sort)

**`tests/unit/test_worker_isolator_symlink_hardening.py`**
- Auto: I001 (import sort), F401 (os unused)

## `# noqa` Added

None. All violations were fixed at the source.

## lint.yml Expansion

| Field   | Before                          | After                              |
|---------|---------------------------------|------------------------------------|
| ruff    | `ruff check src/ tests/`        | `ruff check src tests scripts`     |
| mypy    | `mypy src/ ...`                 | `mypy src/autodev ...`             |

`scripts/` is now covered by CI ruff. mypy target narrowed to the typed package only (scripts are imperative, not typed).

## Policy Tests (`tests/unit/test_lint_workflow_policy.py`)

4 tests, all pass:
1. `test_lint_workflow_file_exists` — workflow file exists on disk
2. `test_lint_workflow_yaml_loads_cleanly` — YAML parses to dict with `jobs` key
3. `test_lint_workflow_ruff_covers_scripts` — substring `scripts` present in ruff step
4. `test_lint_workflow_ruff_covers_src_and_tests` — both `src` and `tests` present in ruff step

## Full Suite

| Outcome  | Count |
|----------|-------|
| Passed   | 1061  |
| xfailed  | 4     |
| Failed   | 1     |

The 1 failure (`test_formula_sha256_placeholder_is_explicit`) is pre-existing and unrelated to ruff changes — it expects `REPLACE_WITH` substring but the formula has `TODO_PUBLISH_SHA256`.

## Verdict

**`clean`** — 0 ruff errors, 0 blanket noqa suppressions, 4/4 policy tests pass, full suite at 1061 passed (no regressions from this work).
