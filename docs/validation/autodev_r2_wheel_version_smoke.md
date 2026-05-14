# HIGH-DIST-01 Closure: Wheel v0.1.0a1 Rebuild and CLI Version Smoke

**Date:** 2026-05-14
**Verdict:** closed

## Rebuild Result

Old `dist/` artifacts (`0.1.0`) were removed and rebuilt from `pyproject.toml` version `0.1.0a1`:

```
rm -rf dist/ && python -m build
Successfully built autodev_ai-0.1.0a1.tar.gz and autodev_ai-0.1.0a1-py3-none-any.whl
```

## Artifacts

| File | SHA-256 | Size |
|------|---------|------|
| `autodev_ai-0.1.0a1-py3-none-any.whl` | `39c39f5ce680ebc5d66f6694ba52bdb457727ac72350b94d5a9d143d62f8cee7` | 303,493 bytes |
| `autodev_ai-0.1.0a1.tar.gz` | `4c2f73569377a92c634b7e112f08ce5a90896e077abf6aa48e5f8dc20c2e000e` | 572,978 bytes |

## Actual `--version` Output (fresh venv, python3.12)

```
autodev-ai 0.1.0a1
```

## Test Results (6/6 PASS)

| Test | Status |
|------|--------|
| `test_wheel_file_exists` | PASS |
| `test_sdist_file_exists` | PASS |
| `test_wheel_installs_in_clean_venv` | PASS |
| `test_wheel_autodev_help_works` | PASS |
| `test_wheel_autodev_version_outputs_0_1_0a1` | PASS |
| `test_wheel_module_form_version_works` | PASS |

Tests located at: `tests/integration/test_wheel_cli_version_smoke.py`

## Full Suite

```
1 failed (pre-existing: test_release_readiness_gate::test_overall_pass_when_all_pass),
975 passed, 4 xfailed, 0 new failures
```

The pre-existing failure in `test_release_readiness_gate` is unrelated to this change (it predates the R2 round).

## Verdict

**closed** — `dist/` now contains correct `0.1.0a1` artifacts; `autodev --version` and `python -m autodev.cli --version` both return `autodev-ai 0.1.0a1` from a clean python3.12 venv install; all 6 smoke tests pass.
