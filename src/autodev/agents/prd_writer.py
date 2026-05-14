"""PRD Writer — assemble PRD.md + PRD.json, or PRFAQ (Press Release + FAQ)."""
from __future__ import annotations

from ..schemas import (
    PRD,
    AcceptanceCriterion,
    FunctionalRequirement,
    NonFunctionalRequirement,
    PRFAQDocument,
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
        style: str = "prd",
    ) -> PRD:
        """Build a PRD object.  *style* is stored but the schema stays the same."""
        prd = PRD(
            product_name=brief.product_name,
            overview="; ".join(brief.goals) or f"PRD for {brief.product_name}",
            functional_requirements=functional,
            non_functional_requirements=non_functional,
            acceptance_criteria=acceptance,
            out_of_scope=brief.non_goals,
            risks=[],
            constraints=[brief.delivery_boundary] if brief.delivery_boundary else [],
        )
        # Attach style hint for render_markdown to pick up.
        object.__setattr__(prd, "_style_hint", style)
        return prd

    def render_markdown(self, prd: PRD, style: str = "prd") -> str:
        """Render PRD (or PRFAQ) as Markdown.

        *style* can be overridden here; the value baked in during ``write()``
        is used as fallback.
        """
        resolved = style or getattr(prd, "_style_hint", "prd")
        if resolved == "prfaq":
            return self._render_prfaq(prd)
        return self._render_prd(prd)

    # ------------------------------------------------------------------
    # Private renderers
    # ------------------------------------------------------------------

    def _render_prd(self, prd: PRD) -> str:
        lines = [f"# PRD — {prd.product_name}", "", f"_overview_: {prd.overview}", "", "## Functional Requirements"]
        for fr in prd.functional_requirements:
            lines.append(f"- **{fr.id}** ({fr.priority}) {fr.title}: {fr.description}")
        lines.append("\n## Non-Functional Requirements")
        for nf in prd.non_functional_requirements:
            lines.append(
                f"- **{nf.id}** ({nf.category}): {nf.description}"
                + (f" — target: {nf.measurable_target}" if nf.measurable_target else "")
            )
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

    def _render_prfaq(self, prd: PRD) -> str:
        """Amazon Working Backwards — Press Release + FAQ style."""
        doc = self._build_prfaq_doc(prd)
        lines: list[str] = []

        lines.append(f"# {doc.product_name} — Press Release")
        lines.append("")

        lines.append("## Headline")
        lines.append(doc.headline)
        lines.append("")

        lines.append("## Body")
        lines.append(doc.body)
        lines.append("")

        lines.append("## Customer Quote")
        lines.append(doc.customer_quote)
        lines.append("")

        lines.append("## Available Today")
        lines.append(doc.availability)
        lines.append("")

        lines.append("## FAQ")
        for i, qa in enumerate(doc.faqs, 1):
            lines.append(f"**Q{i}: {qa.get('question', '')}**")
            lines.append(qa.get("answer", ""))
            lines.append("")

        return "\n".join(lines)

    def _build_prfaq_doc(self, prd: PRD) -> PRFAQDocument:
        """Synthesise PRFAQ content from the PRD object."""
        overview = prd.overview or f"PRD for {prd.product_name}"

        headline = f"Introducing {prd.product_name}: {overview[:120]}"

        # Body: paragraph from functional requirements
        fr_bullets = "; ".join(
            f"{fr.title}" for fr in prd.functional_requirements[:5]
        )
        body = (
            f"{prd.product_name} ships today with the following capabilities: {fr_bullets}. "
            f"{overview}"
        )

        customer_quote = (
            f'"Finally, a tool that delivers {overview[:80]} — this changes how our team works." '
            f"— Early access user"
        )

        availability = (
            f"{prd.product_name} is available today. "
            + (f"Constraints: {'; '.join(prd.constraints)}." if prd.constraints else "")
        )

        # FAQ: derive from functional + non-functional requirements
        faqs: list[dict] = []
        for fr in prd.functional_requirements[:5]:
            faqs.append({
                "question": f"What does '{fr.title}' do?",
                "answer": fr.description,
            })
        for nf in prd.non_functional_requirements[:3]:
            faqs.append({
                "question": f"How is '{nf.category}' addressed?",
                "answer": nf.description + (f" Target: {nf.measurable_target}" if nf.measurable_target else ""),
            })
        # Fill to 10 with generic questions
        generic = [
            {"question": "Is this open source?", "answer": "Please refer to the project license."},
            {"question": "How do I get support?", "answer": "File an issue on the project repository."},
            {"question": "What are the out-of-scope items?", "answer": "; ".join(prd.out_of_scope) or "See PRD."},
        ]
        for g in generic:
            if len(faqs) >= 10:
                break
            faqs.append(g)

        return PRFAQDocument(
            product_name=prd.product_name,
            headline=headline,
            body=body,
            customer_quote=customer_quote,
            availability=availability,
            faqs=faqs,
        )


# BMAD-17: register agent menu at module load time
from ..schemas import AgentMenuEntry  # noqa: E402
from ._menu import register_default_menu  # noqa: E402

register_default_menu("prd_writer", [
    AgentMenuEntry(code="WP", description="Write PRD document", skill="prd_writer"),
    AgentMenuEntry(code="PF", description="Generate PRFAQ", skill="prd_writer"),
    AgentMenuEntry(code="EP", description="Export PRD to JSON", skill="prd_writer"),
])
