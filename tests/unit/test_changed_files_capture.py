"""Tests for Bug4: changed_files populated after execution."""
from __future__ import annotations

import os

import pytest

from autodev.config import ClaudeCodeExecutorConfig, CodexCliExecutorConfig
from autodev.executors._fs_observer import diff_repo, snapshot_repo
from autodev.executors.claude_code_executor import ClaudeCodeExecutor
from autodev.executors.codex_cli_executor import CodexCliExecutor
from autodev.schemas import ExecutionRequest, Language, PipelineMode, TaskType


def _req(repo, mode=PipelineMode.DRY_RUN, prompt="hi"):
    return ExecutionRequest(
        task_id="T1", milestone_id="M0", repo_path=str(repo), prompt=prompt,
        language=Language.PYTHON, mode=mode, task_type=TaskType.SCAFFOLD,
    )


def test_changed_files_captured_via_observer(tmp_path):
    """snapshot_repo + diff_repo finds a newly created file."""
    before = snapshot_repo(str(tmp_path))
    new_file = tmp_path / "output.py"
    new_file.write_text("x = 42")
    after = snapshot_repo(str(tmp_path))
    diff = diff_repo(before, after)
    assert any("output.py" in p for p in diff)


def test_cache_dirs_not_in_changed_files(tmp_path, monkeypatch):
    """Cache dirs (.pytest_cache etc.) are excluded from changed_files."""
    import autodev.executors._fs_observer as obs
    monkeypatch.setattr(obs, "_is_git_repo", lambda p: False)

    before = snapshot_repo(str(tmp_path))

    # Simulate executor writing a real file and pytest leaving a cache.
    (tmp_path / "result.py").write_text("pass")
    cache = tmp_path / ".pytest_cache"
    cache.mkdir()
    (cache / "junk").write_text("x")
    mypy_cache = tmp_path / ".mypy_cache"
    mypy_cache.mkdir()
    (mypy_cache / "meta.json").write_text("{}")

    after = snapshot_repo(str(tmp_path))
    diff = diff_repo(before, after)
    paths_str = " ".join(diff)
    assert ".pytest_cache" not in paths_str
    assert ".mypy_cache" not in paths_str


def test_codex_executor_execute_result_has_changed_files_attr(tmp_path):
    """ExecutionResult from CodexCliExecutor always has changed_files list."""
    # Use echo binary so it exits 0 but doesn't write files.
    cfg = CodexCliExecutorConfig(binary="echo", command_template="echo {prompt}")
    res = CodexCliExecutor(cfg).execute(_req(tmp_path))
    assert hasattr(res, "changed_files")
    assert isinstance(res.changed_files, list)


def test_claude_executor_execute_result_has_changed_files_attr(tmp_path):
    """ExecutionResult from ClaudeCodeExecutor always has changed_files list."""
    cfg = ClaudeCodeExecutorConfig(binary="echo", command_template="echo {prompt}")
    res = ClaudeCodeExecutor(cfg).execute(_req(tmp_path))
    assert hasattr(res, "changed_files")
    assert isinstance(res.changed_files, list)
