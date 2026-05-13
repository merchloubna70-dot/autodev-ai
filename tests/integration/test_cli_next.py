"""Integration tests for 'autodev next' CLI command (BMAD-3)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from autodev.cli import app
from autodev.schemas import (
    PipelineRunState,
    ReleaseCheckReport,
    ReleaseDecision,
)

runner = CliRunner()


def _write_run_state(tmp_path: Path, run_id: str, state: PipelineRunState) -> Path:
    """Write a run_state.json and required subdirs for RunState.load."""
    run_dir = tmp_path / ".dev-factory" / "runs" / run_id
    for sub in ("input", "product", "architecture", "planning", "execution",
                "quality", "verification", "delivery"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    state_file = run_dir / "run_state.json"
    state_file.write_text(json.dumps(state.model_dump(mode="json")), encoding="utf-8")
    return run_dir


def test_next_cmd_no_release_check_outputs_release_check(tmp_path):
    """CLI 'next' on a fresh run should suggest running release-check."""
    run_id = "next-test-fresh-001"
    state = PipelineRunState(run_id=run_id, repo_path=str(tmp_path))
    _write_run_state(tmp_path, run_id, state)

    result = runner.invoke(app, [
        "next",
        "--run-id", run_id,
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.stdout}"
    assert "NEXT:" in result.stdout
    assert "release-check" in result.stdout
    assert "WHY:" in result.stdout
    assert "CONFIDENCE:" in result.stdout


def test_next_cmd_release_ready_outputs_export_delivery(tmp_path):
    """CLI 'next' when release is ready should suggest export-delivery."""
    run_id = "next-test-ready-001"
    state = PipelineRunState(
        run_id=run_id,
        repo_path=str(tmp_path),
        release_check=ReleaseCheckReport(
            decision=ReleaseDecision.RELEASE_READY,
            all_milestones_complete=True,
            all_acceptance_evidence_present=True,
            dry_run=False,
            mock_execution_used=False,
        ),
    )
    _write_run_state(tmp_path, run_id, state)

    result = runner.invoke(app, [
        "next",
        "--run-id", run_id,
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.stdout}"
    assert "export-delivery" in result.stdout
    assert run_id in result.stdout
    assert "CONFIDENCE:" in result.stdout
    # Should include evidence paths section
    assert "EVIDENCE:" in result.stdout
