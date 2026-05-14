# R5 Fix: release_readiness_gate wheel installability

**Date:** 2026-05-14  
**Agent:** R5-B  
**Verdict:** PASS

## Summary

The `release_readiness_gate` module previously used a path-relative `importlib.util.exec_module`
shim in `src/autodev/release_readiness_gate.py` that loaded `scripts/release_readiness_gate.py`
via `Path(__file__).parent.parent.parent / "scripts" / ...`.  This path does not exist in an
installed wheel, so `python -m autodev.release_readiness_gate` failed with `FileNotFoundError`
when the package was installed from PyPI or a wheel.

## Refactor

| File | Before (LoC) | After (LoC) | Change |
|------|-------------|-------------|--------|
| `src/autodev/release_readiness_gate.py` | 25 | 1375 | Full 36-check implementation moved here |
| `scripts/release_readiness_gate.py` | 1334 | 10 | Replaced with thin `from autodev.release_readiness_gate import main` wrapper |

The canonical implementation now ships inside the wheel.  Both invocation paths work from any
install method (editable, wheel, PyPI):

```
python -m autodev.release_readiness_gate [args]       # works everywhere
python scripts/release_readiness_gate.py [args]       # works in source tree with pip install -e .
```

## Test Results

- **Unit tests** (`tests/unit/test_release_readiness_gate.py`): 37/37 pass  
  (import updated from dynamic `exec_module` load → direct `import autodev.release_readiness_gate as gate`)
- **New integration test** (`tests/integration/test_release_readiness_gate_installed_wheel.py`): 3/3 pass  
  (builds fresh wheel → installs into temp venv → runs `python -m autodev.release_readiness_gate` → asserts exit 0, valid JSON, 36 checks)
- **Full suite**: 1303 passed / 8 pre-existing unrelated failures (homebrew formula metadata) / 0 new failures introduced

## Gate Verification

Both invocation forms produce identical 36-check output (same check names, same statuses):

```
python -m autodev.release_readiness_gate --output /tmp/r5_gate_module.json
python scripts/release_readiness_gate.py --output /tmp/r5_gate_script.json
# diff: only ran_at timestamp and duration_ms differ
```

All flags preserved: `--strict`, `--strict-r2`, `--strict-r3`, `--strict-rc`, `--include-r2`, `--include-r3`, `--output`.
