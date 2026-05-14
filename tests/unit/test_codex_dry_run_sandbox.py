"""Tests for Bug2: --sandbox flag injected based on PipelineMode."""
from __future__ import annotations

from autodev.config import CodexCliExecutorConfig
from autodev.executors.codex_cli_executor import CodexCliExecutor, _sandbox_args_for
from autodev.schemas import ExecutionRequest, Language, PipelineMode, TaskType


def _req(repo, mode, prompt="hi"):
    return ExecutionRequest(
        task_id="T1", milestone_id="M0", repo_path=str(repo), prompt=prompt,
        language=Language.PYTHON, mode=mode, task_type=TaskType.SCAFFOLD,
    )


# --- unit tests for _sandbox_args_for ---

def test_sandbox_args_dry_run():
    args = _sandbox_args_for(PipelineMode.DRY_RUN)
    assert args == ["--sandbox", "read-only"]


def test_sandbox_args_apply():
    args = _sandbox_args_for(PipelineMode.APPLY)
    assert args == ["--sandbox", "workspace-write"]


# --- integration: _build_command injects sandbox into argv ---

def test_build_command_dry_run_contains_read_only(tmp_path):
    cfg = CodexCliExecutorConfig(
        binary="echo",
        command_template="echo {prompt}",
    )
    ex = CodexCliExecutor(cfg)
    req = _req(tmp_path, PipelineMode.DRY_RUN)
    prompt = ex._render_prompt(req)
    cmd_str, _argv = ex._build_command(req, prompt)
    assert "--sandbox" in cmd_str
    assert "read-only" in cmd_str


def test_build_command_apply_contains_workspace_write(tmp_path):
    cfg = CodexCliExecutorConfig(
        binary="echo",
        command_template="echo {prompt}",
    )
    ex = CodexCliExecutor(cfg)
    req = _req(tmp_path, PipelineMode.APPLY)
    prompt = ex._render_prompt(req)
    cmd_str, _argv = ex._build_command(req, prompt)
    assert "--sandbox" in cmd_str
    assert "workspace-write" in cmd_str


def test_build_command_no_duplicate_sandbox_when_template_has_it(tmp_path):
    """If command_template already has --sandbox, we don't add it again."""
    cfg = CodexCliExecutorConfig(
        binary="echo",
        command_template="codex exec --sandbox read-only {prompt}",
    )
    ex = CodexCliExecutor(cfg)
    req = _req(tmp_path, PipelineMode.DRY_RUN)
    prompt = ex._render_prompt(req)
    cmd_str, _argv = ex._build_command(req, prompt)
    # Should appear exactly once (the one already in the template).
    assert cmd_str.count("--sandbox") == 1


def test_existing_executor_template_test_still_passes(tmp_path):
    """Pre-existing test: template with echo binary doesn't crash."""
    cfg = CodexCliExecutorConfig(binary="echo", command_template="echo prompt={prompt}")
    res = CodexCliExecutor(cfg).execute(_req(tmp_path, PipelineMode.DRY_RUN, prompt="hi world"))
    assert "echo prompt=" in res.command
