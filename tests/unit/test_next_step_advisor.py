"""Unit tests for NextStepAdvisor — one test per decision-tree branch."""
from __future__ import annotations

from autodev.agents.next_step_advisor import NextStepAdvisor
from autodev.schemas import (
    GateOutcome,
    GateStatus,
    ImplementationResult,
    Language,
    Milestone,
    MilestonePlan,
    PipelineRunState,
    QualityGateResult,
    ReleaseCheckReport,
    ReleaseDecision,
    SecurityReviewReport,
    Severity,
    SeverityFinding,
)


def _base_state(**kwargs) -> PipelineRunState:
    return PipelineRunState(run_id="run-test-001", repo_path="/tmp/repo", **kwargs)


# Branch 1: release_check is None → run release-check
def test_advise_no_release_check():
    state = _base_state()
    advice = NextStepAdvisor().advise(state)
    assert "release-check" in advice.next_command
    assert "run-test-001" in advice.next_command
    assert advice.confidence > 0.9
    assert advice.stage_hint == "verify"


# Branch 2: release_check.decision == ReleaseReady → export-delivery
def test_advise_release_ready():
    state = _base_state(
        release_check=ReleaseCheckReport(
            decision=ReleaseDecision.RELEASE_READY,
            all_milestones_complete=True,
            all_acceptance_evidence_present=True,
            dry_run=False,
        )
    )
    advice = NextStepAdvisor().advise(state)
    assert "export-delivery" in advice.next_command
    assert "run-test-001" in advice.next_command
    assert advice.stage_hint == "ship"
    assert advice.confidence > 0.95


# Branch 3: Blocked + security_review.status == failed → fix security findings
def test_advise_blocked_security_failed():
    sec = SecurityReviewReport(
        status=GateStatus.FAILED,
        severity_findings=[
            SeverityFinding(
                severity=Severity.BLOCKER,
                category="security",
                title="SQL injection in user_input",
                source_agent="security_reviewer",
            ),
            SeverityFinding(
                severity=Severity.BLOCKER,
                category="security",
                title="Hardcoded credentials",
                source_agent="security_reviewer",
            ),
        ],
    )
    state = _base_state(
        release_check=ReleaseCheckReport(decision=ReleaseDecision.BLOCKED, dry_run=False),
        security_review=sec,
    )
    advice = NextStepAdvisor().advise(state)
    assert "fix-bug" in advice.next_command
    assert "SQL injection" in advice.next_command
    assert advice.stage_hint == "fix-security"
    assert "quality/security_review.json" in advice.evidence_paths


# Branch 4: NotReleaseReady + mock_execution_used → switch to apply mode
def test_advise_not_ready_mock_used():
    state = _base_state(
        mock_execution_used=True,
        release_check=ReleaseCheckReport(
            decision=ReleaseDecision.NOT_RELEASE_READY,
            mock_execution_used=True,
            dry_run=True,
        ),
        milestone_plan=MilestonePlan(
            milestones=[
                Milestone(milestone_id="M1", title="First", objective="obj"),
                Milestone(milestone_id="M2", title="Second", objective="obj"),
            ],
        ),
        implementation_results=[
            ImplementationResult(milestone_id="M1", success=True),
        ],
    )
    advice = NextStepAdvisor().advise(state)
    assert "--mode apply" in advice.next_command
    assert "M2" in advice.next_command  # next incomplete milestone
    assert advice.stage_hint == "apply"


# Branch 5: NotReleaseReady + dry_run flag → rerun with --mode apply
def test_advise_not_ready_dry_run():
    state = _base_state(
        mock_execution_used=False,
        release_check=ReleaseCheckReport(
            decision=ReleaseDecision.NOT_RELEASE_READY,
            mock_execution_used=False,
            dry_run=True,
        ),
    )
    advice = NextStepAdvisor().advise(state)
    assert "--mode apply" in advice.next_command
    assert advice.stage_hint == "apply"


# Branch 6: quality gate failed → run fix-bug with top finding
def test_advise_quality_gate_failed():
    qg = QualityGateResult(
        language=Language.PYTHON,
        overall_status=GateStatus.FAILED,
        outcomes=[
            GateOutcome(
                name="pytest",
                status=GateStatus.FAILED,
                notes=["AssertionError in test_login"],
            ),
        ],
    )
    state = _base_state(
        release_check=ReleaseCheckReport(
            decision=ReleaseDecision.NOT_RELEASE_READY,
            dry_run=False,
            mock_execution_used=False,
        ),
        quality_gates=[qg],
    )
    advice = NextStepAdvisor().advise(state)
    assert "fix-bug" in advice.next_command
    assert "AssertionError in test_login" in advice.next_command
    assert advice.stage_hint == "fix-quality"


# Branch 7: implementation_results has failed_task_ids → rerun failed milestone
def test_advise_failed_task_ids():
    state = _base_state(
        release_check=ReleaseCheckReport(
            decision=ReleaseDecision.NOT_RELEASE_READY,
            dry_run=False,
            mock_execution_used=False,
        ),
        implementation_results=[
            ImplementationResult(
                milestone_id="M3",
                success=False,
                failed_task_ids=["T1", "T2"],
            ),
        ],
    )
    advice = NextStepAdvisor().advise(state)
    assert "execute-milestone" in advice.next_command
    assert "M3" in advice.next_command
    assert advice.stage_hint == "fix-impl"


# Branch 8: default → run verify
def test_advise_default_verify():
    state = _base_state(
        release_check=ReleaseCheckReport(
            decision=ReleaseDecision.NOT_RELEASE_READY,
            dry_run=False,
            mock_execution_used=False,
        ),
    )
    advice = NextStepAdvisor().advise(state)
    assert "verify" in advice.next_command
    assert "run-test-001" in advice.next_command
    assert advice.stage_hint == "verify"
