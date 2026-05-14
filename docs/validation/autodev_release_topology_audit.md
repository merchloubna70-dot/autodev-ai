# autodev-ai Release Topology Audit

**Audit date:** 2026-05-14  
**Agent:** Release Hardening Agent A (read-only, topology inspection)

---

## Summary

`autodev-ai` is a Python package (MIT license) providing an AI-driven software factory CLI built on CrewAI, Codex CLI, and Claude Code CLI. The source tree is well-structured with 170 source files across 20 subpackages (23,017 LoC), 85 unit tests, and 27 integration tests. Four CI workflows, four packaging channels (Docker/PyInstaller/Homebrew/macOS .app), and a console entry point are all present and wired correctly. However, **three issues require resolution before a clean public release**: a git tag / pyproject.toml version mismatch, a missing root LICENSE file, and a stale Homebrew formula URL.

---

## 1. pyproject.toml

| Field | Value |
|---|---|
| `[project].name` | `autodev-ai` |
| `[project].version` | `0.1.0` |
| `[project].python_requires` | `>=3.10` |
| `[project].license` | `{ text = "MIT" }` (inline, no file) |
| `[build-system].build-backend` | `hatchling.build` |
| `[build-system].requires` | `hatchling>=1.21` |
| `[tool.ruff].target-version` | `py310` |
| `[tool.ruff].line-length` | `110` |
| `[tool.mypy].python_version` | `3.10` |
| `[tool.mypy].strict` | `false` |

### Runtime dependencies

| Package | Constraint |
|---|---|
| pydantic | `>=2.5,<3.0` |
| typer[all] | `>=0.9` |
| rich | `>=13.7` |
| PyYAML | `>=6.0` |
| jinja2 | `>=3.1` |

### Optional / dev dependencies

| Group | Packages |
|---|---|
| `crewai` | `crewai>=0.30` |
| `tui` | `textual>=0.60` |
| `dev` | pytest>=8.0, pytest-asyncio>=0.23, pytest-cov>=4.1, ruff>=0.4 |

### Console scripts

| Script | Target |
|---|---|
| `autodev` | `autodev.cli:app` (**verified present at cli.py line 26**) |

---

## 2. Top-level directory tree

| Entry | Type | Note |
|---|---|---|
| `_autodev/` | dir | Runtime run artifacts (project-context.json/md) |
| `dist/` | dir | Built wheel + sdist (v0.1.0) |
| `docs/` | dir | 25 Markdown files |
| `examples/` | dir | 10 briefs + README + run script |
| `packaging/` | dir | docker / pyinstaller / homebrew / desktop |
| `scripts/` | dir | **Empty** |
| `src/` | dir | Source root |
| `tests/` | dir | Unit + integration + fixtures |
| `pyproject.toml` | file | Single build manifest |
| `README.md` | file | Present |
| `LICENSE` | **missing** | No LICENSE file at root |
| `CHANGELOG` | **missing** | No CHANGELOG at root |

---

## 3. src/autodev/ package tree

| Subpackage | LoC | .py Files |
|---|---|---|
| `agents/` | 7,465 | 44 |
| `flows/` | 3,080 | 19 |
| `adapters/` | 2,453 | 20 |
| `executors/` | 1,903 | 14 |
| `schemas.py` | 1,587 | 1 |
| `cli.py` | 1,042 | 1 |
| `planners/` | 1,120 | 8 |
| `utils/` | 661 | 10 |
| `tui/` | 634 | 4 |
| `gates/` | 911 | 9 |
| `mcp_server/` | 580 | 3 |
| `scanners/` | 469 | 7 |
| `reports/` | 399 | 5 |
| `context_providers/` | 262 | 6 |
| `tasks/` | 214 | 16 |
| `state.py` | 134 | 1 |
| `config.py` | 98 | 1 |
| `__init__.py` | 5 | 1 |
| `data/` | 0 | 0 |
| `templates/` | 0 | 0 |
| **TOTAL** | **23,017** | **170** |

---

## 4. tests/ layout

| Category | .py Files | LoC |
|---|---|---|
| `tests/unit/` | 85 | 11,004 |
| `tests/integration/` | 27 | 2,992 |
| **Total test** | **112** | **13,996** |

### Fixture directories (10)

`empty_project`, `issue_project`, `mixed_project`, `mock_patches`, `monorepo_project`, `openapi`, `prd_project`, `python_project`, `rust_project`, `typescript_project`

---

## 5. docs/ tree

25 Markdown files total, organized as:

- Top-level reference docs: architecture, usage, faq, quickstart, contributing, state_schema, quality_gate, release_gate, issue_pipeline, project_delivery, multi_cli_executor, mcp_server, a2a, a2a_server, a2a_http_client, crewai_flows, claude_code_adapter, codex_cli_adapter (18 files)
- `tutorials/`: 01-bug-fix through 07-a2a-server (7 files)

---

## 6. examples/ tree

| Dir | Contents |
|---|---|
| `01-mdlines/` through `10-prfaq-product/` | One `brief.md` each (10 briefs) |
| `README.md` | Overview |
| `scripts/run_example.sh` | Runner script |

---

## 7. packaging/ tree

| Channel | Files | Status |
|---|---|---|
| `docker/` | Dockerfile, build.sh, .dockerignore, README | Present |
| `pyinstaller/` | autodev.spec, autodev_entry.py, build.sh, build-universal-mac.sh, _collect_hidden_imports.py | Present (build/ artifacts also committed) |
| `homebrew/Formula/autodev-ai.rb` | Formula, README, refresh-resources.sh | Present but URL points to non-existent v0.1.0 release |
| `desktop/` | autodev-ai.app bundle (Info.plist, launcher, AppIcon.icns), install.sh, autodev-ai-open.sh | Present |

**Note:** The Dockerfile lives at `packaging/docker/Dockerfile` (not at repository root). The `docker-publish.yml` workflow correctly references `file: packaging/docker/Dockerfile`.

---

## 8. .github/workflows/

| Workflow | Triggers | Key details |
|---|---|---|
| `test.yml` | push (all branches), pull_request (all branches) | Matrix: Python 3.10, 3.11, 3.12; runs pytest with coverage |
| `lint.yml` | push (all branches), pull_request (all branches) | ruff check + mypy on Python 3.12 |
| `release.yml` | push tags matching `v*.*.*` | Builds wheel+sdist, attaches to GitHub Release, publishes to PyPI (conditional on `PYPI_API_TOKEN`) |
| `docker-publish.yml` | push tags matching `v*.*.*`, workflow_dispatch | Builds amd64+arm64 image; pushes to GHCR |

---

## 9. Version / Tag Consistency Matrix

| Source | Version string |
|---|---|
| `pyproject.toml` | `0.1.0` |
| `dist/` wheel | `autodev_ai-0.1.0-py3-none-any.whl` |
| `dist/` sdist | `autodev_ai-0.1.0.tar.gz` |
| git tag | `v0.1.0-alpha` |
| Homebrew formula URL | `v0.1.0/autodev_ai-0.1.0.tar.gz` |
| PyInstaller spec comment | `autodev-ai v0.1.0` |

---

## 10. Findings

| # | Kind | Severity | Detail |
|---|---|---|---|
| F-1 | inconsistent | **HIGH** | Git tag is `v0.1.0-alpha` but `pyproject.toml` and all build artifacts say `0.1.0` (no alpha suffix). Both `release.yml` and `docker-publish.yml` trigger on `v*.*.*` — the existing `v0.1.0-alpha` tag matches this glob and would have fired a PyPI upload of `0.1.0` without an alpha pre-release classifier. Either bump pyproject.toml to `0.1.0a1` (PEP 440) and rebuild, or retag as `v0.1.0`. |
| F-2 | missing | **HIGH** | No `LICENSE` file at repository root. `pyproject.toml` uses inline `license = { text = "MIT" }`, which satisfies PEP 639, but GitHub license detection, PyPI badge, and the Homebrew formula's `license "MIT"` clause all expect a physical `LICENSE` file. Add `LICENSE` before the first public release. |
| F-3 | inconsistent | **MEDIUM** | Homebrew formula hardcodes `url "…/releases/download/v0.1.0/autodev_ai-0.1.0.tar.gz"` and a SHA256. The GitHub Release `v0.1.0` does not yet exist (only `v0.1.0-alpha` tag). The formula will produce a 404 for any Homebrew user until a clean `v0.1.0` release is published and the SHA256 is verified. |
| F-4 | missing | **MEDIUM** | No `CHANGELOG.md` or `CHANGES.rst`. The release workflow uses auto-generated notes from commits, but a changelog is expected by PyPI convention and downstream consumers reading the sdist. |
| F-5 | inconsistent | **LOW** | CI lint/Docker workflows fix Python at 3.12 while the test matrix covers 3.10–3.12. `pyproject.toml` declares `requires-python = ">=3.10"`. The mypy and ruff configs also target `py310`. This is internally consistent but the lint job does not verify 3.10 or 3.11 compatibility. |
| F-6 | missing | **LOW** | `src/autodev/data/` and `src/autodev/templates/` exist as directories with zero Python files. If they contain non-Python assets (Jinja2 templates, YAML defaults) those must be declared under `[tool.hatch.build.targets.wheel]` with `artifacts` or `include` to be bundled. Currently only `packages = ["src/autodev"]` is declared, which includes all files under the package directory — verify non-`.py` assets are not being silently omitted. |
| F-7 | missing | **LOW** | `scripts/` directory at repo root is completely empty. Either populate it or remove it to avoid confusion. |
