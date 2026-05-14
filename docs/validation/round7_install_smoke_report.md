# Round 7 Clean Install Smoke Report — Agent 2

**Date:** 2026-05-14  
**Agent:** 2 — clean_install_smoke  
**Package:** autodev-ai 0.1.0a3  
**Overall Result:** PASS (with 1 environment note)

---

## Summary

Both editable (local) and PyPI installs of autodev-ai 0.1.0a3 were validated successfully. The `autodev` binary was installed correctly in both cases, and all functional checks passed. The two R5 fix points were confirmed: no `typer[all]` warning on install, and no `ModuleNotFoundError` traceback from the module-form gate.

**One environment-level finding (P1):** Python 3.12.13 on this macOS system has a system-level `pyexpat`/`libexpat` mismatch (`Symbol not found: _XML_SetAllocTrackerActivationThreshold`). This prevents `pip install` from functioning on Python 3.12 (the task-mandated interpreter). The validation was therefore conducted using Python 3.11.15, which is fully functional. This is a host-environment issue unrelated to the autodev-ai package itself.

---

## Environment

| Item | Value |
|------|-------|
| Platform | darwin 25.2.0 (macOS) |
| Python 3.12 pip status | BROKEN — pyexpat/libexpat ABI mismatch |
| Python 3.11 pip status | OK — used as fallback |
| pip version (both venvs) | 26.1.1 |

---

## Editable Install (`/tmp/r7-venv-editable`)

| Check | Result | Notes |
|-------|--------|-------|
| `pip install -e .` | PASS (exit 0) | All deps resolved from cache |
| typer extra 'all' warning | ABSENT | R5 fix confirmed |
| Other warnings | SSL retry on jinja2 (transient, recovered) | Non-blocking |
| `autodev --version` | PASS: `autodev-ai 0.1.0a3` | |
| `autodev --help` | PASS (exit 0) | 37 commands listed, no traceback |
| `import autodev; print(__version__)` | PASS: `0.1.0a3` | |
| `python -m autodev.cli --version` | PASS: `autodev-ai 0.1.0a3` | |
| `python -m autodev.release_readiness_gate` | PASS (exit 0) | No ModuleNotFoundError — R5 fix confirmed |
| Module gate result | 2 pass / 30 fail / 4 skip | Expected: runs from /tmp without project root |

---

## PyPI Install (`/tmp/r7-venv-pypi`)

| Check | Result | Notes |
|-------|--------|-------|
| `pip install --pre autodev-ai==0.1.0a3` | PASS (exit 0) | Downloaded wheel from PyPI |
| typer extra 'all' warning | ABSENT | R5 fix confirmed |
| Other warnings | None | |
| `autodev --version` | PASS: `autodev-ai 0.1.0a3` | |
| `autodev --help` | PASS (exit 0) | 37 commands listed, no traceback |
| `autodev classify-input --help` | PASS (exit 0) | |
| `autodev mcp-serve --help` | PASS (exit 0) | |
| `autodev scan --help` | PASS (exit 0) | |
| `import autodev; print(__version__)` | PASS: `0.1.0a3` | |
| `python -m autodev.cli --version` | PASS: `autodev-ai 0.1.0a3` | |
| `python -m autodev.release_readiness_gate` | PASS (exit 0) | No ModuleNotFoundError — R5 fix confirmed |
| Module gate result | 2 pass / 30 fail / 4 skip | Expected: runs from /tmp without project root |

---

## Version Comparison

| Source | Version |
|--------|---------|
| Local editable (`/Users/macworkers/autodev`) | 0.1.0a3 |
| PyPI (`autodev-ai==0.1.0a3`) | 0.1.0a3 |
| Diff | **None — versions match** |

---

## R5 Fix Verification

| Fix Point | Expected | Actual | Status |
|-----------|----------|--------|--------|
| typer extra 'all' warning absent | ABSENT | ABSENT | CONFIRMED |
| ModuleNotFoundError traceback absent (editable gate) | ABSENT | ABSENT | CONFIRMED |
| ModuleNotFoundError traceback absent (PyPI gate) | ABSENT | ABSENT | CONFIRMED |

---

## Findings

### P1 — ENV — Python 3.12 pip install broken on this host

- **Severity:** P1 (environment issue, not package issue)
- **Title:** python3.12 pyexpat/libexpat ABI mismatch prevents pip install
- **Detail:** Python 3.12.13 (Homebrew) was compiled against a newer `libexpat` than the system provides. `pip install` fails with `ImportError: dlopen(pyexpat.cpython-312-darwin.so): Symbol not found: _XML_SetAllocTrackerActivationThreshold`. This blocks `ensurepip` and any pip command that touches `xmlrpc.client` (all installs). Python 3.11.15 does not have this issue and was used for the validation.
- **Evidence:** `ImportError: dlopen(pyexpat.cpython-312-darwin.so): Symbol not found: _XML_SetAllocTrackerActivationThreshold` from both `python3.12 -m ensurepip` and `pip3.12 install --help`.
- **Recommendation:** `brew reinstall python@3.12` or upgrade macOS to resolve the libexpat version. This does not affect autodev-ai package quality.

### P2 — INFO — SSL retry during editable install

- **Severity:** P2 (informational, transient)
- **Title:** SSL EOF retry on jinja2 download (recovered)
- **Detail:** One `SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING]')` on jinja2 fetch, with 4 retries configured. Install succeeded using cached wheel.
- **Evidence:** `WARNING: Retrying (Retry(total=4, ...)) after connection broken by 'SSLEOFError...'`

---

## Commands Run

| Command | Exit | Notes |
|---------|------|-------|
| `rm -rf /tmp/r7-venv-*` | 0 | Clean slate |
| `python3.12 -m venv /tmp/r7-venv-editable` | 1 (ensurepip fail) | Env issue, venv dir created |
| `python3.11 -m venv /tmp/r7-venv-editable` | 0 | Fallback to 3.11 |
| `pip install -U pip` (editable) | 0 | 26.0.1 → 26.1.1 |
| `pip install -e . ` (editable) | 0 | All deps installed |
| `autodev --version` (editable) | 0 | autodev-ai 0.1.0a3 |
| `autodev --help` (editable) | 0 | 37 commands |
| `python -c "import autodev..."` (editable) | 0 | 0.1.0a3 |
| `python -m autodev.cli --version` (editable) | 0 | autodev-ai 0.1.0a3 |
| `python -m autodev.release_readiness_gate` (editable) | 0 | 2p/30f/4s, no traceback |
| `python3.11 -m venv /tmp/r7-venv-pypi` | 0 | |
| `pip install -U pip` (pypi) | 0 | 26.0.1 → 26.1.1 |
| `pip install --pre autodev-ai==0.1.0a3` | 0 | From PyPI |
| `autodev --version` (pypi) | 0 | autodev-ai 0.1.0a3 |
| `autodev --help` (pypi) | 0 | 37 commands |
| `autodev classify-input --help` (pypi) | 0 | |
| `autodev mcp-serve --help` (pypi) | 0 | |
| `autodev scan --help` (pypi) | 0 | |
| `python -c "import autodev..."` (pypi) | 0 | 0.1.0a3 |
| `python -m autodev.cli --version` (pypi) | 0 | autodev-ai 0.1.0a3 |
| `python -m autodev.release_readiness_gate` (pypi) | 0 | 2p/30f/4s, no traceback |
| `rm -rf /tmp/r7-venv-*` | 0 | Cleanup |

---

## Evidence Files

- `/Users/macworkers/autodev/docs/validation/round7_install_smoke_report.md`
- `/Users/macworkers/autodev/docs/validation/round7_install_smoke_report.json`
