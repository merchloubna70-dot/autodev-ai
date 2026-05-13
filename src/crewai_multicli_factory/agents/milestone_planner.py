"""Milestone Planner agent — wraps planners.MilestonePlanner."""
from __future__ import annotations

from ..planners.milestone_planner import MilestonePlanner as _CorePlanner
from ..schemas import ArchitectureSpec, Language, Milestone
from ._crewai_bridge import make_agent


class MilestonePlannerAgent:
    def __init__(self) -> None:
        self.core = _CorePlanner()
        self.agent = make_agent(
            role="Milestone Planner",
            goal="Slice delivery into 3-8 verifiable milestones with acceptance criteria.",
            backstory="A delivery lead who turns architecture into checkpoints.",
        )

    def plan(self, *, architecture: ArchitectureSpec, languages: list[Language], max_milestones: int = 6) -> list[Milestone]:
        return self.core.plan(architecture=architecture, languages=languages, max_milestones=max_milestones)
