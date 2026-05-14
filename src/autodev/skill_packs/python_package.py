"""Skill pack: pure Python library with pyproject, pytest, MIT."""
from __future__ import annotations

from .base import SkillPack


class PythonPackagePack(SkillPack):
    """Curated template for a pure Python library project."""

    @property
    def name(self) -> str:
        return "python-package"

    @property
    def description(self) -> str:
        return "Pure Python library with pyproject.toml, pytest, MIT license"

    @property
    def brief_template(self) -> str:
        return """\
# Project Brief: {{project_name}}

## Summary
{{project_name}} is a pure Python library that {{summary}}.

## Goals
- Provide a clean, well-documented public API
- Zero mandatory runtime dependencies (optional deps via extras)
- Publish to PyPI under the MIT license

## Key Features
- {{feature_1}}
- {{feature_2}}

## Stack
- Language: Python ≥ 3.10 (type-annotated throughout)
- Build backend: hatchling (pyproject.toml)
- Testing: pytest + pytest-cov
- Linting / type-checking: ruff + mypy
- CI: GitHub Actions (test matrix on py3.10 / py3.11 / py3.12)
- License: MIT
"""

    @property
    def prd_template(self) -> str:
        return """\
# PRD: {{project_name}}

## 1. Overview
<!-- Library purpose, primary use cases, and target audience (developers). -->

## 2. Problem Statement
<!-- The gap in the Python ecosystem this library fills. -->

## 3. Functional Requirements
### 3.1 Public API
<!-- Main classes, functions, and their signatures. -->

### 3.2 Optional Extensions
<!-- Extra dependencies exposed via `[extras]` in pyproject.toml. -->

### 3.3 CLI (if any)
<!-- Console scripts defined in `[project.scripts]`. -->

## 4. Non-Functional Requirements
- Py version compatibility floor
- Zero mandatory runtime deps (state any exceptions)
- Thread-safety guarantees
- Import-time budget (e.g. < 100 ms)

## 5. Architecture
- `src/{{project_name}}/__init__.py`: public API surface
- `src/{{project_name}}/_internal/`: private implementation modules
- `tests/`: pytest suite (unit + integration)
- `docs/`: Sphinx or MkDocs documentation

## 6. Milestones
<!-- See milestones_template in PythonPackagePack. -->

## 7. Acceptance Criteria
- `pytest --cov` shows ≥ 90 % coverage
- `mypy --strict` passes on the package
- `ruff check .` clean
- `pip install .` works from source and from PyPI wheel
- MIT LICENSE file present
"""

    @property
    def milestones_template(self) -> list[str]:
        return [
            "scaffold",
            "core-impl",
            "tests",
            "docs",
            "ci",
            "release",
        ]

    @property
    def recommended_executor(self) -> str:
        return "auto"

    @property
    def recommended_extras(self) -> list[str]:
        return []
