"""Requirement Analyst — extract functional + non-functional + acceptance."""
from __future__ import annotations

import re

from ..schemas import AcceptanceCriterion, FunctionalRequirement, NonFunctionalRequirement, ProductBrief
from ._crewai_bridge import make_agent


class RequirementAnalystAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Requirement Analyst",
            goal="Lift functional + non-functional + acceptance requirements from a brief.",
            backstory="A BA who writes machine-checkable acceptance criteria.",
        )

    def derive(self, *, brief: ProductBrief, source_text: str = "") -> tuple[
        list[FunctionalRequirement], list[NonFunctionalRequirement], list[AcceptanceCriterion]
    ]:
        functional: list[FunctionalRequirement] = []
        for i, uc in enumerate(brief.use_cases or brief.goals, start=1):
            functional.append(FunctionalRequirement(
                id=f"FR-{i:03d}",
                title=uc[:80],
                description=uc,
                priority="MUST" if i <= 3 else "SHOULD",
                acceptance_criteria=[f"{uc}: validated by integration test"],
            ))
        nf: list[NonFunctionalRequirement] = [
            NonFunctionalRequirement(id="NFR-001", category="security",
                                     description="No secrets in repo; .env never read by agents.",
                                     measurable_target="0 secret findings"),
            NonFunctionalRequirement(id="NFR-002", category="quality",
                                     description="All language gates pass or are explicitly waived.",
                                     measurable_target="green or annotated waiver"),
        ]
        for line in source_text.splitlines():
            m = re.search(r"non-?functional[:\s]+(.*)", line, re.IGNORECASE)
            if m:
                nf.append(NonFunctionalRequirement(
                    id=f"NFR-{len(nf)+1:03d}",
                    category="custom", description=m.group(1).strip(),
                ))
        ac = [
            AcceptanceCriterion(id=f"AC-{fr.id}", description=ac_line, verifiable_by="test")
            for fr in functional for ac_line in fr.acceptance_criteria
        ]
        return functional, nf, ac
