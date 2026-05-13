from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.quality_gate import QualityGateAgent


def build_quality_task(agent: QualityGateAgent):
    return make_task(
        description="Run per-language quality gates and refuse to bless skipped/failed as passed.",
        agent=agent.agent,
        expected_output="List of QualityGateResult JSON objects.",
    )
