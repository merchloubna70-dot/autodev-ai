"""Project Delivery Mode end-to-end smoke tests."""
from __future__ import annotations

import shutil
from pathlib import Path

from autodev.config import FactoryConfig
from autodev.flows.project_delivery_flow import (
    ProjectDeliveryFlow,
    ProjectDeliveryInput,
)
from autodev.schemas import ExecutionBackend, Language, PipelineMode, ReleaseDecision

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def _copy_to(tmp: Path, src: Path) -> Path:
    dst = tmp / src.name
    shutil.copytree(src, dst)
    return dst


def test_delivery_from_brief_to_empty_repo(tmp_path):
    repo = _copy_to(tmp_path, FIX / "empty_project")
    brief_text = (FIX / "prd_project" / "project_brief.md").read_text(encoding="utf-8")
    cfg = FactoryConfig()
    cfg.allow_mock_executor = True
    run = ProjectDeliveryFlow(cfg).run(ProjectDeliveryInput(
        repo_path=str(repo), brief_text=brief_text,
        project_name="compliance-reporting", languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN, backend=ExecutionBackend.AUTO,
        allow_mock=True, from_scratch=True,
    ))
    run_dir = Path(run.repo_path) / ".dev-factory" / "runs" / run.run_id
    assert (run_dir / "product" / "prd.md").exists()
    assert (run_dir / "architecture" / "architecture.md").exists()
    assert (run_dir / "planning" / "milestones.json").exists()
    assert (run_dir / "planning" / "tasks.json").exists()
    assert (run_dir / "delivery" / "delivery_report.md").exists()
    assert (run_dir / "delivery" / "final_report.md").exists()
    # Dry-run + mock means cannot be release ready
    assert run.state.release_check is not None
    assert run.state.release_check.decision != ReleaseDecision.RELEASE_READY


def test_delivery_mixed_project(tmp_path):
    repo = _copy_to(tmp_path, FIX / "mixed_project")
    brief_text = (FIX / "prd_project" / "project_brief.md").read_text(encoding="utf-8")
    cfg = FactoryConfig()
    cfg.allow_mock_executor = True
    run = ProjectDeliveryFlow(cfg).run(ProjectDeliveryInput(
        repo_path=str(repo), brief_text=brief_text,
        project_name="mixed", languages=[Language.PYTHON, Language.RUST, Language.TYPESCRIPT],
        mode=PipelineMode.DRY_RUN, backend=ExecutionBackend.AUTO, allow_mock=True,
    ))
    # cross-language path executed via mock backends
    assert run.state.mock_execution_used is True


def test_continue_and_report_flag_does_not_explode(tmp_path):
    repo = _copy_to(tmp_path, FIX / "empty_project")
    brief_text = (FIX / "prd_project" / "project_brief.md").read_text(encoding="utf-8")
    cfg = FactoryConfig()
    cfg.allow_mock_executor = True
    cfg.continue_and_report = True
    cfg.fail_fast = False
    run = ProjectDeliveryFlow(cfg).run(ProjectDeliveryInput(
        repo_path=str(repo), brief_text=brief_text,
        project_name="x", languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN, allow_mock=True, from_scratch=True,
    ))
    assert run.state.release_check is not None
