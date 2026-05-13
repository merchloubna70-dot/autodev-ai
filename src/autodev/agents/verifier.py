"""Verifier — independent re-check of milestone acceptance + state integrity."""
from __future__ import annotations

from ..schemas import GateStatus, PipelineRunState, VerificationReport
from ._crewai_bridge import make_agent


class VerifierAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Verifier",
            goal="Independently verify state, acceptance evidence, and refuse to fake passes.",
            backstory="A skeptical SRE who treats every 'green' as a hypothesis.",
        )

    def verify(self, state: PipelineRunState) -> VerificationReport:
        notes: list[str] = []
        acceptance: dict[str, GateStatus] = {}
        if state.milestone_plan:
            done_ids = {impl.milestone_id for impl in state.implementation_results if impl.success}
            for m in state.milestone_plan.milestones:
                acceptance[m.milestone_id] = GateStatus.PASSED if m.milestone_id in done_ids else GateStatus.FAILED
        integrity = state.repo_path is not None and bool(state.run_id)
        status = GateStatus.PASSED
        if any(s != GateStatus.PASSED for s in acceptance.values()) and not state.errors:
            status = GateStatus.FAILED
            notes.append("not all milestones complete")
        if state.errors:
            status = GateStatus.FAILED
            notes.append(f"errors recorded: {len(state.errors)}")
        if state.mock_execution_used:
            notes.append("verification observed mock executor usage — cannot claim production-passed")
        return VerificationReport(
            milestone_acceptance=acceptance,
            state_integrity_ok=integrity,
            status=status,
            notes=notes,
        )
