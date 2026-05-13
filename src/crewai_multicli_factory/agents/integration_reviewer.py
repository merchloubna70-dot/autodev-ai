"""Integration Reviewer — cross-language contract + dependency drift."""
from __future__ import annotations

from ..gates.integration_gate import IntegrationGate
from ..schemas import (
    ApiContract,
    DependencyGraph,
    IntegrationReviewReport,
    Language,
)
from ._crewai_bridge import make_agent


class IntegrationReviewerAgent:
    def __init__(self) -> None:
        self.gate = IntegrationGate()
        self.agent = make_agent(
            role="Integration Reviewer",
            goal="Detect API/contract/schema drift across modules and languages.",
            backstory="A platform engineer who watches the seams between services.",
        )

    def review(
        self,
        *,
        api_contract: ApiContract | None,
        dependency_graph: DependencyGraph | None,
        languages: list[Language],
    ) -> IntegrationReviewReport:
        return self.gate.review(
            api_contract=api_contract,
            dependency_graph=dependency_graph,
            languages=[l.value for l in languages],
        )
