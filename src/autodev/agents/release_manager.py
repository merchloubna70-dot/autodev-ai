"""Release Manager — owns release_check + delivery report."""
from __future__ import annotations

from ..gates.release_gate import ReleaseGate
from ..reports.delivery_reporter import DeliveryReporter
from ..reports.release_reporter import ReleaseReporter
from ..schemas import DeliveryReport, PipelineRunState, ReleaseCheckReport
from ._crewai_bridge import make_agent


class ReleaseManagerAgent:
    def __init__(self) -> None:
        self.gate = ReleaseGate()
        self.delivery_reporter = DeliveryReporter()
        self.release_reporter = ReleaseReporter()
        self.agent = make_agent(
            role="Release Manager",
            goal="Produce release_check, release notes, and a delivery report — never overstate readiness.",
            backstory="An eng manager who has had to roll back too many releases.",
        )

    def check(self, state: PipelineRunState) -> ReleaseCheckReport:
        return self.gate.check(state)

    def build_delivery(self, state: PipelineRunState, *, project_name: str) -> DeliveryReport:
        return self.delivery_reporter.build(state, project_name=project_name)

    def render_release_notes(self, state: PipelineRunState, *, project_name: str) -> str:
        return self.release_reporter.render_release_notes(state, project_name=project_name)
