"""Policy tests for .github/workflows/release.yml — HIGH-CI-01.

Verifies that the release workflow:
1. exists as a valid YAML file
2. contains a step that runs pytest
3. has publish gated behind test via `needs: test`
4. contains no `if: false` or other bypass shortcuts
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).parents[2] / ".github" / "workflows" / "release.yml"


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


def _all_step_ifs(workflow: dict) -> list[str]:
    """Return every `if:` expression from every job step."""
    ifs: list[str] = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            if "if" in step:
                ifs.append(str(step["if"]))
    return ifs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_workflow_file_exists():
    """The release workflow file must be present."""
    assert WORKFLOW_PATH.exists(), f"Missing: {WORKFLOW_PATH}"


def test_workflow_yaml_loads_cleanly():
    """The workflow must parse as valid YAML without errors."""
    data = _load_workflow()
    assert isinstance(data, dict), "YAML root must be a mapping"
    assert "jobs" in data, "Workflow must define at least one job"


def test_workflow_contains_pytest_step():
    """At least one step must invoke pytest."""
    workflow = _load_workflow()
    runs = _all_step_runs(workflow)
    pytest_runs = [r for r in runs if "pytest" in r]
    assert pytest_runs, (
        "No step found that runs pytest. "
        f"Steps found: {runs}"
    )


def test_publish_job_needs_test():
    """The publish job must declare `needs: test` so it only runs after tests pass."""
    workflow = _load_workflow()
    jobs = workflow.get("jobs", {})
    assert "publish" in jobs, "Workflow must have a 'publish' job"
    publish_needs = jobs["publish"].get("needs", [])
    # needs can be a string or a list
    if isinstance(publish_needs, str):
        publish_needs = [publish_needs]
    assert "test" in publish_needs, (
        f"publish job must declare `needs: test`, got `needs: {publish_needs}`"
    )


def test_no_bypass_shortcuts_in_step_conditions():
    """No step may use `if: false` or `if: 'false'` bypass shortcuts."""
    workflow = _load_workflow()
    ifs = _all_step_ifs(workflow)
    for condition in ifs:
        # Reject bare `false` bypass
        assert condition.strip().lower() not in ("false", "'false'", '"false"'), (
            f"Step has a bypass `if: {condition!r}` which would silently skip it"
        )
        # Also reject the literal string "if: false" embedded inside
        assert not re.fullmatch(r"false", condition.strip(), re.IGNORECASE), (
            f"Bypass condition detected: {condition!r}"
        )


def test_pypi_upload_gated_on_secret():
    """PyPI upload must only run when PYPI_API_TOKEN secret is set."""
    workflow = _load_workflow()
    jobs = workflow.get("jobs", {})
    publish_steps = jobs.get("publish", {}).get("steps", [])
    twine_upload_steps = [
        s for s in publish_steps if "run" in s and "twine upload" in s.get("run", "")
    ]
    assert twine_upload_steps, "publish job must have a twine upload step"
    for step in twine_upload_steps:
        condition = str(step.get("if", ""))
        assert "PYPI_API_TOKEN" in condition, (
            f"twine upload step must be conditioned on PYPI_API_TOKEN secret, "
            f"got `if: {condition!r}`"
        )


def test_test_job_has_ruff_and_mypy_steps():
    """The test job must include ruff and mypy steps."""
    workflow = _load_workflow()
    jobs = workflow.get("jobs", {})
    assert "test" in jobs, "Workflow must have a 'test' job"
    test_runs = [
        s.get("run", "") for s in jobs["test"].get("steps", []) if "run" in s
    ]
    ruff_steps = [r for r in test_runs if "ruff" in r]
    mypy_steps = [r for r in test_runs if "mypy" in r]
    assert ruff_steps, f"test job must run ruff; steps: {test_runs}"
    assert mypy_steps, f"test job must run mypy; steps: {test_runs}"
