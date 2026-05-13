"""System Architect — produces ArchitectureSpec from PRD + scan."""
from __future__ import annotations

from ..planners.project_planner import ProjectPlanner
from ..schemas import ArchitectureSpec, Language, PRD, RepoScanResult
from ._crewai_bridge import make_agent


class SystemArchitectAgent:
    def __init__(self) -> None:
        self.planner = ProjectPlanner()
        self.agent = make_agent(
            role="System Architect",
            goal="Translate PRD + repo scan into a concrete architecture spec.",
            backstory="A principal engineer focused on boundary clarity and modules.",
        )

    def design(self, *, prd: PRD, scan: RepoScanResult, languages: list[Language]) -> ArchitectureSpec:
        return self.planner.plan_architecture(prd=prd, scan=scan, languages=languages)

    def render_markdown(self, spec: ArchitectureSpec) -> str:
        lines = [f"# {spec.title}", "", spec.overview, "", "## Modules"]
        for m in spec.modules:
            lines.append(f"- **{m.name}** ({m.language.value}): {m.purpose}; depends_on={m.depends_on}")
        lines.append("\n## Dependency Graph")
        lines.append("```mermaid")
        lines.append("flowchart LR")
        for src, dst in spec.dependency_graph.edges:
            lines.append(f"  {src} --> {dst}")
        for n in spec.dependency_graph.nodes:
            lines.append(f"  {n}([{n}])")
        lines.append("```")
        lines.append("\n## Decisions")
        for d in spec.decisions:
            lines.append(f"- {d}")
        return "\n".join(lines) + "\n"
