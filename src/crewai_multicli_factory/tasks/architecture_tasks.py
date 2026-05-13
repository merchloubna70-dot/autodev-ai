from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.system_architect import SystemArchitectAgent


def build_architecture_task(agent: SystemArchitectAgent):
    return make_task(
        description="Translate PRD + repo scan into an ArchitectureSpec with modules, contracts and dependency graph.",
        agent=agent.agent,
        expected_output="ArchitectureSpec JSON + architecture.md markdown.",
    )
