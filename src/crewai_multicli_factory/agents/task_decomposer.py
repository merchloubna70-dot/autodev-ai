"""Task Decomposer — Milestones -> DeliveryTasks."""
from __future__ import annotations

from ..planners.task_planner import TaskPlanner
from ..schemas import ArchitectureSpec, DeliveryTask, Language, Milestone
from ._crewai_bridge import make_agent


class TaskDecomposerAgent:
    def __init__(self) -> None:
        self.core = TaskPlanner()
        self.agent = make_agent(
            role="Task Decomposer",
            goal="Break milestones into small, executable, single-CLI tasks.",
            backstory="A tech lead who writes tasks tight enough for Codex or Claude.",
        )

    def decompose(
        self,
        *,
        milestones: list[Milestone],
        architecture: ArchitectureSpec,
        languages: list[Language],
    ) -> list[DeliveryTask]:
        return self.core.plan(milestones=milestones, architecture=architecture, languages=languages)
