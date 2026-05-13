"""Tests for Bug1/5/6 fixes: task prompt injection and M0 collapse.

Covers:
  (a) prompts contain product_name when context provided
  (b) prompts contain ACCEPTANCE CRITERIA section when AC list provided
  (c) empty context yields legacy-shaped prompt (graceful degradation)
  (d) skip_m0_redundant_arch=True collapses M0 to 1 verify task with type=TEST
  (e) skip_m0_redundant_arch=False preserves legacy behavior
  (f) render_task_prompt is pure and deterministic
"""
from __future__ import annotations

import pytest

from autodev.planners.task_planner import TaskPlanner
from autodev.schemas import (
    AcceptanceCriterion,
    ArchitectureSpec,
    ExecutionBackend,
    Language,
    Milestone,
    PRD,
    ProductBrief,
    TaskPromptContext,
    TaskType,
    render_task_prompt,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _basic_arch() -> ArchitectureSpec:
    return ArchitectureSpec(
        title="Test architecture",
        overview="Test overview",
    )


def _m0() -> Milestone:
    return Milestone(milestone_id="M0", title="Architecture", objective="arch")


def _m1() -> Milestone:
    return Milestone(milestone_id="M1", title="Scaffold", objective="scaffold")


def _m2() -> Milestone:
    return Milestone(milestone_id="M2", title="Core", objective="core")


def _sample_prd() -> PRD:
    return PRD(
        product_name="mdlines",
        overview="A CLI tool that counts lines in Markdown files.",
        functional_requirements=[],
        non_functional_requirements=[],
        acceptance_criteria=[
            AcceptanceCriterion(id="AC1", description="Counts lines correctly", verifiable_by="test"),
            AcceptanceCriterion(id="AC2", description="Handles empty files", verifiable_by="test"),
        ],
    )


def _sample_brief() -> ProductBrief:
    return ProductBrief(
        product_name="mdlines",
        goals=["Count lines in Markdown"],
        non_goals=["PDF support"],
        delivery_boundary="CLI only, no GUI",
    )


# ---------------------------------------------------------------------------
# (a) prompts contain product_name when context provided
# ---------------------------------------------------------------------------

def test_product_name_injected_in_codex_prompt():
    planner = TaskPlanner()
    milestones = [_m0(), _m2()]
    tasks = planner.plan(
        milestones=milestones,
        architecture=_basic_arch(),
        languages=[Language.PYTHON],
        product_name="mdlines",
    )
    # Every non-M0-collapsed task should contain product name in prompts
    for t in tasks:
        assert "mdlines" in t.codex_prompt, f"codex_prompt missing product_name: {t.task_id}"
        assert "mdlines" in t.claude_prompt, f"claude_prompt missing product_name: {t.task_id}"


def test_product_name_from_prd_injected():
    planner = TaskPlanner()
    milestones = [_m2()]
    prd = _sample_prd()
    tasks = planner.plan(
        milestones=milestones,
        architecture=_basic_arch(),
        languages=[Language.PYTHON],
        prd=prd,
    )
    for t in tasks:
        assert "mdlines" in t.codex_prompt
        assert "PRODUCT: mdlines" in t.codex_prompt


# ---------------------------------------------------------------------------
# (b) prompts contain ACCEPTANCE CRITERIA section when AC list provided
# ---------------------------------------------------------------------------

def test_acceptance_criteria_section_in_prompts():
    planner = TaskPlanner()
    milestones = [_m2()]
    prd = _sample_prd()
    tasks = planner.plan(
        milestones=milestones,
        architecture=_basic_arch(),
        languages=[Language.PYTHON],
        prd=prd,
    )
    for t in tasks:
        assert "ACCEPTANCE CRITERIA:" in t.codex_prompt
        assert "Counts lines correctly" in t.codex_prompt
        assert "Handles empty files" in t.codex_prompt


def test_overview_injected():
    planner = TaskPlanner()
    milestones = [_m2()]
    prd = _sample_prd()
    tasks = planner.plan(
        milestones=milestones,
        architecture=_basic_arch(),
        languages=[Language.PYTHON],
        prd=prd,
    )
    for t in tasks:
        assert "A CLI tool that counts lines in Markdown files." in t.codex_prompt


# ---------------------------------------------------------------------------
# (c) empty context yields legacy-shaped prompt (graceful degradation)
# ---------------------------------------------------------------------------

def test_no_context_yields_legacy_prompt_shape():
    planner = TaskPlanner()
    milestones = [_m2()]
    tasks = planner.plan(
        milestones=milestones,
        architecture=_basic_arch(),
        languages=[Language.PYTHON],
        # No prd / product_brief / product_name
    )
    for t in tasks:
        # Should still have [MX-TN] prefix
        assert t.codex_prompt.startswith("[M")
        # Should NOT contain PRODUCT: or ACCEPTANCE CRITERIA: since no context
        assert "PRODUCT:" not in t.codex_prompt
        assert "ACCEPTANCE CRITERIA:" not in t.codex_prompt
        # Should contain the task description
        assert "YOUR TASK:" in t.codex_prompt


# ---------------------------------------------------------------------------
# (d) skip_m0_redundant_arch=True collapses M0 to 1 verify task with type=TEST
# ---------------------------------------------------------------------------

def test_m0_collapsed_emits_zero_tasks():
    """With skip_m0_redundant_arch=True (default), M0 emits ZERO tasks: the
    architecture artifacts are already constructed in-flow by
    SystemArchitectAgent.design() and written before tasks run, so there is
    nothing useful for an LLM-driven task to do here. The milestone is then
    trivially complete (ImplementationResult.success=True for empty task list)."""
    planner = TaskPlanner()
    milestones = [_m0()]
    tasks = planner.plan(
        milestones=milestones,
        architecture=_basic_arch(),
        languages=[Language.PYTHON],
        skip_m0_redundant_arch=True,
    )
    m0_tasks = [t for t in tasks if t.milestone_id == "M0"]
    assert m0_tasks == []


def test_m0_collapsed_default_behavior():
    """Default (no skip_m0_redundant_arch kwarg) should also collapse M0 to zero tasks."""
    planner = TaskPlanner()
    milestones = [_m0()]
    tasks = planner.plan(
        milestones=milestones,
        architecture=_basic_arch(),
        languages=[Language.PYTHON],
    )
    m0_tasks = [t for t in tasks if t.milestone_id == "M0"]
    assert m0_tasks == []


# ---------------------------------------------------------------------------
# (e) skip_m0_redundant_arch=False preserves legacy behavior
# ---------------------------------------------------------------------------

def test_m0_legacy_when_skip_false():
    planner = TaskPlanner()
    milestones = [_m0()]
    tasks = planner.plan(
        milestones=milestones,
        architecture=_basic_arch(),
        languages=[Language.PYTHON],
        skip_m0_redundant_arch=False,
    )
    m0_tasks = [t for t in tasks if t.milestone_id == "M0"]
    assert len(m0_tasks) == 1
    t = m0_tasks[0]
    assert t.task_type == TaskType.ARCHITECTURE
    assert t.preferred_executor == ExecutionBackend.CLAUDE_CODE
    assert t.title == "Lock PRD and architecture"


# ---------------------------------------------------------------------------
# (f) render_task_prompt is pure and deterministic
# ---------------------------------------------------------------------------

def test_render_task_prompt_pure_no_context():
    result1 = render_task_prompt(
        task_id="M2-T1",
        title="Build thing",
        description="Build the thing",
        target_files=["src/thing.py"],
    )
    result2 = render_task_prompt(
        task_id="M2-T1",
        title="Build thing",
        description="Build the thing",
        target_files=["src/thing.py"],
    )
    assert result1 == result2
    assert "[M2-T1] Build thing" in result1
    assert "YOUR TASK: Build the thing" in result1
    assert "TARGET FILES:" in result1


def test_render_task_prompt_with_context_deterministic():
    ctx = TaskPromptContext(
        product_name="mdlines",
        prd_overview="Count Markdown lines",
        acceptance_criteria=["AC1 satisfied", "AC2 done"],
        delivery_boundary="CLI only",
        non_goals=["GUI"],
    )
    result1 = render_task_prompt(
        task_id="M2-T3",
        title="Implement parser",
        description="Write the line parser",
        target_files=["src/parser.py"],
        context=ctx,
    )
    result2 = render_task_prompt(
        task_id="M2-T3",
        title="Implement parser",
        description="Write the line parser",
        target_files=["src/parser.py"],
        context=ctx,
    )
    assert result1 == result2
    assert "PRODUCT: mdlines" in result1
    assert "OVERVIEW: Count Markdown lines" in result1
    assert "ACCEPTANCE CRITERIA:" in result1
    assert "  - AC1 satisfied" in result1
    assert "  - AC2 done" in result1
    assert "DELIVERY BOUNDARY: CLI only" in result1
    assert "NON-GOALS: GUI" in result1


def test_render_task_prompt_include_in_prompt_false():
    ctx = TaskPromptContext(
        product_name="suppressed",
        prd_overview="should not appear",
        include_in_prompt=False,
    )
    result = render_task_prompt(
        task_id="M1-T1",
        title="Some task",
        description="Do something",
        target_files=[],
        context=ctx,
    )
    assert "suppressed" not in result
    assert "should not appear" not in result
    assert "YOUR TASK:" in result


def test_render_task_prompt_empty_target_files():
    result = render_task_prompt(
        task_id="M3-T1",
        title="No files",
        description="No specific files",
        target_files=[],
    )
    assert "TARGET FILES:" not in result
    assert "YOUR TASK: No specific files" in result
