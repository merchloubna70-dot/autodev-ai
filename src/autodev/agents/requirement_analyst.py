"""Requirement Analyst — extract functional + non-functional + acceptance."""
from __future__ import annotations

import re

from ..schemas import (
    PRD,
    AcceptanceCriterion,
    FunctionalRequirement,
    Language,
    NonFunctionalRequirement,
    ProductBrief,
    Scale,
    ScaleInferenceReport,
)
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

    # ------------------------------------------------------------------
    # Scale inference
    # ------------------------------------------------------------------

    def infer_scale(
        self,
        prd: PRD | None = None,
        brief: ProductBrief | None = None,
        languages: list[Language] | None = None,
        repo_scan=None,
        from_scratch: bool = False,
    ) -> ScaleInferenceReport:
        """Heuristically infer the project scale from available context.

        Rules (evaluated in priority order):
        - ``enterprise``: >50 AC  OR  ≥3 languages  OR  risk_level HIGH/CRITICAL
        - ``medium``:     15-50 AC  OR  2 languages
        - ``small``:      5-15 AC  AND  1 language
        - ``bug-fix``:    <5 AC  AND  not from_scratch
        """
        reasoning: list[str] = []

        # Count acceptance criteria
        ac_count = 0
        if prd and prd.acceptance_criteria:
            ac_count = len(prd.acceptance_criteria)
            reasoning.append(f"prd.acceptance_criteria count={ac_count}")

        # Count functional requirements from brief
        fr_count = 0
        if brief:
            fr_count = len(brief.use_cases or brief.goals or [])
            reasoning.append(f"brief fr_count={fr_count}")

        # Language count
        lang_list = languages or []
        language_count = len(lang_list)
        reasoning.append(f"language_count={language_count}")

        # Risk level
        risk_level = "low"
        if prd:
            high_risk_criteria = [
                ac for ac in (prd.acceptance_criteria or [])
                if re.search(r"HIGH|CRITICAL|security|compliance|regulatory", ac.description, re.IGNORECASE)
            ]
            if high_risk_criteria:
                risk_level = "high"
                reasoning.append(f"high-risk AC found: {len(high_risk_criteria)} criteria")

        # from_scratch flag
        if from_scratch:
            reasoning.append("from_scratch=True")

        # Determine scale
        if ac_count > 50 or language_count >= 3 or risk_level in ("high", "critical"):
            scale = Scale.ENTERPRISE
            reasoning.append("=> enterprise: >50 AC or ≥3 languages or high risk")
        elif ac_count >= 15 or language_count >= 2:
            scale = Scale.MEDIUM
            reasoning.append("=> medium: 15-50 AC or 2 languages")
        elif ac_count >= 5 or from_scratch:
            scale = Scale.SMALL
            reasoning.append("=> small: 5-15 AC or from_scratch")
        else:
            scale = Scale.BUG_FIX
            reasoning.append("=> bug-fix: <5 AC and not from_scratch")

        return ScaleInferenceReport(
            scale=scale,
            reasoning=reasoning,
            ac_count=ac_count,
            fr_count=fr_count,
            language_count=language_count,
            risk_level=risk_level,
        )


# BMAD-17: register agent menu at module load time
from ..schemas import AgentMenuEntry  # noqa: E402
from ._menu import register_default_menu  # noqa: E402

register_default_menu("requirement_analyst", [
    AgentMenuEntry(code="DR", description="Derive requirements from brief", skill="requirement_analyst"),
    AgentMenuEntry(code="IS", description="Infer project scale", skill="requirement_analyst"),
    AgentMenuEntry(code="NFR", description="Extract non-functional requirements", skill="requirement_analyst"),
])
