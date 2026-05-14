# R4 Release Workflow Secret Handling — Validation Report

**Round:** R4-E (Security XFail Closure)
**Date:** 2026-05-14
**File changed:** `.github/workflows/release.yml`
**Test file changed:** `tests/unit/test_release_workflow_twine_password_policy.py`
**Status:** PASS

---

## Diff Summary

### Before (release.yml publish step)

```yaml
- name: Publish to PyPI
  if: ${{ secrets.PYPI_API_TOKEN != '' }}
  env:
    PYPI_API_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
  run: twine upload --non-interactive -u __token__ -p "$PYPI_API_TOKEN" dist/*
```

### After (release.yml publish step)

```yaml
- name: Publish to PyPI
  if: ${{ secrets.PYPI_API_TOKEN != '' }}
  env:
    TWINE_USERNAME: __token__
    TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
  run: python -m twine upload dist/*
```

**What changed:**
- Removed `-u __token__ -p "$PYPI_API_TOKEN"` CLI flags from `twine upload` invocation.
- Replaced with `TWINE_USERNAME` and `TWINE_PASSWORD` in the step `env` block.
- Removed the intermediate `PYPI_API_TOKEN` env var (no longer needed).
- Replaced `twine upload` bare call with `python -m twine upload` for consistency.

---

## xfail Annotations Removed

4 `@pytest.mark.xfail(strict=True)` annotations removed from:
`tests/unit/test_release_workflow_twine_password_policy.py`

| Test | Previous state | New state |
|---|---|---|
| `test_twine_upload_does_not_use_p_flag` | xfail(strict) | PASS |
| `test_twine_upload_uses_twine_password_env` | xfail(strict) | PASS |
| `test_twine_upload_does_not_inline_secret_in_run` | xfail(strict) | PASS |
| `test_twine_upload_command_is_minimal_without_auth_flags` | xfail(strict) | PASS |

Policy test run result: **5/5 PASS, 0 xfail**

---

## Security Checks

| Check | Result |
|---|---|
| `-p` flag near twine in release.yml | 0 hits |
| `echo.*TOKEN` in release.yml | 0 hits |
| Token inlined in `run:` block | No — token only in `env:` block |
| `TWINE_PASSWORD` set via `env:` | Yes |

---

## Workflow Invariants Preserved

| Requirement | Present |
|---|---|
| `publish` job has `needs: test` | Yes (line 36) |
| `twine check dist/*` before upload | Yes (line 54) |
| `softprops/action-gh-release@v2` attaches wheel + sdist | Yes (lines 57-60) |
| `if: ${{ secrets.PYPI_API_TOKEN != '' }}` on upload step | Yes (line 63) |
| Dry-run path (no secret) skips upload via `if:` guard | Yes |

---

## YAML Validity

`python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"` — clean, no errors.

---

## Verdict

PASS. The `-p` CLI flag pattern is fully removed. The token is now passed exclusively via the `TWINE_PASSWORD` environment variable, which is not visible in process listings (`ps aux`, `/proc/<pid>/cmdline`). The `if:` guard for the no-secret dry-run path is intact. All 4 formerly-xfail policy tests now pass without annotation.
