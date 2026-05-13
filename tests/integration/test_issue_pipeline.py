"""Issue Mode end-to-end smoke tests."""
from __future__ import annotations

import shutil
from pathlib import Path

from crewai_multicli_factory.config import FactoryConfig
from crewai_multicli_factory.flows.issue_pipeline_flow import IssuePipelineFlow, IssuePipelineInput
from crewai_multicli_factory.schemas import ExecutionBackend, Language, PipelineMode

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def _copy_to(tmp: Path, src: Path) -> Path:
    dst = tmp / src.name
    shutil.copytree(src, dst)
    return dst


def test_issue_mode_auto_dry_run(tmp_path):
    repo = _copy_to(tmp_path, FIX / "python_project")
    text = (FIX / "issue_project" / "issue.md").read_text(encoding="utf-8")
    cfg = FactoryConfig()
    cfg.allow_mock_executor = True
    run = IssuePipelineFlow(cfg).run(IssuePipelineInput(
        repo_path=str(repo), issue_text=text, issue_id="42",
        languages=[Language.PYTHON], mode=PipelineMode.DRY_RUN,
        backend=ExecutionBackend.AUTO, allow_mock=True,
    ))
    # Run artifacts exist
    assert (Path(run.repo_path) / ".dev-factory" / "runs" / run.run_id / "delivery" / "final_report.md").exists()
    # With FACTORY_FORCE_MOCK=1 the router falls back to mock; mock_used recorded.
    assert run.state.mock_execution_used is True


def test_issue_mode_forced_mock(tmp_path):
    repo = _copy_to(tmp_path, FIX / "python_project")
    text = (FIX / "issue_project" / "issue.md").read_text(encoding="utf-8")
    cfg = FactoryConfig()
    cfg.allow_mock_executor = True
    run = IssuePipelineFlow(cfg).run(IssuePipelineInput(
        repo_path=str(repo), issue_text=text, issue_id="42",
        languages=[Language.PYTHON], mode=PipelineMode.DRY_RUN,
        backend=ExecutionBackend.MOCK_CODEX, allow_mock=True,
    ))
    # Explicit mock_codex backend must be honored and recorded.
    assert run.state.mock_execution_used is True
