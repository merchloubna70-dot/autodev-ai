"""Test Designer — emits TestPlan entries per milestone."""
from __future__ import annotations

from ..schemas import (
    DeliveryTask,
    Language,
    Milestone,
    TaskType,
    TestPlan,
    TestPlanEntry,
)
from ._crewai_bridge import make_agent

_PYTHON_PROPERTY_HINT = "integers()"  # default Hypothesis strategy hint


class TestDesignerAgent:
    def __init__(self, *, emit_property_tests: bool = True) -> None:
        """
        Parameters
        ----------
        emit_property_tests:
            When True, for each task with TaskType.TEST or FEATURE on a Python
            target, emit an additional ``TestPlanEntry`` of kind=``property``
            referencing Hypothesis ``@given`` strategy.  Defaults to True but
            only takes effect when the task has Python target_files.
        """
        self.emit_property_tests = emit_property_tests
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
            # Emit property tests when enabled and task is TEST or FEATURE on Python targets
            if (
                self.emit_property_tests
                and t.task_type in (TaskType.TEST, TaskType.FEATURE)
                and any(f.endswith(".py") for f in t.target_files)
            ):
                entries.append(TestPlanEntry(
                    task_id=t.task_id,
                    milestone_id=t.milestone_id,
                    kind="property",
                    description=(
                        f"Hypothesis @given property tests for {t.task_id}: "
                        f"strategies=[{_PYTHON_PROPERTY_HINT}]"
                    ),
                    target_files=t.target_files,
                    command="pytest --hypothesis-seed=0",
                ))
        return TestPlan(entries=entries)

    def _unit_command(self, languages: list[Language]) -> str | None:
        if Language.PYTHON in languages:
            return "pytest"
        if Language.RUST in languages:
            return "cargo test"
        if Language.TYPESCRIPT in languages:
            return "npm test"
        return None
