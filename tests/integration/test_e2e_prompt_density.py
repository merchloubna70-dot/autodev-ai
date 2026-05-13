"""Integration test: wire TaskPlanner.plan with PRD and assert prompt density.

Ensures every emitted task's codex_prompt contains the product name
when prd/product_brief/product_name are provided.
"""
from __future__ import annotations

import pytest

from autodev.planners.task_planner import TaskPlanner
from autodev.schemas import (
    AcceptanceCriterion,
    ArchitectureSpec,
    Language,
    Milestone,
    PRD,
    ProductBrief,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRODUCT_NAME = "mdlines"


def _milestones() -> list[Milestone]:
    return [
        Milestone(milestone_id="M0", title="Architecture", objective="lock architecture"),
        Milestone(milestone_id="M1", title="Scaffold", objective="scaffold project"),
        Milestone(milestone_id="M2", title="Core", objective="implement core domain"),
        Milestone(milestone_id="M3", title="Integration", objective="wire modules"),
        Milestone(milestone_id="M4", title="QA", objective="security and lint"),
        Milestone(milestone_id="M5", title="Release", objective="docs and release"),
    ]


def _arch() -> ArchitectureSpec:
    return ArchitectureSpec(
        title="mdlines architecture",
        overview="CLI tool for counting lines in Markdown files",
    )


def _sample_prd() -> PRD:
    return PRD(
        product_name=PRODUCT_NAME,
        overview="A fast CLI tool that counts lines in Markdown (.md) files.",
        functional_requirements=[],
        non_functional_requirements=[],
        acceptance_criteria=[
            AcceptanceCriterion(id="AC1", description="Line count matches wc -l", verifiable_by="test"),
            AcceptanceCriterion(id="AC2", description="Processes 10k files in <2s", verifiable_by="metric"),
        ],
    )


def _sample_brief() -> ProductBrief:
    return ProductBrief(
        product_name=PRODUCT_NAME,
        goals=["Count lines in Markdown", "Support glob patterns"],
        non_goals=["PDF support", "GUI"],
        delivery_boundary="CLI binary only",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_all_task_codex_prompts_contain_product_name():
    """Every task emitted must have product_name injected in codex_prompt."""
    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=_milestones(),
        architecture=_arch(),
        languages=[Language.PYTHON],
        prd=_sample_prd(),
        product_brief=_sample_brief(),
        product_name=PRODUCT_NAME,
    )
    assert tasks, "Expected at least one task to be produced"
    for t in tasks:
        assert PRODUCT_NAME in t.codex_prompt, (
            f"Task {t.task_id} codex_prompt missing '{PRODUCT_NAME}':\n{t.codex_prompt}"
        )


def test_all_task_claude_prompts_contain_product_name():
    """Every task emitted must have product_name injected in claude_prompt."""
    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=_milestones(),
        architecture=_arch(),
        languages=[Language.PYTHON],
        prd=_sample_prd(),
        product_brief=_sample_brief(),
        product_name=PRODUCT_NAME,
    )
    for t in tasks:
        assert PRODUCT_NAME in t.claude_prompt, (
            f"Task {t.task_id} claude_prompt missing '{PRODUCT_NAME}':\n{t.claude_prompt}"
        )


def test_all_task_prompts_have_structured_sections():
    """Prompts must have PRODUCT/OVERVIEW/YOUR TASK structure with PRD provided."""
    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=_milestones(),
        architecture=_arch(),
        languages=[Language.PYTHON],
        prd=_sample_prd(),
    )
    for t in tasks:
        assert f"PRODUCT: {PRODUCT_NAME}" in t.codex_prompt, (
            f"Task {t.task_id} missing PRODUCT section"
        )
        assert "OVERVIEW:" in t.codex_prompt, f"Task {t.task_id} missing OVERVIEW section"
        assert "YOUR TASK:" in t.codex_prompt, f"Task {t.task_id} missing YOUR TASK section"


def test_m0_collapsed_with_prd():
    """M0 emits ZERO tasks even when PRD is provided (default skip_m0_redundant_arch=True).
    The architecture artifacts have already been constructed in-flow by
    SystemArchitectAgent.design() before the implementation phase runs."""
    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=[Milestone(milestone_id="M0", title="Architecture", objective="arch")],
        architecture=_arch(),
        languages=[Language.PYTHON],
        prd=_sample_prd(),
        product_name=PRODUCT_NAME,
    )
    m0_tasks = [t for t in tasks if t.milestone_id == "M0"]
    assert m0_tasks == []


def test_backward_compat_no_kwargs():
    """Calling plan() without new kwargs still produces valid tasks (no crash)."""
    planner = TaskPlanner()
    milestones = [
        Milestone(milestone_id="M1", title="Scaffold", objective="scaffold"),
        Milestone(milestone_id="M2", title="Core", objective="core"),
    ]
    tasks = planner.plan(
        milestones=milestones,
        architecture=_arch(),
        languages=[Language.PYTHON],
    )
    assert tasks
    for t in tasks:
        assert t.task_id
        assert t.codex_prompt
        assert "[M" in t.codex_prompt
