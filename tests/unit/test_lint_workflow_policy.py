"""Policy tests for .github/workflows/lint.yml — LINT-POLICY-01.

Verifies that the lint workflow:
1. exists as a valid YAML file
2. loads cleanly without errors
3. ruff check step covers `scripts`
4. ruff check step covers both `src` AND `tests`
"""
from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).parents[2] / ".github" / "workflows" / "lint.yml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text())


def _all_step_runs(workflow: dict) -> list[str]:
    """Return every `run:` string from every job step."""
    runs: list[str] = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            if "run" in step:
                runs.append(step["run"])
    return runs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_lint_workflow_file_exists() -> None:
    """lint.yml must exist on disk."""
    assert WORKFLOW_PATH.exists(), f"Lint workflow not found at {WORKFLOW_PATH}"


def test_lint_workflow_yaml_loads_cleanly() -> None:
    """lint.yml must be valid YAML and parse to a dict."""
    content = WORKFLOW_PATH.read_text()
    loaded = yaml.safe_load(content)
    assert isinstance(loaded, dict), "lint.yml must parse to a YAML mapping"
    assert "jobs" in loaded, "lint.yml must contain a 'jobs' key"


def test_lint_workflow_ruff_covers_scripts() -> None:
    """The ruff check step must include `scripts` in its target paths."""
    workflow = _load_workflow()
    runs = _all_step_runs(workflow)
    ruff_runs = [r for r in runs if "ruff check" in r]
    assert ruff_runs, "No 'ruff check' step found in lint.yml"
    assert any("scripts" in r for r in ruff_runs), (
        f"ruff check step does not cover 'scripts'. Found runs: {ruff_runs}"
    )


def test_lint_workflow_ruff_covers_src_and_tests() -> None:
    """The ruff check step must include both `src` and `tests` in its target paths."""
    workflow = _load_workflow()
    runs = _all_step_runs(workflow)
    ruff_runs = [r for r in runs if "ruff check" in r]
    assert ruff_runs, "No 'ruff check' step found in lint.yml"
    assert any("src" in r for r in ruff_runs), (
        f"ruff check step does not cover 'src'. Found runs: {ruff_runs}"
    )
    assert any("tests" in r for r in ruff_runs), (
        f"ruff check step does not cover 'tests'. Found runs: {ruff_runs}"
    )
