# autodev-ai 0.1.0a1 — PyPI RC Metadata Freeze

**Round:** pypi_rc_metadata_freeze  
**Date:** 2026-05-14  
**Package:** autodev-ai  
**Version:** 0.1.0a1  

---

## 1. pyproject.toml Snapshot

| Field | Value |
|---|---|
| `name` | `autodev-ai` |
| `version` | `0.1.0a1` |
| `description` | AI-driven software factory: CrewAI + Codex CLI + Claude Code CLI with multi-CLI router, A2A roundtable, MCP server, scale-adaptive delivery from brief to release-ready project. |
| `requires-python` | `>=3.10` |
| `license` | `MIT` |
| `license-files` | `["LICENSE"]` |
| `authors` | `[{name: "Software Factory"}]` |
| `classifiers` | **none defined** (0) |
| `[project.urls]` | **none defined** |
| `build-backend` | `hatchling>=1.21` |
| `hatch.build.targets.wheel.packages` | `["src/autodev"]` |

### Dependencies (5 core)

```
pydantic>=2.5,<3.0
typer[all]>=0.9
rich>=13.7
PyYAML>=6.0
jinja2>=3.1
```

### Optional Dependencies

| Group | Packages |
|---|---|
| `crewai` | `crewai>=0.30` |
| `tui` | `textual>=0.60` |
| `dev` | `pytest>=8.0`, `pytest-asyncio>=0.23`, `pytest-cov>=4.1`, `ruff>=0.4` |

### Console Scripts

```
autodev = autodev.cli:app
```

Verified: `src/autodev/cli.py` line 26 defines `app = typer.Typer(...)`. Entry point is correct.

---

## 2. Version Verification

| Source | Value | Match |
|---|---|---|
| `pyproject.toml [project] version` | `0.1.0a1` | — |
| `src/autodev/__init__.py __version__` (via `importlib.metadata`) | `0.1.0a1` | YES |
| `importlib.metadata.version("autodev-ai")` (installed in .venv) | `0.1.0a1` | YES |

**Version is exactly `0.1.0a1`. No drift detected.**

---

## 3. README.md Inspection

| Check | Result |
|---|---|
| Present | YES |
| Word count | 1 264 |
| First 200 chars | `# autodev-ai\n\n[![License: MIT](...)](LICENSE)\n[![Python ≥3.10](...)` |
| `## Install` section | YES |
| `## 5-minute quickstart` section | YES |
| `## License` section | YES |

### Relative Link Audit

All 14 relative `docs/...` paths referenced in README.md were checked against the filesystem:

| Path | Status |
|---|---|
| `docs/assets/demo.gif` | MISSING (inside HTML comment — not rendered) |
| `docs/quickstart.md` | OK |
| `docs/tutorials/01-bug-fix.md` | OK |
| `docs/tutorials/02-rust-project.md` | OK |
| `docs/tutorials/03-multi-cli-routing.md` | OK |
| `docs/tutorials/04-sprint-mode.md` | OK |
| `docs/tutorials/05-roundtable.md` | OK |
| `docs/tutorials/06-mcp-server.md` | OK |
| `docs/tutorials/07-a2a-server.md` | OK |
| `docs/architecture.md` | OK |
| `docs/configuration.md` | OK |
| `docs/troubleshooting.md` | OK |
| `docs/faq.md` | OK |
| `docs/contributing.md` | OK |
| `CHANGELOG.md` | OK |

`docs/assets/demo.gif` is commented out as a placeholder and will not render as a broken image on PyPI. No functional broken links.

**WARNING (INFO-level):** The `pip install` URL in the Install section references `autodev_ai-0.1.0-py3-none-any.whl` (missing the `a1` suffix). After PyPI publish the correct URL will include `a1`. This will cause a 404 for anyone following the GitHub-release wheel URL verbatim from README. Should be corrected before tagging.

---

## 4. CHANGELOG.md Inspection

| Check | Result |
|---|---|
| Present | YES |
| `## [0.1.0a1]` heading | YES — `## [0.1.0a1] — 2026-05-14 (Pre-Release)` |
| Pre-release marker | YES — `(Pre-Release)` in heading |
| `[0.1.0a1]` footer link | YES — links to GitHub release tag |

---

## 5. LICENSE Inspection

| Check | Result |
|---|---|
| Present | YES |
| Type | MIT |
| Year | 2026 |
| Holder | `autodev-ai contributors` |

---

## 6. Twine Check (PyPI long_description rendering)

```
Checking dist/autodev_ai-0.1.0a1-py3-none-any.whl: PASSED
Checking dist/autodev_ai-0.1.0a1.tar.gz:             PASSED
```

Both artifacts pass twine's rendering validation.

---

## 7. Dist Artifacts

```
dist/autodev_ai-0.1.0a1-py3-none-any.whl
dist/autodev_ai-0.1.0a1.tar.gz
```

### Wheel Top-20 Files

```
autodev/__init__.py
autodev/cli.py
autodev/config.py
autodev/release_readiness_gate.py
autodev/schemas.py
autodev/state.py
autodev/adapters/__init__.py
autodev/adapters/convention_loader.py
autodev/adapters/distillator.py
autodev/adapters/embeddings_index.py
autodev/adapters/filesystem_adapter.py
autodev/adapters/git_adapter.py
autodev/adapters/github_adapter.py
autodev/adapters/mcp_client.py
autodev/adapters/opus_adapter.py
autodev/adapters/pydantic_ai_bridge.py
autodev/adapters/a2a/__init__.py
autodev/adapters/a2a/client.py
autodev/adapters/a2a/handlers.py
autodev/adapters/a2a/roster.py
```

---

## 8. Findings Summary

| # | Severity | Detail |
|---|---|---|
| F-1 | WARNING | **No trove classifiers** in `pyproject.toml`. PyPI page will show no language, dev-status, or license classifier badges. Recommended before publish: `Development Status :: 3 - Alpha`, `Programming Language :: Python :: 3.10`, `License :: OSI Approved :: MIT License`, `Intended Audience :: Developers`. |
| F-2 | WARNING | **No `[project.urls]` section**. PyPI sidebar will show no Homepage, Source, Changelog, or Bug Tracker links. |
| F-3 | INFO | **README Install URL stale**: the `pip install` GitHub wheel URL contains `autodev_ai-0.1.0-py3-none-any.whl` (no `a1` suffix). Must be corrected to `autodev_ai-0.1.0a1-py3-none-any.whl` before the release tag is cut. |
| F-4 | INFO | `docs/assets/demo.gif` is missing but referenced only inside an HTML comment; no impact on PyPI rendering. Should be resolved before stable `0.1.0`. |
| F-5 | INFO | `authors` contains no email address. Valid for PyPI but minimal. |
| F-6 | PASS | Version `0.1.0a1` confirmed in `pyproject.toml`, `importlib.metadata`, and `__version__` — zero drift. |
| F-7 | PASS | Console script `autodev = autodev.cli:app` verified against source. |
| F-8 | PASS | `twine check` PASSED for both wheel and sdist. |
| F-9 | PASS | LICENSE is MIT 2026 autodev-ai contributors. |
| F-10 | PASS | `CHANGELOG.md` contains `## [0.1.0a1]` heading with `(Pre-Release)` marker. |
| F-11 | PASS | All `docs/` relative links in README resolve to existing files. |

---

## 9. Verdict

**`inconsistencies`**

Two WARNINGs prevent a clean `frozen` verdict:

1. **F-1** — Missing trove classifiers (PyPI discoverability gap).  
2. **F-2** — Missing `[project.urls]` (PyPI sidebar empty).  

These are not blockers for the artifact itself (twine check passes) but are
standard expectations for a PyPI publish. Add classifiers and URLs to
`pyproject.toml`, rebuild the wheel, and re-run this validation to reach
`verdict: frozen`.

The `INFO`-level finding F-3 (stale wheel URL in README) **must** also be
corrected before the release tag is cut, or the quickstart instructions will
produce a 404.
