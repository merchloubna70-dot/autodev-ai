# PyPI RC Artifact Build — autodev-ai 0.1.0a1

**Verdict: `publishable`** — both artifacts pass `twine check`, install cleanly in a fresh Python 3.12 venv, and report the correct version.

## Build

```bash
rm -rf dist build *.egg-info
python -m build
```

Result: success via isolated `hatchling>=1.21` build backend.

## Artifacts (immutable hashes — FINAL after RC-A metadata fixes)

| File | SHA-256 |
|---|---|
| `autodev_ai-0.1.0a1-py3-none-any.whl` | `395e2102e6eb80269de215bb716c1751d5169dcbb4b2ce42be22fca5a55e5b94` |
| `autodev_ai-0.1.0a1.tar.gz` | `0a84c81e38ee9dfa95112e487932af52e599ea27d6943e0aa33b390dfc2fd410` |

> Earlier preflight build hashes (`5f5b51…` wheel / `243c9f…` sdist) are superseded by these final hashes after RC-A's metadata fixes (14 trove classifiers + 5 `[project.urls]` entries + README pip URL `0.1.0` → `0.1.0a1`).

The wheel is platform-agnostic (`py3-none-any`) — pure Python, no native extensions.

## twine check

```
Checking dist/autodev_ai-0.1.0a1-py3-none-any.whl: PASSED
Checking dist/autodev_ai-0.1.0a1.tar.gz:           PASSED
```

Both artifacts render correctly for PyPI's long_description display.

## Fresh-venv smoke

```bash
python3.12 -m venv /tmp/pypi-rc-smoke
/tmp/pypi-rc-smoke/bin/pip install dist/autodev_ai-0.1.0a1-py3-none-any.whl
/tmp/pypi-rc-smoke/bin/autodev --version            # → autodev-ai 0.1.0a1
/tmp/pypi-rc-smoke/bin/autodev --help               # → Usage: autodev ...
/tmp/pypi-rc-smoke/bin/python -m autodev.cli --version   # → autodev-ai 0.1.0a1
```

All four invocations return exit 0 with the expected `autodev-ai 0.1.0a1` version string.

## Reproducibility caveats (honest)

- Wheel **filename** is deterministic (`py3-none-any`), but byte-level reproducibility depends on hatchling + Python minor version at build time.
- sdist tarball includes a timestamp in `PKG-INFO`; not bit-reproducible across rebuilds at different times.
- The recorded SHA-256 here is authoritative for *this exact build*. After tag push, the workflow rebuilds and the published hash will differ from this preflight hash — that's expected. Use these hashes as the local reference; the CI-published hashes will be recorded in the GitHub Release notes after upload.

## Publish blocks

- **Operational**: `PYPI_API_TOKEN` GitHub secret must be set before tag push triggers PyPI upload. No technical blocker remains.
