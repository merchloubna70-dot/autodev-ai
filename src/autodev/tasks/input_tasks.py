from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.input_classifier import InputClassifierAgent


def build_input_classification_task(agent: InputClassifierAgent, raw_input: str):
    return make_task(
        description=f"Classify the following input and pick the right factory flow:\n\n{raw_input[:600]}",
        agent=agent.agent,
        expected_output="An InputClassification JSON object.",
    )
