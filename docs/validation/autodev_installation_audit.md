# autodev-ai Installation Audit

**Date:** 2026-05-14  
**Auditor:** Agent B — autodev Release Hardening  
**Package:** autodev-ai 0.1.0  
**Summary verdict:** `installable_with_caveats`

---

## Path Results

| Path | Method | Python | Exit (help) | Exit (--version) | Import time | pip pkgs | Pass |
|------|--------|--------|-------------|------------------|-------------|----------|------|
| 1 editable_local | `.venv` editable in repo | 3.14.4 | 0 | 0 ✓ | — | 58 | YES |
| 2 wheel_clean_venv | `pip install dist/*.whl` | 3.12.13 | 0 | **2 FAIL** | 0.016 s | 20 | NO |
| 3 sdist_clean_venv | `pip install dist/*.tar.gz` | 3.12.13 | 0 | **2 FAIL** | 0.030 s | 20 | NO |
| 4 editable_fresh_dev | `pip install -e .[dev]` (rsync'd src) | 3.12.13 | 0 | 0 ✓ | — | 28 | YES |

---

## Path 1 — Existing editable install

```
source /Users/macworkers/autodev/.venv/bin/activate
autodev --help      # exit 0
autodev --version   # exit 0  →  "autodev-ai 0.1.0"
```

Duration: 0.24 s. 58 packages in venv (includes dev + extras).  
Console script: `/Users/macworkers/autodev/.venv/bin/autodev`  
**PASS.**

---

## Path 2 — Fresh venv + wheel

```
python3.12 -m venv /tmp/autodev-install-audit-2/venv
pip install /Users/macworkers/autodev/dist/autodev_ai-0.1.0-py3-none-any.whl
```

pip install: exit 0, duration 5.9 s. 20 packages.  
`autodev --help`: exit 0 (all 38 commands present).  
`autodev --version`: **exit 2 — "No such option: --version".**  
`python -c "import autodev"`: exit 0, 0.016 s.  
Import warnings: none.

**Root cause:** installed `cli.py` is 1019 lines. Source `cli.py` is 1042 lines.  
The wheel is missing `_version_callback` and the `@app.callback()` block (23 lines added after the dist was built).  
**FAIL — stale dist artifact.**

---

## Path 3 — Fresh venv + sdist

```
python3.12 -m venv /tmp/autodev-install-audit-3/venv
pip install /Users/macworkers/autodev/dist/autodev_ai-0.1.0.tar.gz
```

pip install: exit 0, duration 7.8 s (includes build). 20 packages.  
`autodev --help`: exit 0.  
`autodev --version`: **exit 2 — "No such option: --version".**  
`python -c "import autodev"`: exit 0, 0.030 s.

Installed `cli.py` is identical to wheel (1019 lines). Both dist artifacts predate the `--version` commit.  
**FAIL — same stale dist artifact.**

---

## Path 4 — Fresh venv + pip install -e .[dev]

```
rsync -a --exclude='.venv' /Users/macworkers/autodev/ /tmp/autodev-install-audit-4/repo/
python3.12 -m venv /tmp/autodev-install-audit-4/venv
pip install -e '/tmp/autodev-install-audit-4/repo/[dev]'
```

pip install: exit 0, duration 11.8 s. 28 packages (runtime + dev extras).  
`autodev --version`: exit 0 → "autodev-ai 0.1.0".  
`autodev --help`: exit 0.

### pytest subset

```
pytest tests/unit/test_prfaq_style.py tests/unit/test_report_banner.py -q
```

Result: **13 passed, 0 failed, exit 0**, duration 1.2 s.  
**PASS.**

---

## Path 5 — Module-form invocation (`python -m autodev.cli`)

Tested in all three venvs:

| Venv | Exit code | Output |
|------|-----------|--------|
| editable (path 1) | 0 | `Usage: python -m autodev.cli [OPTIONS] COMMAND [ARGS]...` |
| wheel (path 2) | 0 | same |
| sdist (path 3) | 0 | same |

`module_form_works = true`  
**PASS in all venvs.**

---

## Environment Note — Python 3.14.4 (system python3)

`python3 -m venv` with the system Homebrew `python3` (3.14.4) **fails**:

```
Error: Command '...python3.14 -m ensurepip --upgrade --default-pip' returned non-zero exit status 1.
```

This is a Homebrew packaging bug with Python 3.14.4 + pip 26.0.1.  
All fresh-venv audit paths used `python3.12` as the fallback.  
**Action:** document `python3.12` or `python3.13` as recommended interpreter in README until this resolves.

---

## Dependency Pull

Both wheel and sdist pull 19 transitive packages:

```
MarkupSafe  annotated-doc  annotated-types  click  jinja2
markdown-it-py  mdurl  pydantic  pydantic-core  pygments
pyyaml  rich  shellingham  typer  typing-extensions  typing-inspection
```

No missing runtime dependencies. No import warnings on any path.

---

## Findings

| Severity | Finding |
|----------|---------|
| **HIGH** | `dist/` artifacts (wheel + sdist) are **stale** — built before `_version_callback` + `@app.callback()` were added to `src/autodev/cli.py`. `autodev --version` returns exit 2 from any non-editable install. **Fix:** rebuild with `python -m build` or `hatch build` from current HEAD. |
| **MEDIUM** | Python 3.14.4 (Homebrew) `ensurepip` is broken — `python3 -m venv` fails. End-users on macOS may hit this if their system `python3` is 3.14. **Fix:** add a note to README recommending python 3.12/3.13. |
| **LOW** | pip 26.1.1 is available (26.0 installed); update notice shows on all fresh installs but does not block anything. |
| **INFO** | Module-form invocation (`python -m autodev.cli`) works in all install variants. Console script entry point registers correctly. 13/13 unit tests pass under fresh editable dev install. |

---

## Verdict

**`installable_with_caveats`**

- Editable installs from source: fully functional.
- Wheel + sdist in `dist/`: install successfully and all commands work, but `--version` is broken (stale build). Rebuild before release.
- No missing runtime dependencies.
- Python 3.14 venv creation broken on this machine (Homebrew issue, not a package bug).
