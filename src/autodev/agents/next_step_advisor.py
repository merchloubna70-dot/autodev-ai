"""Pure-Python decision-tree advisor for the next pipeline action.

No LLM calls — reads PipelineRunState and returns a NextStepAdvice via a
deterministic decision tree.
"""
from __future__ import annotations

from ..schemas import (
    GateStatus,
    NextStepAdvice,
    PipelineRunState,
    ReleaseDecision,
    Severity,
)


class NextStepAdvisor:
    """Suggest the next concrete action based on current PipelineRunState."""

    def __init__(self) -> None:
        pass

    def advise(self, state: PipelineRunState) -> NextStepAdvice:
        """Decision tree producing structured advice.

        Priority order:
        1. No release_check → run release-check
        2. release_check.decision == ReleaseReady → export-delivery
        3. Blocked + security failed → fix security findings
        4. NotReleaseReady + mock_execution_used → switch to apply mode
        5. NotReleaseReady + dry_run → rerun with --mode apply
        6. Any quality_gate.failed → fix top finding
        7. implementation_results has failed_task_ids → rerun failed milestone
        8. Default → run verify
        """
        run_id = state.run_id

        # Branch 1: no release_check
        if state.release_check is None:
            return NextStepAdvice(
                next_command=f"autodev release-check --run-id {run_id}",
                rationale="Release check has not been run yet; evaluate readiness first.",
                confidence=0.95,
                evidence_paths=["run_state.json"],
                stage_hint="verify",
            )

        rc = state.release_check

        # Branch 2: ReleaseReady
        if rc.decision == ReleaseDecision.RELEASE_READY:
            return NextStepAdvice(
                next_command=f"autodev export-delivery --run-id {run_id}",
                rationale="All gates passed and the release check is green — package the delivery.",
                confidence=0.99,
                evidence_paths=["quality/", "verification/"],
                stage_hint="ship",
            )

        # Branch 3: Blocked + security failed
        if rc.decision == ReleaseDecision.BLOCKED and state.security_review is not None:
            sr = state.security_review
            if sr.status == GateStatus.FAILED:
                # List top 3 BLOCKER findings
                blocker_titles = [
                    f.title
                    for f in sr.severity_findings
                    if f.severity == Severity.BLOCKER
                ][:3]
                blocker_summary = "; ".join(blocker_titles) if blocker_titles else "(see report)"
                return NextStepAdvice(
                    next_command=f"autodev fix-bug --bug '{blocker_summary}'",
                    rationale=(
                        "Release is BLOCKED by security findings. "
                        f"Top BLOCKER(s): {blocker_summary}. "
                        "Inspect quality/security_review.json for details."
                    ),
                    confidence=0.92,
                    evidence_paths=["quality/security_review.json"],
                    stage_hint="fix-security",
                )

        # Branch 4: NotReleaseReady + mock_execution_used
        if rc.decision == ReleaseDecision.NOT_RELEASE_READY and state.mock_execution_used:
            # Find first incomplete milestone
            next_milestone = _first_incomplete_milestone(state)
            milestone_arg = f" --milestone-id {next_milestone}" if next_milestone else ""
            return NextStepAdvice(
                next_command=(
                    f"autodev execute-milestone --run-id {run_id}"
                    f"{milestone_arg} --mode apply"
                ),
                rationale=(
                    "Execution used mock backends. Switch to apply mode to run real executors."
                ),
                confidence=0.88,
                evidence_paths=["execution/execution_calls.jsonl", "run_state.json"],
                stage_hint="apply",
            )

        # Branch 5: NotReleaseReady + dry_run flag
        if rc.decision == ReleaseDecision.NOT_RELEASE_READY and rc.dry_run:
            return NextStepAdvice(
                next_command=f"autodev execute-milestone --run-id {run_id} --mode apply",
                rationale="Pipeline ran in dry-run mode. Rerun with --mode apply to apply changes.",
                confidence=0.85,
                evidence_paths=["run_state.json"],
                stage_hint="apply",
            )

        # Branch 6: any quality gate failed
        top_finding = _top_quality_finding(state)
        if top_finding is not None:
            return NextStepAdvice(
                next_command=f"autodev fix-bug --bug '{top_finding}'",
                rationale=f"Quality gate failure detected: {top_finding}",
                confidence=0.80,
                evidence_paths=["quality/"],
                stage_hint="fix-quality",
            )

        # Branch 7: implementation_results has failed_task_ids
        failed_milestone = _first_failed_milestone(state)
        if failed_milestone is not None:
            return NextStepAdvice(
                next_command=f"autodev execute-milestone --run-id {run_id} --milestone-id {failed_milestone}",
                rationale=f"Milestone '{failed_milestone}' has failed tasks. Rerun to retry them.",
                confidence=0.78,
                evidence_paths=["execution/execution_calls.jsonl"],
                stage_hint="fix-impl",
            )

        # Branch 8: default
        return NextStepAdvice(
            next_command=f"autodev verify --run-id {run_id}",
            rationale="No clear blocker found. Refresh evidence by running the verifier.",
            confidence=0.60,
            evidence_paths=["verification/", "run_state.json"],
            stage_hint="verify",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first_incomplete_milestone(state: PipelineRunState) -> str | None:
    """Return the first milestone_id not yet successfully executed."""
    if not state.milestone_plan:
        return None
    done = {impl.milestone_id for impl in state.implementation_results if impl.success}
    for m in state.milestone_plan.milestones:
        if m.milestone_id not in done:
            return m.milestone_id
    return None


def _first_failed_milestone(state: PipelineRunState) -> str | None:
    """Return milestone_id of first ImplementationResult with failed_task_ids."""
    for impl in state.implementation_results:
        if impl.failed_task_ids:
            return impl.milestone_id
    return None


def _top_quality_finding(state: PipelineRunState) -> str | None:
    """Return the title of the first BLOCKER/MAJOR finding from quality gates."""
    for qg in state.quality_gates:
        if qg.overall_status == GateStatus.FAILED:
            for outcome in qg.outcomes:
                if outcome.status == GateStatus.FAILED and outcome.notes:
                    return outcome.notes[0]
            return f"quality gate failed for {qg.language.value}"
    return None
