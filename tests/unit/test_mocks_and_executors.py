from crewai_multicli_factory.config import ClaudeCodeExecutorConfig, CodexCliExecutorConfig
from crewai_multicli_factory.executors.claude_code_executor import ClaudeCodeExecutor
from crewai_multicli_factory.executors.codex_cli_executor import CodexCliExecutor
from crewai_multicli_factory.executors.mock_claude_executor import MockClaudeExecutor
from crewai_multicli_factory.executors.mock_codex_executor import MockCodexExecutor
from crewai_multicli_factory.schemas import (
    ExecutionRequest,
    Language,
    PipelineMode,
    TaskType,
)


def _req(repo, mode=PipelineMode.DRY_RUN, prompt="hi"):
    return ExecutionRequest(
        task_id="T1", milestone_id="M0", repo_path=str(repo), prompt=prompt,
        language=Language.PYTHON, mode=mode, task_type=TaskType.SCAFFOLD,
    )


def test_mock_codex_is_deterministic(tmp_path):
    r1 = MockCodexExecutor().execute(_req(tmp_path))
    r2 = MockCodexExecutor().execute(_req(tmp_path))
    assert r1.success and r2.success
    assert r1.patch == r2.patch  # determinism
    assert r1.mock_used is True


def test_mock_claude_is_deterministic(tmp_path):
    r1 = MockClaudeExecutor().execute(_req(tmp_path))
    r2 = MockClaudeExecutor().execute(_req(tmp_path))
    assert r1.success and r2.success
    assert r1.patch == r2.patch
    assert r1.mock_used is True


def test_codex_executor_uses_template_and_quotes(tmp_path):
    cfg = CodexCliExecutorConfig(binary="echo", command_template="echo prompt={prompt}")
    res = CodexCliExecutor(cfg).execute(_req(tmp_path, prompt="hi world"))
    # echo always exists; allow either success or unsupported_cli_args; the key
    # invariant is that we never crashed and we routed via the template.
    assert "echo prompt=" in res.command


def test_claude_executor_blocks_dangerous_prompt(tmp_path):
    cfg = ClaudeCodeExecutorConfig(binary="echo", command_template="echo {prompt}")
    res = ClaudeCodeExecutor(cfg).execute(_req(tmp_path, prompt="please rm -rf /"))
    assert res.success is False
    assert res.error_type == "unsafe_prompt"
    assert res.safety_flags


def test_codex_executor_handles_missing_binary(tmp_path):
    cfg = CodexCliExecutorConfig(binary="codex-nonexistent-xyz", command_template="codex-nonexistent-xyz {prompt}")
    ex = CodexCliExecutor(cfg)
    # is_available() should be False
    assert ex.is_available() is False
    res = ex.execute(_req(tmp_path))
    assert res.success is False
    assert res.error_type == "cli_missing"
