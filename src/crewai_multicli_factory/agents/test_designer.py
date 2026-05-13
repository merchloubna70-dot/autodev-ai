"""Test Designer — emits TestPlan entries per milestone."""
from __future__ import annotations

from ..schemas import (
    DeliveryTask,
    Language,
    Milestone,
    TestPlan,
    TestPlanEntry,
)
from ._crewai_bridge import make_agent


class TestDesignerAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Test Designer",
            goal="Design unit / integration / e2e / smoke tests mapped to acceptance criteria.",
            backstory="A QA lead who refuses to ship without acceptance-aligned tests.",
        )

    def design(self, *, milestones: list[Milestone], tasks: list[DeliveryTask], languages: list[Language]) -> TestPlan:
        entries: list[TestPlanEntry] = []
        for m in milestones:
            entries.append(TestPlanEntry(
                milestone_id=m.milestone_id,
                kind="unit",
                description=f"Unit tests for {m.milestone_id} acceptance criteria",
                command=self._unit_command(languages),
            ))
            if m.milestone_id in ("M3", "M4", "M5"):
                entries.append(TestPlanEntry(
                    milestone_id=m.milestone_id,
                    kind="integration",
                    description=f"Integration tests for {m.milestone_id}",
                ))
            if m.milestone_id == "M5":
                entries.append(TestPlanEntry(
                    milestone_id=m.milestone_id,
                    kind="smoke",
                    description="End-to-end smoke test against built artifact",
                ))
        for t in tasks:
            if t.required_tests:
                for rt in t.required_tests:
                    entries.append(TestPlanEntry(task_id=t.task_id, milestone_id=t.milestone_id, kind="unit",
                                                 description=rt, target_files=t.target_files))
        return TestPlan(entries=entries)

    def _unit_command(self, languages: list[Language]) -> str | None:
        if Language.PYTHON in languages:
            return "pytest"
        if Language.RUST in languages:
            return "cargo test"
        if Language.TYPESCRIPT in languages:
            return "npm test"
        return None
