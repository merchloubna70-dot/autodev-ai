"""PRD Writer — assemble PRD.md + PRD.json."""
from __future__ import annotations

from ..schemas import (
    AcceptanceCriterion,
    FunctionalRequirement,
    NonFunctionalRequirement,
    PRD,
    ProductBrief,
)
from ._crewai_bridge import make_agent


class PRDWriterAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="PRD Writer",
            goal="Compile a complete, machine-readable PRD.",
            backstory="A PM-writer hybrid who emits both markdown and JSON PRDs.",
        )

    def write(
        self,
        *,
        brief: ProductBrief,
        functional: list[FunctionalRequirement],
        non_functional: list[NonFunctionalRequirement],
        acceptance: list[AcceptanceCriterion],
    ) -> PRD:
        return PRD(
            product_name=brief.product_name,
            overview="; ".join(brief.goals) or f"PRD for {brief.product_name}",
            functional_requirements=functional,
            non_functional_requirements=non_functional,
            acceptance_criteria=acceptance,
            out_of_scope=brief.non_goals,
            risks=[],
            constraints=[brief.delivery_boundary] if brief.delivery_boundary else [],
        )

    def render_markdown(self, prd: PRD) -> str:
        lines = [f"# PRD — {prd.product_name}", "", f"_overview_: {prd.overview}", "", "## Functional Requirements"]
        for fr in prd.functional_requirements:
            lines.append(f"- **{fr.id}** ({fr.priority}) {fr.title}: {fr.description}")
        lines.append("\n## Non-Functional Requirements")
        for nf in prd.non_functional_requirements:
            lines.append(f"- **{nf.id}** ({nf.category}): {nf.description}"
                         + (f" — target: {nf.measurable_target}" if nf.measurable_target else ""))
        lines.append("\n## Acceptance Criteria")
        for ac in prd.acceptance_criteria:
            lines.append(f"- **{ac.id}** [{ac.verifiable_by}]: {ac.description}")
        if prd.out_of_scope:
            lines.append("\n## Out of Scope")
            for o in prd.out_of_scope:
                lines.append(f"- {o}")
        if prd.constraints:
            lines.append("\n## Constraints")
            for c in prd.constraints:
                lines.append(f"- {c}")
        return "\n".join(lines) + "\n"
