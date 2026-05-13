"""Release gate — decides ReleaseReady / NotReleaseReady / Blocked.

Fail-closed semantics:
- If any milestone is incomplete -> NotReleaseReady
- If mock execution was used -> NotReleaseReady (must be acknowledged)
- If dry-run -> NotReleaseReady
- If any failed gate -> Blocked
"""
from __future__ import annotations

from ..schemas import (
    GateStatus,
    PipelineRunState,
    ReleaseCheckReport,
    ReleaseDecision,
)


class ReleaseGate:
    def check(self, state: PipelineRunState) -> ReleaseCheckReport:
        report = ReleaseCheckReport()
        reasons: list[str] = []

        # Milestones
        if state.milestone_plan and state.milestone_plan.milestones:
            done_ids = {
                impl.milestone_id
                for impl in state.implementation_results
                if impl.success
            }
            all_ids = {m.milestone_id for m in state.milestone_plan.milestones}
            report.all_milestones_complete = bool(all_ids) and all_ids.issubset(done_ids)
            if not report.all_milestones_complete:
                reasons.append(f"incomplete milestones: missing={sorted(all_ids - done_ids)}")
        else:
            reasons.append("no milestone plan present")

        # Quality gates
        for qg in state.quality_gates:
            if qg.overall_status == GateStatus.FAILED:
                reasons.append(f"quality gate failed: {qg.language.value}")

        # Security
        if state.security_review and state.security_review.status == GateStatus.FAILED:
            reasons.append("security review failed")
            report.open_critical_issues += len(state.security_review.blocked_commands)

        # Integration
        if state.integration_review and state.integration_review.status == GateStatus.FAILED:
            reasons.append("integration review failed")

        # Verification
        if state.verification and state.verification.status == GateStatus.FAILED:
            reasons.append("verification failed")

        # Acceptance evidence
        if state.verification and state.verification.milestone_acceptance:
            failed = [m for m, s in state.verification.milestone_acceptance.items() if s != GateStatus.PASSED]
            report.all_acceptance_evidence_present = not failed
            if failed:
                reasons.append(f"milestones without acceptance evidence: {failed}")
        else:
            report.all_acceptance_evidence_present = False
            reasons.append("no verification acceptance evidence")

        # Mock / dry-run
        report.mock_execution_used = state.mock_execution_used
        report.dry_run = state.mode.value == "dry-run"
        if report.mock_execution_used:
            reasons.append("mock executor was used; cannot mark ReleaseReady from mock evidence alone")
        if report.dry_run:
            reasons.append("dry-run mode; no real changes applied")

        # Docs presence (heuristic)
        report.delivery_report_present = state.delivery_report is not None
        report.docs_present = report.delivery_report_present

        if reasons:
            report.decision = ReleaseDecision.NOT_RELEASE_READY
        else:
            report.decision = ReleaseDecision.RELEASE_READY
        if any(r.startswith("security review failed") for r in reasons):
            report.decision = ReleaseDecision.BLOCKED
        report.reasons = reasons
        return report
