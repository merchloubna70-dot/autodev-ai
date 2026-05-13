"""ProjectContextFlow — BMAD-11 wrapper around ContextGeneratorAgent.

Usage:
    flow = ProjectContextFlow()
    ctx = flow.run(ProjectContextInput(repo_path=".", product_name="MyApp"))
"""
from __future__ import annotations

from pathlib import Path

from ..agents.context_generator import ContextGeneratorAgent
from ..schemas import ProjectContext, ProjectContextInput


class ProjectContextFlow:
    """Thin orchestration wrapper; delegates all logic to ContextGeneratorAgent."""

    def __init__(self) -> None:
        self._agent = ContextGeneratorAgent()

    def run(self, inputs: ProjectContextInput) -> ProjectContext:
        """Discover → synthesize → commit.  Returns ProjectContext with file_path set."""
        brief: str | None = None
        if inputs.brief_path:
            try:
                brief = Path(inputs.brief_path).read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                brief = None

        return self._agent.run(
            repo_path=inputs.repo_path,
            brief=brief,
            product_name=inputs.product_name,
        )
