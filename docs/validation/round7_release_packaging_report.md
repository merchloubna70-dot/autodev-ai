# Round 7 Release Packaging Report
Agent 9 — Release Readiness / Packaging

**Date:** 2026-05-14  
**Overall Result:** partial  
**P0:** 0 | **P1:** 0 | **P2:** 3 | **P3:** 1

---

## Build Artifacts

| Artifact | Size | Status |
|---|---|---|
| `autodev_ai-0.1.0a3-py3-none-any.whl` | 327,340 bytes (320 KB) | BUILT |
| `autodev_ai-0.1.0a3.tar.gz` | 858,884 bytes (839 KB) | BUILT |

**Twine check:** Both PASSED (no metadata errors, README renders, classifiers valid).

Build used `uv venv` + `python -m build 1.5.0` + `hatchling` from clean sandbox at `/tmp/r7-build-sandbox/`.

---

## Install Smoke Tests

| Test | Command | Result |
|---|---|---|
| Wheel install | `pip install *.whl` → `autodev --version` | `autodev-ai 0.1.0a3` ✓ |
| Wheel help | `autodev --help` | exit 0 ✓ |
| Sdist install | `pip install *.tar.gz` → `autodev --version` | `autodev-ai 0.1.0a3` ✓ |

---

## Release Readiness Gate

Gate runs 36 checks total (34 pass, 2 fail across all runs).

| Flag | Exit | Result |
|---|---|---|
| `--strict` | 1 | FAIL (2 checks fail) |
| `--strict-r2` | 1 | FAIL (both are r2_ checks) |
| `--strict-r3` | 0 | PASS (all r3_ checks pass) |
| `--strict-rc` | 1 | FAIL (both fail checks included in RC scope) |
| module form (no flag) | 0 | PASS (design: exit 0 without strict flag) |

### Failing Checks

**r2_wheel_version_works** — wheel version `0.1.0a2` does not match pyproject `0.1.0a3`  
Root cause: `dist/` in the main repo contains stale build artifacts from the previous alpha (`autodev_ai-0.1.0a2-py3-none-any.whl`). The gate scans the repo's `dist/` directory, not a fresh build sandbox. Fix: run `python -m build` in the main repo to replace dist/ with 0.1.0a3 artifacts, or delete stale 0.1.0a2 files.

**r2_macos_info_plist_version_match** — Failed to parse Info.plist: `dlopen pyexpat.cpython-312-darwin.so Symbol not found _XML_SetAllocTrackerActivationThreshold`  
Root cause: Two sub-issues: (1) `packaging/desktop/autodev-ai.app/Contents/Info.plist` has `CFBundleShortVersionString=0.1.0a1` (stale by 2 alphas); (2) macOS local `libexpat.1.dylib` lacks the symbol expected by Homebrew python@3.12.13's `pyexpat` extension. The libexpat mismatch is a dev environment issue. The plist version staleness is actionable.

---

## release-check CLI

`autodev release-check --help`: exit 0, requires `--run-id`.  
Invoked with real run-id `run_20260514T053102_7a5b306f`: returned JSON with `decision: Blocked` (expected — mock executor + security issues in that run). CLI functional.

---

## Docker Build

Status: **PASS**

```
Successfully installed autodev-ai-0.1.0a3 (colima docker driver)
```

Notes:
- Used `docker build -t r7-smoke -f packaging/docker/Dockerfile /tmp/r7-build-sandbox/` (no `--target`)
- Task spec used `--target final` which **fails** — final runtime stage in Dockerfile is unnamed (only `builder` stage is named). Minor defect: naming the final stage `AS final` would satisfy `--target final`.
- Build context: sandbox with fresh 0.1.0a3 dist/ artifacts.

---

## Homebrew Audit

Status: **PASS** (matches baseline)

```
autodev-ai: 1 problem detected
  * Stable: `version 0.1.0a3` is redundant with version scanned from URL
```

1 warning, matches the known acceptable baseline (PEP 440 alpha version redundancy defense). No additional warnings beyond baseline.

---

## Findings

### P2 — Stale 0.1.0a2 wheel in main repo dist/

The main repo `dist/` has `autodev_ai-0.1.0a2-py3-none-any.whl` and `.tar.gz`. The gate's `r2_wheel_version_works` check finds the stale wheel and fails. This is not a packaging regression — the sandbox builds 0.1.0a3 cleanly — but it makes `--strict` and `--strict-rc` fail. Fix: rebuild dist/ from main repo or delete stale artifacts.

### P2 — Info.plist version stale at 0.1.0a1

`packaging/desktop/autodev-ai.app/Contents/Info.plist` has `CFBundleShortVersionString=0.1.0a1`. Should be `0.1.0a3`. This means macOS .app bundle metadata is 2 alphas behind.

### P2 — Docker Dockerfile final stage unnamed (--target final fails)

The task spec calls `--target final` but the Dockerfile's runtime stage has no name. `docker build` succeeds without `--target` but the explicit target call fails. Naming the last stage `AS final` fixes this.

### P3 — python@3.12 libexpat symbol mismatch on dev machine

Homebrew python@3.12.13's `pyexpat` extension references `_XML_SetAllocTrackerActivationThreshold` in `/usr/lib/libexpat.1.dylib`, which the system libexpat doesn't provide. Affects `plistlib` and `ensurepip`. Worked around with `uv venv`. Not a project defect.

---

## Environment Notes

- `python3.12 -m venv` broken on this dev machine due to libexpat mismatch; `uv venv --python 3.12` used as workaround
- Build venv used `uv pip install build twine` successfully
- All smoke tests ran against fresh isolated venvs (no editable install leakage)

---

## Evidence Files

- `/Users/macworkers/autodev/docs/validation/round7_release_packaging_report.json`
- `/Users/macworkers/autodev/docs/validation/round7_release_packaging_report.md`
- `/Users/macworkers/autodev/docs/validation/release_readiness_gate_run.json` (gate run artifact)
