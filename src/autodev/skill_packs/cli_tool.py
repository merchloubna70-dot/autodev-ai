"""Skill pack: Python CLI tool with typer, rich, hatch packaging."""
from __future__ import annotations

from .base import SkillPack


class CliToolPack(SkillPack):
    """Curated template for a Python CLI tool project."""

    @property
    def name(self) -> str:
        return "cli-tool"

    @property
    def description(self) -> str:
        return "Python CLI with typer, rich, hatch packaging"

    @property
    def brief_template(self) -> str:
        return """\
# Project Brief: {{project_name}}

## Summary
{{project_name}} is a Python CLI tool that {{summary}}.

## Goals
- Provide an ergonomic command-line interface using Typer
- Produce rich terminal output with progress bars and coloured tables
- Publish to PyPI via hatch

## Key Features
- {{feature_1}}
- {{feature_2}}

## Stack
- Language: Python ≥ 3.11
- CLI framework: Typer (rich integration included)
- Output: Rich (tables, progress bars, syntax highlighting)
- Packaging: hatch + pyproject.toml
- Testing: pytest
- CI: GitHub Actions
"""

    @property
    def prd_template(self) -> str:
        return """\
# PRD: {{project_name}}

## 1. Overview
<!-- Who uses this CLI and in what workflow context? -->

## 2. Problem Statement
<!-- The manual/scripting pain point this tool automates. -->

## 3. Functional Requirements
### 3.1 Commands
<!-- List each typer command, its arguments, and options. -->

### 3.2 Output Format
<!-- Default (Rich), --json flag, --quiet mode, etc. -->

### 3.3 Configuration
<!-- Config file location (XDG / ~/.config/{{project_name}}/), env vars. -->

## 4. Non-Functional Requirements
- First-run latency target (cold import budget)
- Compatibility: macOS, Linux, Windows (WSL acceptable)
- Python version floor

## 5. Architecture
- `src/{{project_name}}/cli.py`: Typer app
- `src/{{project_name}}/core.py`: business logic (import-free from typer)
- `src/{{project_name}}/__init__.py`: version export
- `tests/`: pytest suite with `CliRunner` fixtures

## 6. Milestones
<!-- See milestones_template in CliToolPack. -->

## 7. Acceptance Criteria
- `pytest` passes
- `{{project_name}} --help` renders all subcommands
- `pip install .` and `hatch build` both succeed
- Rich output renders without error on 80-column terminal
"""

    @property
    def milestones_template(self) -> list[str]:
        return [
            "scaffold",
            "cli-commands",
            "core-impl",
            "rich-output",
            "tests",
            "ci",
            "release",
        ]

    @property
    def recommended_executor(self) -> str:
        return "auto"

    @property
    def recommended_extras(self) -> list[str]:
        return ["typer", "rich"]
