"""Integration tests for the CLI review and multi-patch-fix-bug commands (W7)."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from autodev.cli import app

runner = CliRunner()


def _make_run_dir(tmp_path: Path, run_id: str = "test-run-001") -> Path:
    run_dir = tmp_path / ".dev-factory" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def test_review_approve_writes_file(tmp_path):
    """CLI 'review --decision approve' must write an 'approved' sentinel file."""
    run_id = "run-approve-001"
    run_dir = _make_run_dir(tmp_path, run_id)

    result = runner.invoke(app, [
        "review",
        "--run-id", run_id,
        "--decision", "approve",
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code == 0, f"Unexpected exit: {result.stdout}"
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["decision"] == "approved"

    approved_file = run_dir / "approved"
    assert approved_file.exists(), "'approved' sentinel file must be created"


def test_review_reject_writes_file(tmp_path):
    """CLI 'review --decision reject' must write a 'rejected' sentinel file."""
    run_id = "run-reject-001"
    run_dir = _make_run_dir(tmp_path, run_id)

    result = runner.invoke(app, [
        "review",
        "--run-id", run_id,
        "--decision", "reject",
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code == 0, f"Unexpected exit: {result.stdout}"
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["decision"] == "rejected"

    rejected_file = run_dir / "rejected"
    assert rejected_file.exists(), "'rejected' sentinel file must be created"


def test_review_invalid_decision_exits_nonzero(tmp_path):
    """CLI 'review --decision badvalue' must exit with a non-zero code."""
    run_id = "run-bad-001"
    _make_run_dir(tmp_path, run_id)

    result = runner.invoke(app, [
        "review",
        "--run-id", run_id,
        "--decision", "maybe",
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code != 0


def test_review_missing_run_dir_exits_nonzero(tmp_path):
    """CLI 'review' with a non-existent run_id must exit non-zero."""
    result = runner.invoke(app, [
        "review",
        "--run-id", "does-not-exist",
        "--decision", "approve",
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code != 0
