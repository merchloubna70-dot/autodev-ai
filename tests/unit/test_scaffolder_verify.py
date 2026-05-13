"""Unit tests for ScaffolderAgent.verify()."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from autodev.agents.scaffolder import ScaffolderAgent
from autodev.schemas import Language, PipelineMode


@pytest.fixture()
def agent() -> ScaffolderAgent:
    return ScaffolderAgent()


@pytest.fixture()
def python_plan(agent):
    return agent.plan(project_name="mylib", languages=[Language.PYTHON])


# 1) missing files detected when repo is empty
def test_verify_empty_repo_returns_all_missing(tmp_path, agent, python_plan):
    result = agent.verify(str(tmp_path), python_plan)
    assert set(result.missing_files) == set(python_plan.files_to_create)
    assert result.present_files == []
    assert result.dropped_task_ids == []
    assert result.survived_task_ids == []


# 2) present files listed when files already exist
def test_verify_present_files_listed(tmp_path, agent, python_plan):
    # pre-create some files that the plan expects
    (tmp_path / "pyproject.toml").write_text("[project]\nname='mylib'\n")
    (tmp_path / "README.md").write_text("# mylib\n")

    result = agent.verify(str(tmp_path), python_plan)
    assert "pyproject.toml" in result.present_files
    assert "README.md" in result.present_files
    # everything else should be missing
    for f in python_plan.files_to_create:
        if f not in {"pyproject.toml", "README.md"}:
            assert f in result.missing_files


# 3) idempotent apply — second apply does NOT overwrite existing files
def test_apply_idempotent_no_overwrite(tmp_path, agent, python_plan):
    # First apply (DRY_RUN — nothing actually written, but test create_only logic too)
    # Use APPLY mode on a real tmpdir to test idempotency
    agent.apply(plan=python_plan, repo_path=str(tmp_path), mode=PipelineMode.APPLY)

    # Modify pyproject.toml after first write
    pyproject = tmp_path / "pyproject.toml"
    original_content = pyproject.read_text()
    modified_marker = "# MODIFIED BY TEST\n"
    pyproject.write_text(modified_marker + original_content)

    # Second apply must not overwrite
    agent.apply(plan=python_plan, repo_path=str(tmp_path), mode=PipelineMode.APPLY)
    assert pyproject.read_text().startswith(modified_marker), (
        "Second apply must not overwrite existing pyproject.toml"
    )


# 4) verify on empty repo returns all-missing (explicit check for all plan files)
def test_verify_all_missing_on_brand_new_repo(tmp_path, agent):
    plan = agent.plan(project_name="newproject", languages=[Language.PYTHON, Language.RUST])
    result = agent.verify(str(tmp_path), plan)
    assert len(result.present_files) == 0
    assert set(result.missing_files) == set(plan.files_to_create)
