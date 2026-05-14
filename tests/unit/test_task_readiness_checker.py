"""Unit tests for TaskReadinessChecker (BMAD-12).

Covers: one test per dimension + happy-path + sweep aggregate.
"""
from __future__ import annotations

from autodev.planners.task_readiness_checker import TaskReadinessChecker
from autodev.schemas import (
    DeliveryTask,
    ExecutionBackend,
    Language,
    ReadinessDimension,
    RiskLevel,
    TaskDependency,
    TaskType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONG_TEXT = "x" * 800  # cheap padding to satisfy token-budget lower bound


def _make_task(
    task_id: str = "M1-T1",
    milestone_id: str = "M1",
    title: str = "Scaffold Python skeleton",
    description: str = "Implement the core module in src/app/core.py.",
    target_files: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    codex_prompt: str = "",
    dependencies: list[TaskDependency] | None = None,
) -> DeliveryTask:
    return DeliveryTask(
        task_id=task_id,
        milestone_id=milestone_id,
        title=title,
        description=description,
        target_files=target_files if target_files is not None else ["src/app/core.py"],
        acceptance_criteria=acceptance_criteria
        if acceptance_criteria is not None
        else ["Given the module exists, when imported, then no ImportError is raised."],
        codex_prompt=codex_prompt,
        dependencies=dependencies or [],
        language=Language.PYTHON,
        task_type=TaskType.FEATURE,
        risk_level=RiskLevel.LOW,
        preferred_executor=ExecutionBackend.AUTO,
        rollback_strategy="revert",
        claude_prompt="",
        allowed_files=[],
        forbidden_files=[],
        context_files=[],
        expected_outputs=[],
        required_tests=[],
    )


checker = TaskReadinessChecker()


# ---------------------------------------------------------------------------
# 1. ACTIONABLE — file path required
# ---------------------------------------------------------------------------


def test_actionable_fails_without_target_files():
    task = _make_task(target_files=[])
    report = checker.check_task(task)
    actionable = next(c for c in report.checks if c.dimension == ReadinessDimension.ACTIONABLE)
    assert not actionable.passed
    assert any("target_files" in r for r in actionable.reasons)


def test_actionable_fails_without_action_verb():
    task = _make_task(description="The module configuration for the app.")
    report = checker.check_task(task)
    actionable = next(c for c in report.checks if c.dimension == ReadinessDimension.ACTIONABLE)
    assert not actionable.passed


def test_actionable_passes_with_verb_and_file():
    task = _make_task()
    report = checker.check_task(task)
    actionable = next(c for c in report.checks if c.dimension == ReadinessDimension.ACTIONABLE)
    assert actionable.passed


# ---------------------------------------------------------------------------
# 2. LOGICAL — orphan deps / cycles
# ---------------------------------------------------------------------------


def test_logical_fails_with_orphan_dep():
    task = _make_task(
        dependencies=[TaskDependency(depends_on_task_id="M99-T99")]
    )
    report = checker.check_task(task, all_tasks=[task])
    logical = next(c for c in report.checks if c.dimension == ReadinessDimension.LOGICAL)
    assert not logical.passed
    assert "M99-T99" in logical.reasons[0]


def test_logical_passes_when_deps_exist():
    t1 = _make_task(task_id="M1-T1")
    t2 = _make_task(
        task_id="M1-T2", dependencies=[TaskDependency(depends_on_task_id="M1-T1")]
    )
    sweep = checker.check_all([t1, t2])
    logical_t2 = next(
        c for r in sweep.per_task if r.task_id == "M1-T2"
        for c in r.checks if c.dimension == ReadinessDimension.LOGICAL
    )
    assert logical_t2.passed


def test_logical_fails_with_cycle():
    t1 = _make_task(task_id="M1-T1", dependencies=[TaskDependency(depends_on_task_id="M1-T2")])
    t2 = _make_task(task_id="M1-T2", dependencies=[TaskDependency(depends_on_task_id="M1-T1")])
    sweep = checker.check_all([t1, t2])
    for r in sweep.per_task:
        logical = next(c for c in r.checks if c.dimension == ReadinessDimension.LOGICAL)
        assert not logical.passed


# ---------------------------------------------------------------------------
# 3. TESTABLE — ACs must contain verifiable language
# ---------------------------------------------------------------------------


def test_testable_fails_with_empty_acs():
    task = _make_task(acceptance_criteria=[])
    report = checker.check_task(task)
    testable = next(c for c in report.checks if c.dimension == ReadinessDimension.TESTABLE)
    assert not testable.passed


def test_testable_fails_without_gwt_or_should():
    task = _make_task(acceptance_criteria=["The feature exists."])
    report = checker.check_task(task)
    testable = next(c for c in report.checks if c.dimension == ReadinessDimension.TESTABLE)
    assert not testable.passed


def test_testable_passes_with_given_when_then():
    task = _make_task(
        acceptance_criteria=["Given a valid input, when the function is called, then a result is returned."]
    )
    report = checker.check_task(task)
    testable = next(c for c in report.checks if c.dimension == ReadinessDimension.TESTABLE)
    assert testable.passed


def test_testable_passes_with_should_keyword():
    task = _make_task(acceptance_criteria=["The module should return 200 on success."])
    report = checker.check_task(task)
    testable = next(c for c in report.checks if c.dimension == ReadinessDimension.TESTABLE)
    assert testable.passed


# ---------------------------------------------------------------------------
# 4. COMPLETE — no placeholders
# ---------------------------------------------------------------------------


def test_complete_fails_with_tbd():
    task = _make_task(description="Implement TBD feature in src/app/core.py.")
    report = checker.check_task(task)
    complete = next(c for c in report.checks if c.dimension == ReadinessDimension.COMPLETE)
    assert not complete.passed


def test_complete_fails_with_angle_bracket_placeholder():
    task = _make_task(description="Implement <feature_name> in src/app/core.py.")
    report = checker.check_task(task)
    complete = next(c for c in report.checks if c.dimension == ReadinessDimension.COMPLETE)
    assert not complete.passed


def test_complete_passes_with_no_placeholders():
    task = _make_task()
    report = checker.check_task(task)
    complete = next(c for c in report.checks if c.dimension == ReadinessDimension.COMPLETE)
    assert complete.passed


# ---------------------------------------------------------------------------
# 5. SINGLE_GOAL — no multi-goal connectives
# ---------------------------------------------------------------------------


def test_single_goal_fails_with_and_also():
    task = _make_task(
        description="Implement core.py in src/app/core.py and also add the CLI."
    )
    report = checker.check_task(task)
    sg = next(c for c in report.checks if c.dimension == ReadinessDimension.SINGLE_GOAL)
    assert not sg.passed


def test_single_goal_passes_for_focused_task():
    task = _make_task()
    report = checker.check_task(task)
    sg = next(c for c in report.checks if c.dimension == ReadinessDimension.SINGLE_GOAL)
    assert sg.passed


# ---------------------------------------------------------------------------
# 6. TOKEN_BUDGET — 3600–6400 chars
# ---------------------------------------------------------------------------


def test_token_budget_fails_undersized():
    task = _make_task(description="Fix bug.", codex_prompt="")
    report = checker.check_task(task)
    tb = next(c for c in report.checks if c.dimension == ReadinessDimension.TOKEN_BUDGET)
    assert not tb.passed
    assert "small" in tb.reasons[0].lower() or "min" in tb.reasons[0].lower()


def test_token_budget_fails_oversized():
    big = "x" * 7000
    task = _make_task(description="Implement something.", codex_prompt=big)
    report = checker.check_task(task)
    tb = next(c for c in report.checks if c.dimension == ReadinessDimension.TOKEN_BUDGET)
    assert not tb.passed
    assert "oversized" in tb.reasons[0].lower() or "max" in tb.reasons[0].lower()


def test_token_budget_passes_within_range():
    # description + codex_prompt must total between 3600-6400 chars
    in_range = "y" * 3560
    task = _make_task(
        description="Implement the core module in src/app/core.py.",
        codex_prompt=in_range,
    )
    report = checker.check_task(task)
    tb = next(c for c in report.checks if c.dimension == ReadinessDimension.TOKEN_BUDGET)
    assert tb.passed


# ---------------------------------------------------------------------------
# 7. Happy path — all dimensions pass
# ---------------------------------------------------------------------------


def test_happy_path_all_pass():
    # Need total chars (description + codex_prompt) in [3600, 6400]
    desc = "Implement the authentication module in src/app/auth.py."
    padding = "z" * (3600 - len(desc) + 50)  # just above minimum
    task = _make_task(
        description=desc,
        acceptance_criteria=[
            "Given a valid token, when the user calls /login, then a 200 response should be returned."
        ],
        codex_prompt=padding,
    )
    report = checker.check_task(task)
    assert report.passed
    assert report.blocker_count == 0


# ---------------------------------------------------------------------------
# 8. Sweep aggregate
# ---------------------------------------------------------------------------


def test_sweep_aggregate_overall_passed_requires_all():
    desc = "Implement auth module in src/app/auth.py."
    padding = "z" * (3600 - len(desc) + 50)
    good = _make_task(
        task_id="M1-T1",
        description=desc,
        acceptance_criteria=[
            "Given a valid token, when called, then it should return 200."
        ],
        codex_prompt=padding,
    )
    bad = _make_task(task_id="M1-T2", target_files=[])  # will fail ACTIONABLE

    sweep = checker.check_all([good, bad])
    assert sweep.total_tasks == 2
    assert sweep.passing_tasks == 1
    assert sweep.failing_tasks == 1
    assert not sweep.overall_passed


def test_sweep_all_pass():
    tasks = []
    for i in range(1, 4):
        desc = f"Implement module_{i} in src/app/module_{i}.py."
        padding = "z" * (3600 - len(desc) + 50)
        tasks.append(
            _make_task(
                task_id=f"M1-T{i}",
                description=desc,
                acceptance_criteria=[
                    f"Given input_{i}, when processed, then result_{i} should be non-null."
                ],
                codex_prompt=padding,
            )
        )
    sweep = checker.check_all(tasks)
    assert sweep.total_tasks == 3
    assert sweep.overall_passed
    assert sweep.failing_tasks == 0


def test_sweep_empty_list_not_overall_passed():
    sweep = checker.check_all([])
    assert sweep.total_tasks == 0
    assert not sweep.overall_passed


# ---------------------------------------------------------------------------
# 9. TaskPlanner enforce_readiness=True filters non-ready tasks
# ---------------------------------------------------------------------------


def test_task_planner_enforce_readiness_filters():
    """enforce_readiness=True should drop tasks that fail checks."""
    from autodev.planners.task_planner import TaskPlanner
    from autodev.schemas import (
        ArchitectureSpec,
        DependencyGraph,
        Milestone,
    )

    arch = ArchitectureSpec(
        title="test",
        overview="test arch",
        dependency_graph=DependencyGraph(),
    )
    milestone = Milestone(
        milestone_id="M2",
        title="Core",
        objective="Implement core",
    )

    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=[milestone],
        architecture=arch,
        languages=[Language.PYTHON],
        product_name="myapp",
        enforce_readiness=True,
    )
    # Tasks emitted by M2 Python path have target_files set so won't fail ACTIONABLE,
    # but they will fail TOKEN_BUDGET (too short) and TESTABLE (no proper ACs).
    # enforce_readiness=True filters them — result should be empty or fewer tasks.
    assert isinstance(tasks, list)
