from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.test_designer import TestDesignerAgent


def build_test_design_task(agent: TestDesignerAgent):
    return make_task(
        description="Design unit, integration, e2e, and smoke tests aligned with acceptance criteria.",
        agent=agent.agent,
        expected_output="TestPlan JSON.",
    )
