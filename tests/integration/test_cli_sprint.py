"""Integration tests for the BMAD-7 Sprint CLI subcommands."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from autodev.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Test 1 — sprint-start creates sprint directory and returns sprint_id
# ---------------------------------------------------------------------------


def test_sprint_start_creates_sprint(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["sprint-start", "--repo-path", str(tmp_path), "--goal", "Ship login flow"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "sprint_id=sprint-001" in result.output
    sprint_dir = tmp_path / ".autodev" / "sprints" / "sprint-001"
    assert sprint_dir.is_dir()
    assert (sprint_dir / "state.json").exists()


# ---------------------------------------------------------------------------
# Test 2 — sprint-status returns health for existing sprint
# ---------------------------------------------------------------------------


def test_sprint_status_after_start(tmp_path: Path) -> None:
    # First start a sprint
    runner.invoke(
        app,
        ["sprint-start", "--repo-path", str(tmp_path), "--goal", "MVP"],
        catch_exceptions=False,
    )

    result = runner.invoke(
        app,
        ["sprint-status", "--repo-path", str(tmp_path), "--sprint-id", "sprint-001"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "sprint_id=sprint-001" in result.output
    assert "health=" in result.output
    assert "tasks_total=" in result.output


# ---------------------------------------------------------------------------
# Test 3 — sprint-retro runs retrospective and saves report
# ---------------------------------------------------------------------------


def test_sprint_retro_after_start(tmp_path: Path) -> None:
    # Start sprint
    runner.invoke(
        app,
        ["sprint-start", "--repo-path", str(tmp_path), "--goal", "MVP"],
        catch_exceptions=False,
    )

    # Add a fake implementation result
    sprint_dir = tmp_path / ".autodev" / "sprints" / "sprint-001"
    impl_dir = sprint_dir / "implementation"
    impl_dir.mkdir(parents=True, exist_ok=True)
    (impl_dir / "t1_result.json").write_text(
        json.dumps({"task_id": "T-1", "success": True}), encoding="utf-8"
    )

    result = runner.invoke(
        app,
        ["sprint-retro", "--repo-path", str(tmp_path), "--sprint-id", "sprint-001"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "sprint_id=sprint-001" in result.output
    assert "actions=" in result.output

    # Retro file should exist
    assert (sprint_dir / "retrospective.json").exists()


# ---------------------------------------------------------------------------
# Test 4 — sprint-correct produces a change proposal
# ---------------------------------------------------------------------------


def test_sprint_correct_course(tmp_path: Path) -> None:
    # Start sprint
    runner.invoke(
        app,
        ["sprint-start", "--repo-path", str(tmp_path), "--goal", "MVP"],
        catch_exceptions=False,
    )

    result = runner.invoke(
        app,
        [
            "sprint-correct",
            "--repo-path", str(tmp_path),
            "--sprint-id", "sprint-001",
            "--change", "Switch database from SQLite to PostgreSQL",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "sprint_id=sprint-001" in result.output
    assert "impacts=" in result.output
    assert "actions=" in result.output
