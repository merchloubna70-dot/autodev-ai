from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.milestone_planner import MilestonePlannerAgent


def build_milestone_task(agent: MilestonePlannerAgent):
    return make_task(
        description="Generate 3-8 milestones with acceptance criteria and quality gates.",
        agent=agent.agent,
        expected_output="A list of Milestone JSON objects.",
    )
