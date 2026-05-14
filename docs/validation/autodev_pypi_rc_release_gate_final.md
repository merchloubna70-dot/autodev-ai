# PyPI RC Release Readiness Gate — Final Run

**Version**: `0.1.0a1`
**Verdict**: `rc_ready_no_technical_blockers`

All 36 gate checks pass. All four strict modes exit 0.

## Inventory

```
Total checks : 36
  BASE       : 12  (package metadata, CLI help, pytest evidence, ruff,
                    mypy, docs, MCP/A2A smoke paths, mock executor,
                    packaging files, dangerous claims, blockers recorded)
  R2 P0      : 12  (version, license, wheel --version, SSRF, flow tests,
                    release.yml pytest, Homebrew metadata, Info.plist)
  R3 P0      : 12  (mypy, ruff, lint scripts, MCP guardrail, DNS rebinding,
                    symlink hardening, CHANGELOG, configuration,
                    troubleshooting, Docker digest, Homebrew honest,
                    PyPI-RC not blocked by Homebrew)
```

## Run results

```
$ python scripts/release_readiness_gate.py
=== Release Readiness Gate ===
  overall : pass
  pass    : 36
  fail    : 0
  skip    : 0
```

## Strict modes (all exit 0)

| Flag | Exit | Semantics |
|---|---:|---|
| `--strict` | 0 | Fail if ANY check fails. |
| `--strict-r2` | 0 | Fail if any R2 check fails. |
| `--strict-r3` | 0 | Fail if any R3 check fails. |
| `--strict-rc` | 0 | Fail if any non-Homebrew-publish check fails — separates PyPI RC verdict from Homebrew sha256 dependency. |

## Module form

```
$ python -m autodev.release_readiness_gate
```

Module shim at `src/autodev/release_readiness_gate.py` exits 0; equivalent to the standalone script.

## Operational dependency (not technical)

Before tag push triggers PyPI upload, the user must set:

```
GitHub Repo Settings → Secrets and variables → Actions → New repository secret
Name : PYPI_API_TOKEN
Value: <your PyPI API token, scoped to autodev-ai or account-wide>
```

URL: https://github.com/merchloubna70-dot/autodev-ai/settings/secrets/actions

Without the secret: release.yml's `test` job runs, the `publish` job runs `python -m build` + `twine check` + attaches artifacts to the GitHub Release, but the `twine upload` step is **skipped** (`if: ${{ secrets.PYPI_API_TOKEN != '' }}`). So you can dry-run a tag push to verify the workflow end-to-end without publishing to PyPI.
