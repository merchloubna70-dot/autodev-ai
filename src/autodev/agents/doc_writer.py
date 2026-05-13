"""Doc Writer — README / usage / architecture docs for the delivered project."""
from __future__ import annotations

from ..schemas import ArchitectureSpec, PRD
from ._crewai_bridge import make_agent


class DocWriterAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Doc Writer",
            goal="Produce concise, accurate README, usage, and architecture docs.",
            backstory="A tech writer who reads code before writing docs.",
        )

    def readme(self, *, prd: PRD, architecture: ArchitectureSpec | None) -> str:
        lines = [f"# {prd.product_name}", "", prd.overview, "", "## Features"]
        for fr in prd.functional_requirements[:8]:
            lines.append(f"- {fr.title}")
        if architecture:
            lines.append("\n## Architecture")
            lines.append(architecture.overview)
            lines.append("\nModules:")
            for m in architecture.modules:
                lines.append(f"- `{m.name}` ({m.language.value}): {m.purpose}")
        lines.append("\n## Status")
        lines.append("Scaffolded and delivered by `autodev`.")
        return "\n".join(lines) + "\n"

    def usage(self, *, prd: PRD) -> str:
        return (
            f"# Usage — {prd.product_name}\n\n"
            "## Install\n\n"
            "```\npip install -e .\n```\n\n"
            "## Run\n\n"
            "Refer to acceptance criteria in PRD for behavior expectations.\n"
        )
