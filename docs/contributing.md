# Contributing to autodev-x

## Dev Setup

```bash
# Clone and install in editable mode with dev extras
git clone https://github.com/<org>/autodev-x.git
cd autodev-x
pip install -e ".[dev]"

# Install pre-commit hooks
pip install pre-commit
pre-commit install
# For push-time hooks (pytest collected count):
pre-commit install --hook-type pre-push
```

## Running Tests

```bash
pytest -q
# With coverage:
pytest --cov=autodev --cov-report=term-missing
```

## Code Style

- Formatter/linter: **ruff** (`ruff check src/ tests/`)
- Line length: 110
- Target: Python 3.10+

Pre-commit runs `ruff --fix` automatically on staged files.

## CI Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `test.yml` | push / PR | pytest on Python 3.10/3.11/3.12, uploads coverage artifact |
| `lint.yml` | push / PR | ruff check + mypy |
| `release.yml` | `v*.*.*` tag | builds wheel/sdist, attaches to GitHub Release, optionally pushes to PyPI |

## Releasing

1. Bump `version` in `pyproject.toml`.
2. `git tag v0.2.0 && git push origin v0.2.0`
3. The `release.yml` workflow builds and attaches artifacts automatically.
4. To publish to PyPI, set the `PYPI_API_TOKEN` repository secret.

## Dependabot

Weekly automated PRs for pip and GitHub Actions dependency updates are configured in `.github/dependabot.yml`.
