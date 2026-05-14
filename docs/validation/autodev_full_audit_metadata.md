# autodev-ai — Pre-Tag Full Audit: Metadata

**Round:** full_audit_metadata
**Agent:** PreTag-A
**Date:** 2026-05-14
**Verdict:** `tag_ready_from_metadata_pov`

---

## Summary

All 10 metadata checks pass. No version drift detected. Zero false publish claims. twine check PASSED for both dist artifacts. The package is metadata-ready for tag push and PyPI publish.

---

## Version Sources — Confirmed

| Source | Value | Status |
|---|---|---|
| `pyproject.toml [project] version` | `0.1.0a1` | PASS |
| `src/autodev/__init__.py` (`importlib.metadata`) | `0.1.0a1` | PASS |
| Runtime: `python -c "import autodev; print(autodev.__version__)"` | `0.1.0a1` | PASS |

No drift across any version source.

---

## Check Matrix

| # | Check | Expected | Actual | Result |
|---|---|---|---|---|
| 1 | `pyproject.toml` name | `autodev-ai` | `autodev-ai` | PASS |
| 2 | `pyproject.toml` version | `0.1.0a1` | `0.1.0a1` | PASS |
| 3 | `pyproject.toml` license | `MIT` (text) + `["LICENSE"]` (files) | matches | PASS |
| 4 | `pyproject.toml` classifiers count | 14 | 14 | PASS |
| 5 | `pyproject.toml` `[project.urls]` count | 5 | 5 | PASS |
| 6 | `pyproject.toml` `[project.scripts]` | `autodev = autodev.cli:app` | matches | PASS |
| 7 | `src/autodev/__init__.py` exports `__version__` | via `importlib.metadata` | confirmed | PASS |
| 8 | Runtime import version | `0.1.0a1` | `0.1.0a1` | PASS |
| 9 | `LICENSE` — MIT, 2026, "autodev-ai contributors" | all three | confirmed | PASS |
| 10 | `CHANGELOG.md` has `## [0.1.0a1]` marked Pre-Release | present | `## [0.1.0a1] — 2026-05-14 (Pre-Release)` | PASS |
| 11 | `README.md` pip URL contains `0.1.0a1` (not `0.1.0`) | `0.1.0a1` in wheel URL | `autodev_ai-0.1.0a1-py3-none-any.whl` | PASS |
| 12 | `README.md` `--pre` documented | present | `pip install --pre autodev-ai` | PASS |
| 13 | `docs/release_notes/v0.1.0a1.md` exists | present | confirmed | PASS |
| 14 | False publish claims (`available on PyPI`, `production-ready`, `enterprise-ready`) | 0 | 0 | PASS |
| 15 | `docs/release/pypi_0_1_0a1_publish_checklist.md` exists | present | confirmed | PASS |
| 16 | `docs/release/pypi_0_1_0a1_rollback_plan.md` exists | present | confirmed | PASS |
| 17 | `twine check dist/*` — wheel | PASSED | PASSED | PASS |
| 18 | `twine check dist/*` — sdist | PASSED | PASSED | PASS |

---

## Twine Check Output

```
Checking dist/autodev_ai-0.1.0a1-py3-none-any.whl: PASSED
Checking dist/autodev_ai-0.1.0a1.tar.gz: PASSED
```

---

## Diff vs RC Prep

No regression from RC-A state. All three inline fixes applied during the RC round are confirmed present:

- **F-1** — 14 classifiers now present in `pyproject.toml` (was 0 at RC-A start)
- **F-2** — 5 `[project.urls]` entries now present (was 0 at RC-A start)
- **F-3** — README pip URL corrected to `0.1.0a1` wheel path; `--pre` documented

---

## Notes

- `CHANGELOG.md` Notes section explicitly states "PyPI not yet published; install from the GitHub Release wheel or source." No false PyPI availability claim.
- `docs/release_notes/v0.1.0a1.md` Install section states "PyPI publish has not happened yet" — consistent with CHANGELOG.
- `LICENSE` copyright year is 2026 and holder is "autodev-ai contributors" — both match requirement.
- `src/autodev/__init__.py` uses `importlib.metadata.version("autodev-ai")` with fallback to `"0.0.0+local"` — clean pattern.
- Both dist artifacts present: `dist/autodev_ai-0.1.0a1-py3-none-any.whl` and `dist/autodev_ai-0.1.0a1.tar.gz`.

---

## Verdict

**`tag_ready_from_metadata_pov`** — all 18 checks pass, zero false publish claims, no version drift, twine clean. Operational prerequisite: set `PYPI_API_TOKEN` GitHub Secret before tag push (as noted in publish checklist and RC aggregator report).
