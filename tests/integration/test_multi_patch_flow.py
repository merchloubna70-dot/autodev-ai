"""Integration tests for MultiPatchFlow (W7)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from crewai_multicli_factory.config import FactoryConfig
from crewai_multicli_factory.flows.multi_patch_flow import MultiPatchFlow, MultiPatchInput
from crewai_multicli_factory.schemas import Language, PipelineMode

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def _make_repo(tmp_path: Path) -> Path:
    src = FIX / "python_project"
    dst = tmp_path / "python_project"
    shutil.copytree(src, dst)
    return dst


def _cfg(allow_mock: bool = True) -> FactoryConfig:
    cfg = FactoryConfig()
    cfg.allow_mock_executor = allow_mock
    return cfg


def test_multi_patch_creates_candidate_files(tmp_path):
    """multi_patch/ dir must contain N candidate JSON files."""
    repo = _make_repo(tmp_path)
    n = 3
    cfg = _cfg()
    run = MultiPatchFlow(cfg).run(MultiPatchInput(
        bug_description="NullPointerError in process()",
        repo_path=str(repo),
        n_candidates=n,
        languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    ))

    multi_patch_dir = Path(run.repo_path) / ".dev-factory" / "runs" / run.run_id / "multi_patch"
    assert multi_patch_dir.exists(), "multi_patch/ directory must be created"

    candidate_files = sorted(multi_patch_dir.glob("candidate-*.json"))
    assert len(candidate_files) == n, f"Expected {n} candidate files, got {len(candidate_files)}"

    # Each file should be valid JSON with correct structure
    for f in candidate_files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "candidate_id" in data
        assert "seed" in data
        assert "test_pass_count" in data


def test_multi_patch_creates_vote_json(tmp_path):
    """multi_patch/vote.json must exist and name a winner."""
    repo = _make_repo(tmp_path)
    cfg = _cfg()
    run = MultiPatchFlow(cfg).run(MultiPatchInput(
        bug_description="IndexError in list accessor",
        repo_path=str(repo),
        n_candidates=2,
        languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    ))

    vote_file = Path(run.repo_path) / ".dev-factory" / "runs" / run.run_id / "multi_patch" / "vote.json"
    assert vote_file.exists(), "vote.json must be created"

    data = json.loads(vote_file.read_text(encoding="utf-8"))
    assert "candidates" in data
    assert "winner_candidate_id" in data
    assert len(data["candidates"]) == 2


def test_multi_patch_summary_json_written(tmp_path):
    """multi_patch/summary.json must be written to the run dir."""
    repo = _make_repo(tmp_path)
    cfg = _cfg()
    run = MultiPatchFlow(cfg).run(MultiPatchInput(
        bug_description="KeyError in dict lookup",
        repo_path=str(repo),
        n_candidates=2,
        languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    ))

    summary_file = Path(run.repo_path) / ".dev-factory" / "runs" / run.run_id / "multi_patch" / "summary.json"
    assert summary_file.exists(), "summary.json must be created"
