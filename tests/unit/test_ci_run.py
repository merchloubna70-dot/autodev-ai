"""Tests for autodev.ci — CI environment detection and ci-run command."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from autodev.ci import detect_ci, run_ci
from autodev.cli import app

# ---------------------------------------------------------------------------
# Unit tests: detect_ci()
# ---------------------------------------------------------------------------


def test_detect_ci_returns_none_outside_ci(monkeypatch):
    """When no CI env vars are set, detect_ci returns None."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.delenv("DRONE", raising=False)
    assert detect_ci() is None


def test_detect_ci_github_actions(monkeypatch):
    """GITHUB_ACTIONS=true is detected as github-actions."""
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.delenv("DRONE", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    result = detect_ci()
    assert result is not None
    assert result.name == "github-actions"
    assert result.summary_env == "GITHUB_STEP_SUMMARY"


def test_detect_ci_gitlab(monkeypatch):
    """GITLAB_CI=true is detected as gitlab-ci."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("DRONE", raising=False)
    monkeypatch.setenv("GITLAB_CI", "true")
    result = detect_ci()
    assert result is not None
    assert result.name == "gitlab-ci"
    # GitLab does not have a step-summary env var
    assert result.summary_env is None


def test_detect_ci_drone(monkeypatch):
    """DRONE=true is detected as drone."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.setenv("DRONE", "true")
    result = detect_ci()
    assert result is not None
    assert result.name == "drone"
    assert result.summary_env is None


# ---------------------------------------------------------------------------
# Unit tests: run_ci() — not-in-CI exit 1
# ---------------------------------------------------------------------------


def test_run_ci_not_in_ci_returns_exit_1(monkeypatch):
    """run_ci returns 1 when no CI environment is detected."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.delenv("DRONE", raising=False)
    code = run_ci()
    assert code == 1


# ---------------------------------------------------------------------------
# CLI surface tests: ci-run command via Typer test runner
# ---------------------------------------------------------------------------


runner = CliRunner()


def test_cli_ci_run_not_in_ci_exits_1(monkeypatch):
    """autodev-x ci-run exits 1 outside CI."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.delenv("DRONE", raising=False)
    result = runner.invoke(app, ["ci-run"])
    assert result.exit_code == 1


def test_cli_ci_run_github_actions_detected(tmp_path, monkeypatch):
    """ci-run succeeds when GITHUB_ACTIONS=true and deliver-project completes."""
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.delenv("DRONE", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    # Stub out the actual flow so tests are fast and hermetic.
    # ProjectDeliveryFlow is lazily imported inside run_ci(), so we patch it
    # at its canonical module path.
    fake_run = MagicMock()
    fake_run.run_id = "test-run-001"
    fake_run.state.mock_execution_used = True

    with patch("autodev.flows.project_delivery_flow.ProjectDeliveryFlow") as MockFlow:
        MockFlow.return_value.run.return_value = fake_run
        result = runner.invoke(app, ["ci-run", "--repo-path", str(tmp_path)])

    assert result.exit_code == 0, result.output


def test_cli_ci_run_gitlab_detected(tmp_path, monkeypatch):
    """ci-run succeeds when GITLAB_CI=true and deliver-project completes."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("DRONE", raising=False)
    monkeypatch.setenv("GITLAB_CI", "true")

    fake_run = MagicMock()
    fake_run.run_id = "test-run-002"
    fake_run.state.mock_execution_used = True

    with patch("autodev.flows.project_delivery_flow.ProjectDeliveryFlow") as MockFlow:
        MockFlow.return_value.run.return_value = fake_run
        result = runner.invoke(app, ["ci-run", "--repo-path", str(tmp_path)])

    assert result.exit_code == 0, result.output


def test_cli_ci_run_drone_detected(tmp_path, monkeypatch):
    """ci-run succeeds when DRONE=true and deliver-project completes."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.setenv("DRONE", "true")

    fake_run = MagicMock()
    fake_run.run_id = "test-run-003"
    fake_run.state.mock_execution_used = False

    with patch("autodev.flows.project_delivery_flow.ProjectDeliveryFlow") as MockFlow:
        MockFlow.return_value.run.return_value = fake_run
        result = runner.invoke(app, ["ci-run", "--repo-path", str(tmp_path)])

    assert result.exit_code == 0, result.output


def test_cli_ci_run_help(monkeypatch):
    """ci-run --help is available and exits 0."""
    result = runner.invoke(app, ["ci-run", "--help"])
    assert result.exit_code == 0
    assert "ci-run" in result.output or "CI" in result.output
