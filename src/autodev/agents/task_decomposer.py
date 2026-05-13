"""Task Decomposer — Milestones -> DeliveryTasks."""
from __future__ import annotations

from ..planners.task_planner import TaskPlanner
from ..schemas import ArchitectureSpec, DeliveryTask, Language, Milestone, PRD, ProductBrief, Scale
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
        prd: PRD | None = None,
        product_brief: ProductBrief | None = None,
        product_name: str | None = None,
        skip_m0_redundant_arch: bool = True,
        scale: Scale | None = None,
    ) -> list[DeliveryTask]:
        return self.core.plan(
            milestones=milestones,
            architecture=architecture,
            languages=languages,
            prd=prd,
            product_brief=product_brief,
            product_name=product_name,
            skip_m0_redundant_arch=skip_m0_redundant_arch,
            scale=scale,
        )
