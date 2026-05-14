"""Tests: PRD/brief/product_name passthrough from flows into TaskDecomposer/TaskPlanner."""
from __future__ import annotations

import shutil
from pathlib import Path

from autodev.agents.system_architect import SystemArchitectAgent
from autodev.agents.task_decomposer import TaskDecomposerAgent
from autodev.schemas import (
    PRD,
    AcceptanceCriterion,
    ExecutionBackend,
    Language,
    Milestone,
    PipelineMode,
    ProductBrief,
    RepoScanResult,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def _basic_scan() -> RepoScanResult:
    return RepoScanResult(
        repo_path="/tmp",
        is_empty=False,
        is_monorepo=False,
        detected_languages=[Language.PYTHON],
        language_results={},
    )


def _sample_brief(name: str = "mdlines") -> ProductBrief:
    return ProductBrief(
        product_name=name,
        goals=["Parse markdown lines"],
        non_goals=["Full AST parsing"],
        delivery_boundary="Single Python package.",
    )


def _sample_prd(name: str = "mdlines", with_ac: bool = True) -> PRD:
    ac = []
    if with_ac:
        ac = [AcceptanceCriterion(id="AC-1", description="All lines parsed correctly", verifiable_by="test")]
    return PRD(
        product_name=name,
        overview="A tool that parses markdown lines efficiently.",
        functional_requirements=[],
        non_functional_requirements=[],
        acceptance_criteria=ac,
    )


def _milestone_set() -> list[Milestone]:
    return [
        Milestone(
            milestone_id="M1",
            title="Scaffold",
            objective="Create skeleton",
            deliverables=["pyproject.toml"],
            acceptance_criteria=["scaffold done"],
            quality_gates=["python_gate"],
            allowed_languages=[Language.PYTHON],
        ),
        Milestone(
            milestone_id="M2",
            title="Core",
            objective="Implement core",
            deliverables=["src/"],
            acceptance_criteria=["tests pass"],
            quality_gates=["python_gate"],
            allowed_languages=[Language.PYTHON],
        ),
    ]


# ---------------------------------------------------------------------------
# Test 1: With prd/product_brief/product_name, codex_prompt contains PRODUCT: header
# ---------------------------------------------------------------------------

def test_decompose_with_prd_injects_product_name_and_ac():
    """TaskDecomposerAgent.decompose with prd+brief kwargs injects PRODUCT: and ACCEPTANCE CRITERIA:."""
    arch = SystemArchitectAgent().design(
        prd=_sample_prd(), scan=_basic_scan(), languages=[Language.PYTHON]
    )
    decomposer = TaskDecomposerAgent()
    tasks = decomposer.decompose(
        milestones=_milestone_set(),
        architecture=arch,
        languages=[Language.PYTHON],
        prd=_sample_prd(name="mdlines", with_ac=True),
        product_brief=_sample_brief(name="mdlines"),
        product_name="mdlines",
    )
    assert tasks, "Expected at least one task"
    for task in tasks:
        assert "PRODUCT: mdlines" in task.codex_prompt, (
            f"Task {task.task_id} codex_prompt missing 'PRODUCT: mdlines':\n{task.codex_prompt[:300]}"
        )
    # At least one task should have ACCEPTANCE CRITERIA: (from the AC in the PRD)
    prompts_with_ac = [t for t in tasks if "ACCEPTANCE CRITERIA:" in t.codex_prompt]
    assert prompts_with_ac, "Expected at least one task with ACCEPTANCE CRITERIA: in codex_prompt"


# ---------------------------------------------------------------------------
# Test 2: Without kwargs, prompts are legacy-shaped (no PRODUCT: header)
# ---------------------------------------------------------------------------

def test_decompose_without_prd_kwargs_legacy_shape():
    """TaskDecomposerAgent.decompose without prd/brief kwargs produces legacy prompts (no PRODUCT: header)."""
    arch = SystemArchitectAgent().design(
        prd=_sample_prd(), scan=_basic_scan(), languages=[Language.PYTHON]
    )
    decomposer = TaskDecomposerAgent()
    tasks = decomposer.decompose(
        milestones=_milestone_set(),
        architecture=arch,
        languages=[Language.PYTHON],
        # No prd/product_brief/product_name
    )
    assert tasks, "Expected at least one task"
    for task in tasks:
        assert "PRODUCT:" not in task.codex_prompt, (
            f"Task {task.task_id} should NOT have PRODUCT: header in legacy mode:\n{task.codex_prompt[:300]}"
        )


# ---------------------------------------------------------------------------
# Test 3: ProjectDeliveryFlow integration — tasks contain product name from brief
# ---------------------------------------------------------------------------

def test_project_delivery_flow_tasks_contain_product_name(tmp_path):
    """ProjectDeliveryFlow propagates product_name from brief into task codex_prompts."""
    from autodev.config import FactoryConfig
    from autodev.flows.project_delivery_flow import ProjectDeliveryFlow, ProjectDeliveryInput

    # Use prd_project fixture — brief mentions "Compliance Reporting Service"
    src = FIX / "prd_project"
    repo = tmp_path / "prd_project"
    shutil.copytree(src, repo)
    brief_text = (src / "project_brief.md").read_text(encoding="utf-8")

    cfg = FactoryConfig()
    cfg.allow_mock_executor = True
    run = ProjectDeliveryFlow(cfg).run(ProjectDeliveryInput(
        repo_path=str(repo),
        brief_text=brief_text,
        languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN,
        backend=ExecutionBackend.MOCK_CODEX,
        allow_mock=True,
    ))

    tasks_path = (
        Path(run.repo_path)
        / ".dev-factory"
        / "runs"
        / run.run_id
        / "planning"
        / "tasks.json"
    )
    assert tasks_path.exists(), f"tasks.json not found at {tasks_path}"

    import json
    tasks_data = json.loads(tasks_path.read_text())
    " ".join(t.get("codex_prompt", "") for t in tasks_data)

    # The brief mentions "compliance" — product name or prompt should include it
    assert any(
        "compliance" in t.get("codex_prompt", "").lower()
        or "Compliance" in t.get("codex_prompt", "")
        or "PRODUCT:" in t.get("codex_prompt", "")
        for t in tasks_data
    ), "Expected at least one task codex_prompt to contain product context (PRODUCT: or 'compliance')"
