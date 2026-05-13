"""Tests for MockFixtureConfig-driven mock executors."""
from __future__ import annotations

from pathlib import Path

from crewai_multicli_factory.config import MockFixtureConfig
from crewai_multicli_factory.executors.mock_codex_executor import MockCodexExecutor
from crewai_multicli_factory.schemas import (
    ExecutionRequest,
    Language,
    PipelineMode,
    TaskType,
)


def _feature_request(repo_path: str) -> ExecutionRequest:
    return ExecutionRequest(
        task_id="T1",
        milestone_id="M0",
        repo_path=repo_path,
        prompt="implement the feature",
        language=Language.PYTHON,
        mode=PipelineMode.DRY_RUN,
        task_type=TaskType.FEATURE,
    )


def test_fixture_config_renders_template(tmp_path):
    """When patches_dir has feature.txt, content is rendered from the template."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    template = "task={task_id}|m={milestone_id}|t={task_type}|lang={language}"
    (patches_dir / "feature.txt").write_text(template, encoding="utf-8")

    cfg = MockFixtureConfig(enabled=True, patches_dir=str(patches_dir))
    executor = MockCodexExecutor(fixture_config=cfg)
    result = executor.execute(_feature_request(str(tmp_path)))

    assert result.success
    # changed_files must contain the codex mock output path
    assert any("codex_T1_" in f for f in result.changed_files), (
        f"Expected codex_T1_* in changed_files, got {result.changed_files}"
    )
    # The patch content must contain the rendered template
    assert "task=T1|m=M0|t=feature|lang=python" in result.patch, (
        f"Rendered template not found in patch:\n{result.patch}"
    )


def test_no_fixture_config_uses_legacy_format(tmp_path):
    """Without fixture_config, legacy format is used (contains prompt_sha= and task_id=T1)."""
    executor = MockCodexExecutor()
    result = executor.execute(_feature_request(str(tmp_path)))

    assert result.success
    assert "prompt_sha=" in result.patch
    assert "task_id=T1" in result.patch


def test_fixture_config_missing_template_falls_back(tmp_path):
    """When patches_dir exists but feature.txt is absent, legacy format is used."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    # No feature.txt created

    cfg = MockFixtureConfig(enabled=True, patches_dir=str(patches_dir))
    executor = MockCodexExecutor(fixture_config=cfg)
    result = executor.execute(_feature_request(str(tmp_path)))

    assert result.success
    # Falls back to legacy format
    assert "prompt_sha=" in result.patch


def test_fixture_config_determinism(tmp_path):
    """Same inputs always produce the same patch content."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    (patches_dir / "feature.txt").write_text(
        "task={task_id}|m={milestone_id}|t={task_type}|lang={language}", encoding="utf-8"
    )
    cfg = MockFixtureConfig(enabled=True, patches_dir=str(patches_dir))

    r1 = MockCodexExecutor(fixture_config=cfg).execute(_feature_request(str(tmp_path)))
    r2 = MockCodexExecutor(fixture_config=cfg).execute(_feature_request(str(tmp_path)))
    assert r1.patch == r2.patch
