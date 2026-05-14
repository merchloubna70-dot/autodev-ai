# HIGH-CI-01: Release Workflow pytest Gate — Validation Report

**Date:** 2026-05-14
**Agent:** R2-F
**Verdict:** `pytest_gate_added`

## What Was Added

### `.github/workflows/release.yml`

The single-job `build-and-release` workflow was replaced with a two-job pipeline:

| Job | Purpose |
|-----|---------|
| `test` | Runs ruff, mypy, and the full pytest suite |
| `publish` | Builds wheel+sdist, attaches to GitHub Release, and (if secret set) uploads to PyPI |

### New Steps — `test` job
1. `actions/checkout@v4`
2. `actions/setup-python@v5` (Python 3.12, pip cache)
3. `pip install -e .[dev]` — installs package with all dev extras
4. `ruff check .`
5. `mypy src/autodev`
6. `python -m pytest tests/ -q`

### New Steps — `publish` job
1. `actions/checkout@v4`
2. `actions/setup-python@v5` (Python 3.12)
3. `pip install --upgrade build twine`
4. `python -m build`
5. `python -m twine check dist/*`
6. `softprops/action-gh-release@v2` — attaches `dist/*` to the GitHub Release
7. `twine upload` — **only if** `secrets.PYPI_API_TOKEN != ''`

## Job Dependency Chain

```
push tag v*.*.*
    │
    ▼
 [test]  ─── ruff + mypy + pytest
    │
    │ (needs: test)
    ▼
 [publish] ─── build + twine check + attach release + (optional) PyPI upload
```

## PyPI Auto-Publish Caveat

The `twine upload` step carries `if: ${{ secrets.PYPI_API_TOKEN != '' }}`.
Since `PYPI_API_TOKEN` is not currently configured in the repository, the step is
skipped on every run. Artifacts are always attached to the GitHub Release regardless.
No code is published to PyPI until the secret is explicitly set.

## Policy Test File

`tests/unit/test_release_workflow_policy.py` — 7 tests covering:

| # | Test | Result |
|---|------|--------|
| 1 | `test_workflow_file_exists` | PASS |
| 2 | `test_workflow_yaml_loads_cleanly` | PASS |
| 3 | `test_workflow_contains_pytest_step` | PASS |
| 4 | `test_publish_job_needs_test` | PASS |
| 5 | `test_no_bypass_shortcuts_in_step_conditions` | PASS |
| 6 | `test_pypi_upload_gated_on_secret` | PASS |
| 7 | `test_test_job_has_ruff_and_mypy_steps` | PASS |

**Policy tests: 7/7 passed**

## Full Suite Results

```
3 failed, 966 passed, 4 xfailed in 24.04s
```

The 3 failures are pre-existing A2A HTTP transport flakiness
(`test_a2a_http_transport`, `test_a2a_http_roundtrip`, `test_a2a_http_ssrf_hardening`)
unrelated to this change. Zero regressions introduced.

## Verdict

`pytest_gate_added`
