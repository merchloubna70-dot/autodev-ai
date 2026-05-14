"""Tests for --resume-from flag and resume_from_milestone() helper."""
from __future__ import annotations

from pathlib import Path  # noqa: F401  — used in _make_run_dir signature
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from autodev.cli import app
from autodev.flows.replay_flow import (
    _MILESTONE_TO_STAGE,
    MILESTONE_TAGS,
    _clear_artifacts_after,
    resume_from_milestone,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_dir(base: Path, run_id: str, milestones: list[str]) -> Path:
    """Create a minimal fake run directory tree for testing."""
    run_root = base / ".dev-factory" / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    # Write a minimal run_state.json so RunState.load() can deserialise it.
    import json

    state = {
        "run_id": run_id,
        "repo_path": str(base),
        "errors": [],
        "implementation_results": [],
        "languages": ["python"],
        "mode": "dry-run",
        "mock_execution_used": True,
    }
    (run_root / "run_state.json").write_text(json.dumps(state), encoding="utf-8")

    # Create the requested milestone artifact dirs.
    for tag in milestones:
        (run_root / tag).mkdir(parents=True, exist_ok=True)

    return run_root


# ---------------------------------------------------------------------------
# Test: invalid stage is rejected
# ---------------------------------------------------------------------------


def test_resume_from_invalid_stage_raises(tmp_path):
    """resume_from_milestone raises ValueError for an unknown milestone tag."""
    _make_run_dir(tmp_path, "run-001", milestones=["input", "product"])

    with pytest.raises(ValueError, match="Unknown milestone tag"):
        resume_from_milestone(
            run_id="run-001",
            repo_path=str(tmp_path),
            milestone="bogus-stage",
        )


def test_resume_from_missing_artifact_dir_raises(tmp_path):
    """resume_from_milestone raises ValueError when artifact dir is absent."""
    # Only create 'input' — 'product' does not exist on disk.
    _make_run_dir(tmp_path, "run-002", milestones=["input"])

    with pytest.raises(ValueError, match="Milestone artifact directory not found"):
        resume_from_milestone(
            run_id="run-002",
            repo_path=str(tmp_path),
            milestone="product",
        )


# ---------------------------------------------------------------------------
# Test: valid stage clears later artifacts
# ---------------------------------------------------------------------------


def test_clear_artifacts_after_removes_downstream_dirs(tmp_path):
    """_clear_artifacts_after removes directories after the given milestone."""
    run_root = tmp_path / ".dev-factory" / "runs" / "run-003"
    run_root.mkdir(parents=True, exist_ok=True)

    # Create all milestone dirs.
    for tag in MILESTONE_TAGS:
        (run_root / tag).mkdir()

    # Ask to clear everything after "planning" (index 3).
    removed = _clear_artifacts_after(run_root, "planning")

    # Dirs before/at "planning" must still exist.
    for tag in ["input", "product", "architecture", "planning"]:
        assert (run_root / tag).exists(), f"Expected {tag} to still exist"

    # Dirs after "planning" must be removed.
    for tag in ["execution", "quality", "verification", "delivery"]:
        assert not (run_root / tag).exists(), f"Expected {tag} to be removed"

    # Removed list should contain the 4 downstream paths.
    assert len(removed) == 4


def test_resume_from_valid_stage_clears_later_and_replays(tmp_path):
    """resume_from_milestone clears downstream dirs then invokes ReplayFlow."""
    all_tags = MILESTONE_TAGS
    run_root = _make_run_dir(tmp_path, "run-004", milestones=all_tags)

    # Stub the ReplayFlow so we don't execute the full pipeline.
    fake_run_state = MagicMock()
    fake_run_state.run_id = "run-004"
    fake_run_state.state.errors = []

    with patch("autodev.flows.replay_flow.ReplayFlow") as MockReplayFlow:
        MockReplayFlow.return_value.replay.return_value = fake_run_state

        result = resume_from_milestone(
            run_id="run-004",
            repo_path=str(tmp_path),
            milestone="planning",
        )

    # Verify replay was called with the correct stage mapping.
    MockReplayFlow.return_value.replay.assert_called_once_with(
        run_id="run-004",
        repo_path=str(tmp_path),
        from_stage="planning",
    )
    assert result is fake_run_state

    # Downstream artifact dirs should have been removed before replay.
    for tag in ["execution", "quality", "verification", "delivery"]:
        assert not (run_root / tag).exists(), f"Expected {tag} to be cleared"


# ---------------------------------------------------------------------------
# Test: no --resume-from flag = unchanged behavior
# ---------------------------------------------------------------------------


runner = CliRunner()


def test_deliver_project_no_resume_from_flag_unchanged(tmp_path, monkeypatch):
    """deliver-project without --resume-from follows the normal delivery path."""
    # Stub ProjectDeliveryFlow so the test is fast.
    fake_run = MagicMock()
    fake_run.run_id = "normal-run"
    fake_run.state.mock_execution_used = True
    fake_run.state.release_check = None

    with patch("autodev.cli.ProjectDeliveryFlow") as MockFlow:
        MockFlow.return_value.run.return_value = fake_run
        result = runner.invoke(
            app,
            [
                "deliver-project",
                "--repo-path", str(tmp_path),
                "--mode", "dry-run",
                "--allow-mock-executor", "true",
            ],
        )

    assert result.exit_code == 0, result.output
    # Ensure the normal delivery path was taken (no resume).
    MockFlow.return_value.run.assert_called_once()


def test_deliver_project_resume_from_no_run_id_exits_1(tmp_path):
    """deliver-project --resume-from without --run-id exits 1."""
    result = runner.invoke(
        app,
        [
            "deliver-project",
            "--repo-path", str(tmp_path),
            "--resume-from", "planning",
        ],
    )
    assert result.exit_code == 1


def test_deliver_project_resume_from_invalid_tag_exits_1(tmp_path):
    """deliver-project --resume-from with invalid tag exits 1."""
    result = runner.invoke(
        app,
        [
            "deliver-project",
            "--repo-path", str(tmp_path),
            "--resume-from", "bogus",
            "--run-id", "run-xyz",
        ],
    )
    assert result.exit_code == 1


def test_milestone_to_stage_mapping_complete():
    """Every MILESTONE_TAG maps to a known STAGE."""
    from autodev.flows.replay_flow import STAGES

    for tag in MILESTONE_TAGS:
        assert tag in _MILESTONE_TO_STAGE, f"Missing mapping for tag: {tag}"
        assert _MILESTONE_TO_STAGE[tag] in STAGES, (
            f"Tag {tag!r} maps to unknown stage {_MILESTONE_TO_STAGE[tag]!r}"
        )
