"""Unit tests for ReleaseFlow (HIGH-COV-01 / HIGH-ORPHAN-01).

ReleaseFlow.check(run) calls ReleaseManagerAgent.check(run.state) then
Reporter.write_final_report(run).  All tests are deterministic: we mock
at the agent/gate layer so no real CLIs are required.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autodev.flows.release_flow import ReleaseFlow
from autodev.schemas import (
    GateStatus,
    ImplementationResult,
    Language,
    Milestone,
    MilestonePlan,
    PipelineMode,
    ReleaseCheckReport,
    ReleaseDecision,
    Severity,
    SeverityFinding,
    VerificationReport,
)
from autodev.state import RunState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(tmp_path: Path) -> RunState:
    """Create a minimal RunState that has been persisted."""
    run = RunState(repo_path=str(tmp_path))
    run.state.languages = [Language.PYTHON]
    run.state.mode = PipelineMode.DRY_RUN
    run.save()
    return run


def _passing_rc() -> ReleaseCheckReport:
    return ReleaseCheckReport(
        all_milestones_complete=True,
        all_acceptance_evidence_present=True,
        open_critical_issues=0,
        delivery_report_present=True,
        docs_present=True,
        mock_execution_used=False,
        dry_run=False,
        decision=ReleaseDecision.RELEASE_READY,
        reasons=[],
    )


def _blocking_rc() -> ReleaseCheckReport:
    return ReleaseCheckReport(
        all_milestones_complete=False,
        decision=ReleaseDecision.BLOCKED,
        reasons=["security review failed"],
        open_critical_issues=1,
    )


# ---------------------------------------------------------------------------
# Test 1 — initialization
# ---------------------------------------------------------------------------


def test_release_flow_initialization() -> None:
    """ReleaseFlow can be constructed with no arguments."""
    flow = ReleaseFlow()
    assert flow.release_manager is not None
    assert flow.reporter is not None


# ---------------------------------------------------------------------------
# Test 2 — happy path: all gates pass, decision == RELEASE_READY
# ---------------------------------------------------------------------------


def test_release_flow_release_check_happy_path(tmp_path: Path) -> None:
    """When all gates pass, check() returns ReleaseCheckReport with RELEASE_READY."""
    run = _make_run(tmp_path)
    flow = ReleaseFlow()
    passing = _passing_rc()

    with patch.object(flow.release_manager, "check", return_value=passing), patch.object(
        flow.reporter, "write_final_report", return_value=str(tmp_path / "final_report.md")
    ):
        rc = flow.check(run)

    assert rc.decision == ReleaseDecision.RELEASE_READY
    assert rc.all_milestones_complete is True
    assert rc.reasons == []


# ---------------------------------------------------------------------------
# Test 3 — BLOCKER finding blocks release
# ---------------------------------------------------------------------------


def test_release_flow_blocker_finding_blocks_release(tmp_path: Path) -> None:
    """A BLOCKER SeverityFinding causes decision == BLOCKED."""
    run = _make_run(tmp_path)
    flow = ReleaseFlow()

    # Build a state with a security review that has a BLOCKER finding.
    from autodev.schemas import GateStatus, SecurityReviewReport

    blocker = SeverityFinding(
        severity=Severity.BLOCKER,
        category="security",
        title="SQL injection in query builder",
        detail="Unsanitised user input reaches raw SQL.",
        source_agent="security_reviewer",
    )
    run.state.security_review = SecurityReviewReport(
        findings=["sql injection"],
        blocked_commands=["DROP TABLE"],
        status=GateStatus.FAILED,
        severity_findings=[blocker],
    )
    run.save()

    # Let the real ReleaseGate evaluate state (no mock on gate.check) so we
    # exercise the actual security-blocked branch.
    with patch.object(flow.reporter, "write_final_report", return_value=""):
        rc = flow.check(run)

    assert rc.decision == ReleaseDecision.BLOCKED
    assert any("security" in r for r in rc.reasons)


# ---------------------------------------------------------------------------
# Test 4 — release_report / final_report is written to disk
# ---------------------------------------------------------------------------


def test_release_flow_writes_release_report(tmp_path: Path) -> None:
    """ReleaseFlow.check() causes Reporter.write_final_report() to be called,
    which writes delivery/final_report.md under the run root."""
    run = _make_run(tmp_path)
    flow = ReleaseFlow()
    passing = _passing_rc()

    with patch.object(flow.release_manager, "check", return_value=passing):
        # Use the REAL reporter so we verify actual disk write.
        flow.check(run)

    expected = (
        Path(tmp_path) / ".dev-factory" / "runs" / run.run_id / "delivery" / "final_report.md"
    )
    assert expected.exists(), "final_report.md must be written by ReleaseFlow.check()"
    content = expected.read_text()
    assert run.run_id in content, "final_report.md must reference the run_id"


# ---------------------------------------------------------------------------
# Test 5 — no external CLI required (mock executor only)
# ---------------------------------------------------------------------------


def test_release_flow_no_external_cli_required(tmp_path: Path) -> None:
    """ReleaseFlow runs end-to-end with only mocked components; no codex/claude binary needed."""
    run = _make_run(tmp_path)
    flow = ReleaseFlow()

    mock_rc = ReleaseCheckReport(
        decision=ReleaseDecision.NOT_RELEASE_READY,
        reasons=["dry-run mode; no real changes applied"],
        dry_run=True,
    )

    with patch.object(flow.release_manager, "check", return_value=mock_rc), patch.object(
        flow.reporter, "write_final_report", return_value=""
    ) as mock_write:
        rc = flow.check(run)
        mock_write.assert_called_once_with(run)

    assert rc.decision == ReleaseDecision.NOT_RELEASE_READY
    assert rc.dry_run is True


# ---------------------------------------------------------------------------
# Test 6 — check() saves release_check into run.state and persists run
# ---------------------------------------------------------------------------


def test_release_flow_persists_release_check_to_run_state(tmp_path: Path) -> None:
    """check() must attach the ReleaseCheckReport to run.state.release_check and call run.save()."""
    run = _make_run(tmp_path)
    flow = ReleaseFlow()
    passing = _passing_rc()

    with patch.object(flow.release_manager, "check", return_value=passing), patch.object(
        flow.reporter, "write_final_report", return_value=""
    ):
        flow.check(run)

    # run.state.release_check must be populated
    assert run.state.release_check is not None
    assert run.state.release_check.decision == ReleaseDecision.RELEASE_READY

    # The state must have been saved to disk
    state_file = Path(tmp_path) / ".dev-factory" / "runs" / run.run_id / "run_state.json"
    data = json.loads(state_file.read_text())
    rc_data = data.get("release_check")
    assert rc_data is not None
    assert rc_data["decision"] == ReleaseDecision.RELEASE_READY.value


# ---------------------------------------------------------------------------
# Test 7 — check() also saves verification/release_check.json artifact
# ---------------------------------------------------------------------------


def test_release_flow_saves_release_check_json_artifact(tmp_path: Path) -> None:
    """check() must call run.save_json('verification/release_check.json', rc)."""
    run = _make_run(tmp_path)
    flow = ReleaseFlow()
    passing = _passing_rc()

    with patch.object(flow.release_manager, "check", return_value=passing), patch.object(
        flow.reporter, "write_final_report", return_value=""
    ):
        flow.check(run)

    artifact = (
        Path(tmp_path)
        / ".dev-factory"
        / "runs"
        / run.run_id
        / "verification"
        / "release_check.json"
    )
    assert artifact.exists(), "verification/release_check.json must be written"
    data = json.loads(artifact.read_text())
    assert data["decision"] == ReleaseDecision.RELEASE_READY.value
