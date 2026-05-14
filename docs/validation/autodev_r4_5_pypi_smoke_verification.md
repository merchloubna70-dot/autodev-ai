# R4.5-A — PyPI Published Package Smoke

**Verdict: `pypi_install_works_with_2_documented_r5_cleanups`**

## Smoke

```bash
$ python3.12 -m venv /tmp/autodev-pypi-final
$ /tmp/autodev-pypi-final/bin/pip install --upgrade pip
$ /tmp/autodev-pypi-final/bin/pip install --pre autodev-ai==0.1.0a2
WARNING: typer 0.25.1 does not provide the extra 'all'

$ /tmp/autodev-pypi-final/bin/autodev --version
autodev-ai 0.1.0a2

$ /tmp/autodev-pypi-final/bin/autodev --help
 Usage: autodev [OPTIONS] COMMAND [ARGS]...  (exit 0)

$ /tmp/autodev-pypi-final/bin/python -m autodev.cli --version
autodev-ai 0.1.0a2

$ /tmp/autodev-pypi-final/bin/python -m autodev.release_readiness_gate
Traceback (most recent call last):
  ...
  File "src/autodev/release_readiness_gate.py", line 20, in _load
    spec.loader.exec_module(mod)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
exit 0  (Python caught the traceback but exit code remained 0)
```

## 2 Honest R5 Cleanups

1. **`typer[all]` deprecation** — typer 0.25.1 dropped the `[all]` extra; pyproject.toml still says `typer[all]>=0.9`. pip emits a non-blocking WARNING. Modern typer bundles `rich + shellingham` automatically. Fix: change to bare `typer>=0.9`.

2. **`autodev.release_readiness_gate` shim broken from PyPI install** — the shim at `src/autodev/release_readiness_gate.py` does `spec.loader.exec_module` on `scripts/release_readiness_gate.py` via a relative path. The `scripts/` directory is NOT shipped in the wheel (only `src/autodev/` is). When users `pip install autodev-ai` and run `python -m autodev.release_readiness_gate`, they get a traceback. The gate works fine from a source tree. Fix options:
   - (a) ship `scripts/` in the wheel (add to hatch's `include`)
   - (b) rewrite the shim to be fully self-contained (duplicate the gate logic into the `src/autodev/` module)
   - (c) drop the shim entirely; document that the gate is a dev tool only

## Production Smoke

End-user `pip install --pre autodev-ai==0.1.0a2 && autodev --help` works as documented. The 2 cleanups are dev/CI conveniences; end users see them as a warning + a broken `python -m` invocation but the primary CLI (`autodev`) is functional.

## Verdict

**`pypi_install_works_with_2_documented_r5_cleanups`** — autodev-ai 0.1.0a2 is installable from PyPI and the primary `autodev` CLI runs correctly. Two minor pyproject/packaging cleanups deferred to R5.
