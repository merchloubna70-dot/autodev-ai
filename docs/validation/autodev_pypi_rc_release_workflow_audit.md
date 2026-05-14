# autodev PyPI RC Release Workflow Audit

**Round:** pypi_rc_release_workflow_audit
**Date:** 2026-05-14
**Workflow file:** `.github/workflows/release.yml`
**Verdict:** ready_for_tag_push

---

## Workflow File

`.github/workflows/release.yml` — 66 lines, YAML valid.

---

## Triggers

| Trigger | Pattern | Matches `v0.1.0a1`? |
|---|---|---|
| `push.tags` | `v*.*.*` | **Yes** |
| `workflow_dispatch` | — | Not present |

GitHub's fnmatch glob `v*.*.*` splits on literal dots. The third segment `*` is greedy and matches `0a1`, so `v0.1.0a1` triggers the workflow. No manual dispatch is available.

---

## Job Chain

```
test  ──►  publish (needs: test)
```

**test** (6 steps, `ubuntu-latest`):
1. `actions/checkout@v4`
2. `actions/setup-python@v5` — Python 3.12, pip cache
3. `pip install -e .[dev]`
4. `ruff check .`
5. `mypy src/autodev`
6. `python -m pytest tests/ -q`

**publish** (7 steps, `ubuntu-latest`):
1. `actions/checkout@v4`
2. `actions/setup-python@v5` — Python 3.12, pip cache
3. `pip install --upgrade build twine`
4. `python -m build` — produces `dist/`
5. `python -m twine check dist/*`
6. `softprops/action-gh-release@v2` — attaches `dist/*`, auto-generates release notes
7. `twine upload` — **guarded** by `if: ${{ secrets.PYPI_API_TOKEN != '' }}`

---

## Token Guard

```yaml
if: ${{ secrets.PYPI_API_TOKEN != '' }}
env:
  PYPI_API_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
run: twine upload --non-interactive -u __token__ -p "$PYPI_API_TOKEN" dist/*
```

Token is scoped to the single upload step. Not echoed, not written to any file, not exported at job or workflow level.

---

## Publish Behavior

| Scenario | Result |
|---|---|
| Token set, tests pass | PyPI upload + GitHub Release with `dist/*` |
| Token unset, tests pass | GitHub Release with `dist/*` only; upload step skipped |
| Tests fail | Publish job never runs |

---

## Permissions

| Level | Key | Value |
|---|---|---|
| Workflow | `contents` | `write` |
| Job | — | (none declared) |

`contents:write` is required for `softprops/action-gh-release` to create the release and attach assets. No `id-token:write` (OIDC trusted publishing is not used). Permissions are appropriately minimal.

---

## Environment Protection

**Not present.** Neither job declares `environment:`. There is no required-reviewer gate before PyPI publish. Any push of a `v*.*.*` tag will trigger an immediate publish attempt (after tests pass) if the token is set.

---

## Findings

| Severity | Category | Detail |
|---|---|---|
| Low | Secret exposure | Token is passed via `-p "$PYPI_API_TOKEN"` CLI flag. Process args are visible in `/proc/<pid>/cmdline` before runner masking applies. Safer: use `TWINE_PASSWORD` env var; twine reads it automatically, keeping the secret out of the process argument list. |
| Info | No environment gate | No `environment:` declaration means no manual-approval gate for PyPI publish. Acceptable for alpha; recommended for stable releases. |
| Info | No workflow_dispatch | Cannot re-run publish without re-pushing the tag. If upload fails partway, recovery requires tag deletion and re-push. |
| Info | Action pinning | Actions use major-version tags (`@v4`, `@v5`, `@v2`) rather than immutable SHA digests. Low risk for these well-audited actions; SHA pinning is best practice for supply-chain hardening. |

---

## Verdict

**ready_for_tag_push.** Pushing tag `v0.1.0a1` will safely trigger the workflow:

- Tests (ruff + mypy + pytest) gate the publish job.
- If `PYPI_API_TOKEN` is set in repo secrets, artifacts are uploaded to PyPI.
- If `PYPI_API_TOKEN` is unset, the upload step is skipped and a GitHub Release is still created with the wheel and sdist attached.
- No step prints or persists the token. The one low-severity finding (token as CLI arg) is mitigated by GitHub runner masking and is not a blocker for RC publication.
