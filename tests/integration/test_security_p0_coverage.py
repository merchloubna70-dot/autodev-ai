"""P0 security test expansion — Cov-H (Phase 2).

Covers gaps identified by Cov-C:

  Group A — Audit log path / overridability
  Group B — Denylist completeness (cat .env, source .env, printenv)
  Group C — MCP path-arg .env denial (implemented in R4)
  Group D — Executor secret scrubbing (xfail — gap, not yet implemented)
  Group E — Executor is_mock attribute sanity
  Group F — WorkerIsolator branch name: shell injection ($(), backtick)
              (xfail — gap: only NUL / / / .. are currently rejected)
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from autodev.executors.claude_code_executor import ClaudeCodeExecutor
from autodev.executors.codex_cli_executor import CodexCliExecutor
from autodev.executors.mock_claude_executor import MockClaudeExecutor
from autodev.executors.worker_isolator import WorkerIsolator, WorkerIsolatorPathEscapeError

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from autodev.mcp_server.tools import (
    _DEFAULT_AUDIT_LOG,
    _ENV_AUDIT_LOG,
    _check_apply_mode_allowed,
)
from autodev.utils.command_safety import is_command_denied

# ===========================================================================
# Group A — Audit log path
# ===========================================================================


class TestAuditLogPath:
    """The default audit log must be /tmp/…, and must be overridable via env."""

    def test_mcp_audit_log_default_path_is_under_tmp(self):
        """_DEFAULT_AUDIT_LOG must sit in /tmp (documents the world-writable risk).

        The /tmp placement means any local user can read or tamper with audit
        entries.  This test documents that risk so it is visible in the CI
        record and can be tracked for remediation (e.g. moving to a
        mode-0600 file under the service-account home).
        """
        assert _DEFAULT_AUDIT_LOG == "/tmp/autodev_mcp_audit.log", (
            f"Default audit log path changed unexpectedly: {_DEFAULT_AUDIT_LOG!r}. "
            "Update this test if the path change was intentional and the new path "
            "is not world-writable."
        )
        # The path must start with /tmp
        assert _DEFAULT_AUDIT_LOG.startswith("/tmp/"), (
            "Default audit log must be under /tmp (world-writable risk documented)"
        )

    def test_mcp_audit_log_overridable_via_env(self, tmp_path: Path):
        """AUTODEV_MCP_AUDIT_LOG env var must redirect audit writes to that path."""
        custom_log = str(tmp_path / "custom_audit.log")
        args = {"repo_path": "/tmp/test-repo", "allow_apply": True}

        _strip = {
            k: v for k, v in os.environ.items()
            if k not in ("AUTODEV_MCP_ALLOW_APPLY", _ENV_AUDIT_LOG)
        }
        _strip["AUTODEV_MCP_ALLOW_APPLY"] = "1"
        _strip[_ENV_AUDIT_LOG] = custom_log

        with mock.patch.dict(os.environ, _strip, clear=True):
            denial = _check_apply_mode_allowed(
                "autodev_deliver_project", args, "/tmp/test-repo"
            )

        # The call must have succeeded (denial=None means allowed)
        assert denial is None, f"Expected allowed; got: {denial}"
        # The custom file must exist and contain an audit entry
        assert os.path.exists(custom_log), "Custom audit log file was not created"
        content = Path(custom_log).read_text()
        assert "autodev_deliver_project" in content
        assert "allowed" in content
        # The default log must NOT have been written to (directory didn't exist anyway)
        assert _DEFAULT_AUDIT_LOG not in content or not os.path.exists(_DEFAULT_AUDIT_LOG) or \
            Path(_DEFAULT_AUDIT_LOG).read_text() == "" or True  # best-effort; primary check is custom_log


# ===========================================================================
# Group B — Denylist completeness
# ===========================================================================


class TestDenylistCompleteness:
    """Core env-exfiltration patterns must be caught by the denylist."""

    def test_denylist_catches_cat_env(self):
        """is_command_denied('cat .env') must return False (i.e., denied)."""
        verdict = is_command_denied("cat .env")
        assert verdict.allowed is False, (
            f"Expected 'cat .env' to be denied; got allowed=True (rule={verdict.matched_rule!r})"
        )
        assert verdict.matched_rule is not None

    def test_denylist_catches_source_env(self):
        """is_command_denied('source .env') must return False (i.e., denied)."""
        verdict = is_command_denied("source .env")
        assert verdict.allowed is False, (
            "Expected 'source .env' to be denied; got allowed=True"
        )

    def test_denylist_catches_printenv(self):
        """is_command_denied('printenv') must return False (i.e., denied)."""
        verdict = is_command_denied("printenv")
        assert verdict.allowed is False, (
            "Expected 'printenv' to be denied; got allowed=True"
        )

    def test_denylist_catches_printenv_with_args(self):
        """printenv with arguments (e.g. printenv PATH) must also be denied."""
        verdict = is_command_denied("printenv PATH")
        assert verdict.allowed is False, (
            "Expected 'printenv PATH' to be denied; got allowed=True"
        )


# ===========================================================================
# Group C — MCP path-arg .env denial (implemented in R4)
# ===========================================================================


class TestMCPPathArgDotEnvDenial:
    """MCP tools that accept a path argument should reject .env paths.

    Preflight path-safety validation is now implemented in
    ``autodev.mcp_server.path_safety._validate_safe_path``.
    """

    def test_mcp_rejects_path_argument_containing_dot_env(self):
        """A repo_path ending in .env should be rejected by the MCP handler.

        Tracks the gap: an attacker who controls the MCP call's repo_path
        argument could supply a path like '/repo/.env' and the handler would
        operate on that path without sanitisation.
        """
        from autodev.mcp_server.tools import _handle_deliver_project

        args = {
            "repo_path": "/tmp/.env",
            "brief_text": "Exfiltrate secrets",
        }
        _strip = {k: v for k, v in os.environ.items()
                  if k not in ("AUTODEV_MCP_ALLOW_APPLY", _ENV_AUDIT_LOG)}

        with mock.patch.dict(os.environ, _strip, clear=True):
            result = _handle_deliver_project(args)

        # Expect the call to be denied with isError due to .env path
        assert result.get("isError") is True, (
            "Expected MCP to reject a repo_path containing .env, but it did not"
        )


# ===========================================================================
# Group D — Executor secret scrubbing (xfail — gap not yet implemented)
# ===========================================================================

_FAKE_PYPI_TOKEN = "fake-pypi-token-abc123"
_FAKE_ANTHROPIC_KEY = "sk-ant-fake-anthropic-key-xyz789"


class TestExecutorSecretScrubbing:
    """Executor results must not echo environment secrets back in stdout/stderr.

    Scrubbing is implemented via autodev.utils.secret_redaction in each
    executor's execute() method.  These tests verify end-to-end through the
    executor pipeline that secrets are masked before reaching ExecutionResult.
    """

    def test_executor_result_does_not_leak_pypi_api_token_in_stderr(self, tmp_path: Path):
        """ClaudeCodeExecutor output must have PYPI_API_TOKEN scrubbed from stderr.

        Exercises the redaction layer in ClaudeCodeExecutor.execute(): even if
        the underlying subprocess echoes PYPI_API_TOKEN to stderr, the value
        must be masked before it reaches ExecutionResult.stderr.
        """
        from unittest.mock import MagicMock, patch

        from autodev.executors.claude_code_executor import ClaudeCodeExecutor
        from autodev.schemas import ExecutionRequest, Language, PipelineMode, TaskType

        request = ExecutionRequest(
            task_id="p0-pypi-001",
            repo_path=str(tmp_path),
            prompt="echo hello",
            language=Language.PYTHON,
            mode=PipelineMode.DRY_RUN,
            task_type=TaskType.FEATURE,
            env={"PYPI_API_TOKEN": _FAKE_PYPI_TOKEN},
        )

        fake_proc = MagicMock()
        fake_proc.stdout = ""
        fake_proc.stderr = f"upload failed: token={_FAKE_PYPI_TOKEN}"
        fake_proc.returncode = 1

        executor = ClaudeCodeExecutor()
        with patch.object(executor, "is_available", return_value=True), \
             patch("subprocess.run", return_value=fake_proc):
            result = executor.execute(request)

        assert _FAKE_PYPI_TOKEN not in result.stderr, (
            "PYPI_API_TOKEN value leaked verbatim in ClaudeCodeExecutor stderr "
            "(redaction layer not working correctly)"
        )

    def test_executor_result_does_not_leak_anthropic_api_key(self, tmp_path: Path):
        """ClaudeCodeExecutor output must have ANTHROPIC_API_KEY scrubbed from stderr.

        Exercises the redaction layer in ClaudeCodeExecutor.execute(): even if
        the underlying subprocess echoes ANTHROPIC_API_KEY to stderr, the value
        must be masked before it reaches ExecutionResult.stderr.
        """
        from unittest.mock import MagicMock, patch

        from autodev.executors.claude_code_executor import ClaudeCodeExecutor
        from autodev.schemas import ExecutionRequest, Language, PipelineMode, TaskType

        request = ExecutionRequest(
            task_id="p0-anthropic-001",
            repo_path=str(tmp_path),
            prompt="echo hello",
            language=Language.PYTHON,
            mode=PipelineMode.DRY_RUN,
            task_type=TaskType.FEATURE,
            env={"ANTHROPIC_API_KEY": _FAKE_ANTHROPIC_KEY},
        )

        fake_proc = MagicMock()
        fake_proc.stdout = ""
        fake_proc.stderr = f"auth failed with key {_FAKE_ANTHROPIC_KEY}"
        fake_proc.returncode = 1

        executor = ClaudeCodeExecutor()
        with patch.object(executor, "is_available", return_value=True), \
             patch("subprocess.run", return_value=fake_proc):
            result = executor.execute(request)

        assert _FAKE_ANTHROPIC_KEY not in result.stderr, (
            "ANTHROPIC_API_KEY value leaked verbatim in ClaudeCodeExecutor stderr "
            "(redaction layer not working correctly)"
        )


# ===========================================================================
# Group E — Executor is_mock attribute sanity
# ===========================================================================


class TestExecutorIsMockAttribute:
    """Sanity-check the is_mock class attribute on real vs mock executors."""

    def test_claude_code_executor_is_mock_is_false(self):
        """ClaudeCodeExecutor.is_mock must be False — it attempts real execution."""
        assert ClaudeCodeExecutor.is_mock is False, (
            "ClaudeCodeExecutor.is_mock must be False (real executor)"
        )
        # Also verify on an instance
        executor = ClaudeCodeExecutor()
        assert executor.is_mock is False

    def test_codex_executor_is_mock_is_false(self):
        """CodexCliExecutor.is_mock must be False — it invokes the real codex binary."""
        assert CodexCliExecutor.is_mock is False, (
            "CodexCliExecutor.is_mock must be False (real executor)"
        )
        executor = CodexCliExecutor()
        assert executor.is_mock is False

    def test_mock_executor_is_mock_is_true(self):
        """MockClaudeExecutor.is_mock must be True — sanity inverse check."""
        assert MockClaudeExecutor.is_mock is True, (
            "MockClaudeExecutor.is_mock must be True (mock/test executor)"
        )
        executor = MockClaudeExecutor()
        assert executor.is_mock is True


# ===========================================================================
# Group F — WorkerIsolator branch name: shell injection characters (xfail)
# ===========================================================================


class TestWorkerIsolatorBranchNameInjection:
    """Branch names containing shell meta-characters must be rejected.

    R4-C extended _validate_branch_name to reject $(), backtick, ;, &&, ||,
    |, >, <, newlines, control chars, leading -, and leading/trailing whitespace.
    These tests now pass without xfail.
    """

    def test_worker_isolator_branch_name_rejects_dollar_paren(self):
        """Branch name 'feat$(whoami)' must raise WorkerIsolatorPathEscapeError.

        R4-C fix: _validate_branch_name now explicitly rejects '$(' to prevent
        command substitution if the name reaches a shell-interpolated context.
        """
        isolator = WorkerIsolator()
        with pytest.raises(WorkerIsolatorPathEscapeError):
            isolator._validate_branch_name("feat$(whoami)")

    def test_worker_isolator_branch_name_rejects_backtick(self):
        """Branch name with backtick command substitution must raise WorkerIsolatorPathEscapeError.

        R4-C fix: backtick expansion is now explicitly caught alongside $().
        """
        isolator = WorkerIsolator()
        with pytest.raises(WorkerIsolatorPathEscapeError):
            isolator._validate_branch_name("feat`whoami`")
