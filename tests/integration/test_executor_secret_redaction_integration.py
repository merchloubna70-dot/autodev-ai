"""Integration tests: executor outputs must not leak secrets.

Verifies that the secret redaction layer in each executor strips
injected credentials from stdout/stderr before they reach the caller.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from autodev.executors.claude_code_executor import ClaudeCodeExecutor
from autodev.executors.codex_cli_executor import CodexCliExecutor
from autodev.executors.mock_claude_executor import MockClaudeExecutor
from autodev.schemas import ExecutionBackend, ExecutionRequest, Language, PipelineMode, TaskType

_REDACTED = "***REDACTED***"


def _make_request(tmp_path: Path, **kwargs) -> ExecutionRequest:
    """Build a minimal ExecutionRequest rooted at *tmp_path*."""
    defaults = {
        "task_id": "test-redact-001",
        "repo_path": str(tmp_path),
        "prompt": "echo hello",
        "language": Language.PYTHON,
        "mode": PipelineMode.DRY_RUN,
        "task_type": TaskType.FEATURE,
    }
    defaults.update(kwargs)
    return ExecutionRequest(**defaults)


# ===========================================================================
# Test 1 — Codex executor does not leak OPENAI_API_KEY in stderr
# ===========================================================================

class TestCodexExecutorSecretRedaction:
    def test_codex_executor_does_not_leak_openai_key_in_stderr(self, tmp_path: Path):
        """Codex executor output must have OPENAI_API_KEY value scrubbed from stderr."""
        fake_token = "sk-fake-openai-key-abcdefghijklmnopqrst"

        request = _make_request(
            tmp_path,
            env={"OPENAI_API_KEY": fake_token},
        )

        fake_proc = mock.MagicMock()
        fake_proc.stdout = ""
        fake_proc.stderr = f"Error: invalid key {fake_token}"
        fake_proc.returncode = 1

        executor = CodexCliExecutor()
        with mock.patch.object(executor, "is_available", return_value=True), \
             mock.patch("subprocess.run", return_value=fake_proc):
            result = executor.execute(request)

        assert fake_token not in result.stderr, (
            f"OPENAI_API_KEY value leaked in CodexCliExecutor stderr: {result.stderr!r}"
        )
        assert _REDACTED in result.stderr


# ===========================================================================
# Test 2 — Claude executor does not leak ANTHROPIC_API_KEY in stderr
# ===========================================================================

class TestClaudeExecutorSecretRedaction:
    def test_claude_executor_does_not_leak_anthropic_key_in_stderr(self, tmp_path: Path):
        """ClaudeCodeExecutor output must have ANTHROPIC_API_KEY value scrubbed from stderr."""
        fake_key = "sk-ant-fake-anthropic-key-xyz789abcdefghijklm"

        request = _make_request(
            tmp_path,
            env={"ANTHROPIC_API_KEY": fake_key},
        )

        fake_proc = mock.MagicMock()
        fake_proc.stdout = ""
        fake_proc.stderr = f"Auth failed with ANTHROPIC_API_KEY={fake_key}"
        fake_proc.returncode = 1

        executor = ClaudeCodeExecutor()
        with mock.patch.object(executor, "is_available", return_value=True), \
             mock.patch("subprocess.run", return_value=fake_proc):
            result = executor.execute(request)

        assert fake_key not in result.stderr, (
            f"ANTHROPIC_API_KEY value leaked in ClaudeCodeExecutor stderr: {result.stderr!r}"
        )
        assert _REDACTED in result.stderr

    def test_claude_executor_does_not_leak_key_in_stdout(self, tmp_path: Path):
        """ClaudeCodeExecutor stdout must also be scrubbed."""
        fake_key = "sk-ant-api03-fakekey-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"

        request = _make_request(
            tmp_path,
            env={"ANTHROPIC_API_KEY": fake_key},
        )

        fake_proc = mock.MagicMock()
        fake_proc.stdout = f"Running with key {fake_key} ... done"
        fake_proc.stderr = ""
        fake_proc.returncode = 0

        executor = ClaudeCodeExecutor()
        with mock.patch.object(executor, "is_available", return_value=True), \
             mock.patch("subprocess.run", return_value=fake_proc):
            result = executor.execute(request)

        assert fake_key not in result.stdout, (
            f"ANTHROPIC_API_KEY value leaked in ClaudeCodeExecutor stdout: {result.stdout!r}"
        )
        assert _REDACTED in result.stdout


# ===========================================================================
# Test 3 — Mock executor: simulate stderr containing an sk- token
# ===========================================================================

class TestMockExecutorSecretRedaction:
    def test_mock_executor_output_does_not_contain_injected_sk_token(self, tmp_path: Path):
        """MockClaudeExecutor stdout/stderr must be passed through redact_secrets.

        The mock generates its own output, but we verify that if the redaction
        helper is applied, no raw sk- token leaks out.
        """
        from autodev.utils.secret_redaction import redact_secrets

        # Simulate raw output containing a secret (as if it came from
        # a real mock that somehow picked up an injected env value)
        raw_stderr = "sk-fake-abc123def456GHIJKLMNOPQRSTUVWX"
        redacted = redact_secrets(raw_stderr)

        assert raw_stderr not in redacted
        assert _REDACTED in redacted
        assert "sk-f" in redacted  # first 4 chars preserved

    def test_mock_claude_executor_run_produces_no_raw_token(self, tmp_path: Path):
        """MockClaudeExecutor.execute() stdout/stderr must not contain raw secret tokens."""
        request = _make_request(
            tmp_path,
            env={"ANTHROPIC_API_KEY": "sk-ant-fake-key-mocktestABCDEFGHIJKLMNOP"},
        )

        executor = MockClaudeExecutor()
        result = executor.execute(request)

        # Mock executor produces deterministic safe output — verify no raw tokens
        assert "sk-ant-fake-key-mocktestABCDEFGHIJKLMNOP" not in (result.stdout or "")
        assert "sk-ant-fake-key-mocktestABCDEFGHIJKLMNOP" not in (result.stderr or "")


# ===========================================================================
# Test 4 — Selection log JSON: reason field does not leak env secrets
# ===========================================================================

class TestSelectionLogSecretRedaction:
    def test_router_decision_json_does_not_contain_env_secrets(self, tmp_path: Path):
        """executor_selection_*.json reason must not contain injected secret values.

        The RouterDecision.to_json() is derived from task_type/risk/language — not
        from env — so it should be clean by construction.  This test documents
        and verifies that invariant.
        """
        from autodev.executors.executor_router import ExecutorRouter

        fake_token = "sk-ant-fake-selection-log-ABCDEFGHIJKLM"
        request = _make_request(
            tmp_path,
            env={"ANTHROPIC_API_KEY": fake_token},
            backend=ExecutionBackend.MOCK_CLAUDE,
        )

        router = ExecutorRouter(allow_mock=True)
        decision = router.decide(request)
        selection_json = json.dumps(decision.to_json())

        assert fake_token not in selection_json, (
            f"Secret token leaked into selection log JSON: {selection_json!r}"
        )

    def test_redacted_stderr_does_not_appear_in_json_report(self, tmp_path: Path):
        """An ExecutionResult with redacted stderr serialises without raw secrets."""
        from autodev.schemas import ExecutionResult
        from autodev.utils.secret_redaction import redact_secrets

        fake_token = "sk-ant-api03-fakereport-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        raw_stderr = f"Error: token={fake_token}"

        result = ExecutionResult(
            task_id="t-log-001",
            backend=ExecutionBackend.MOCK_CLAUDE,
            language=Language.PYTHON,
            command="<mock>",
            exit_code=1,
            stdout="",
            stderr=redact_secrets(raw_stderr),
            success=False,
        )

        serialised = json.dumps(result.model_dump(mode="json"))
        assert fake_token not in serialised, (
            f"Raw secret leaked in serialised ExecutionResult JSON: {serialised!r}"
        )
        assert _REDACTED in serialised
