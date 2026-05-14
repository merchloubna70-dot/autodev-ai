"""Tests for the WARNING banner in Reporter.render_final_report."""
from __future__ import annotations

import tempfile

from autodev.reports.reporter import Reporter
from autodev.schemas import (
    PipelineMode,
    ReleaseCheckReport,
    ReleaseDecision,
)
from autodev.state import RunState


def _make_run(
    mode: PipelineMode,
    mock_used: bool,
    release_decision: ReleaseDecision | None,
    tmpdir: str,
) -> RunState:
    run = RunState(repo_path=tmpdir)
    run.state.mode = mode
    run.state.mock_execution_used = mock_used
    if release_decision is not None:
        run.state.release_check = ReleaseCheckReport(
            decision=release_decision,
            dry_run=(mode == PipelineMode.DRY_RUN),
            mock_execution_used=mock_used,
        )
    return run


# ---------------------------------------------------------------------------
# Banner PRESENT cases
# ---------------------------------------------------------------------------

def test_banner_present_dry_run_and_mock():
    with tempfile.TemporaryDirectory() as tmpdir:
        run = _make_run(
            mode=PipelineMode.DRY_RUN,
            mock_used=True,
            release_decision=ReleaseDecision.NOT_RELEASE_READY,
            tmpdir=tmpdir,
        )
        rendered = Reporter().render_final_report(run)
        assert rendered.startswith("> [!WARNING]"), f"Expected banner at top, got:\n{rendered[:200]}"
        assert "MockExecutionUsed:" in rendered
        assert "DryRun:" in rendered
        assert "ReleaseDecision:" in rendered


def test_banner_present_dry_run_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        run = _make_run(
            mode=PipelineMode.DRY_RUN,
            mock_used=False,
            release_decision=ReleaseDecision.NOT_RELEASE_READY,
            tmpdir=tmpdir,
        )
        rendered = Reporter().render_final_report(run)
        assert rendered.startswith("> [!WARNING]")


def test_banner_present_mock_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        run = _make_run(
            mode=PipelineMode.APPLY,
            mock_used=True,
            release_decision=ReleaseDecision.RELEASE_READY,
            tmpdir=tmpdir,
        )
        rendered = Reporter().render_final_report(run)
        assert rendered.startswith("> [!WARNING]")


def test_banner_present_when_no_release_check():
    """No release_check means not_release_ready -> banner should appear."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run = _make_run(
            mode=PipelineMode.DRY_RUN,
            mock_used=False,
            release_decision=None,
            tmpdir=tmpdir,
        )
        rendered = Reporter().render_final_report(run)
        assert rendered.startswith("> [!WARNING]")


# ---------------------------------------------------------------------------
# Banner ABSENT case
# ---------------------------------------------------------------------------

def test_banner_absent_when_release_ready_no_mock_apply_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        run = _make_run(
            mode=PipelineMode.APPLY,
            mock_used=False,
            release_decision=ReleaseDecision.RELEASE_READY,
            tmpdir=tmpdir,
        )
        rendered = Reporter().render_final_report(run)
        assert not rendered.startswith("> [!WARNING]"), (
            f"Banner should be absent for APPLY+no-mock+RELEASE_READY, got:\n{rendered[:200]}"
        )
        assert "# Final Report" in rendered
