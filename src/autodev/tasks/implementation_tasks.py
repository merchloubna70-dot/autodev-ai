from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.implementer import ImplementerAgent


def build_implementation_task(agent: ImplementerAgent, milestone_id: str):
    return make_task(
        description=(
            f"Implement milestone {milestone_id} by routing each task through the ExecutorRouter. "
            f"Do NOT call Codex or Claude executors directly. Honor allowed_files / forbidden_files."
        ),
        agent=agent.agent,
        expected_output="An ImplementationResult JSON object with task_results entries.",
    )
