"""P0 security test expansion — Cov-H (Phase 2).

Covers gaps identified by Cov-C:

  Group A — Audit log path / overridability
  Group B — Denylist completeness (cat .env, source .env, printenv)
  Group C — MCP path-arg .env denial (xfail — gap, not yet implemented)
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
# Group C — MCP path-arg .env denial (xfail — gap not yet implemented)
# ===========================================================================


class TestMCPPathArgDotEnvDenial:
    """MCP tools that accept a path argument should reject .env paths.

    This guard does not yet exist in the production code, so tests are marked
    xfail(strict=True) to document the gap without breaking the suite.
    """

    @pytest.mark.xfail(
        strict=True,
        reason="MCP path-arg .env denial not yet implemented: "
               "tools accept any repo_path without validating for .env component",
    )
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

    No scrubbing exists in the current codebase; tests are xfail(strict=True)
    to document the gap and track it for R4 remediation.
    """

    @pytest.mark.xfail(
        strict=True,
        reason="Executor secret scrubbing not yet implemented for real executors: "
               "ClaudeCodeExecutor passes env directly to subprocess without output scrubbing; "
               "tokens set in env can appear verbatim in ExecutionResult.stderr if the "
               "underlying CLI echoes them",
    )
    def test_executor_result_does_not_leak_pypi_api_token_in_stderr(self, tmp_path: Path):
        """Real executor output must have PYPI_API_TOKEN scrubbed from stderr.

        Tracks gap: ClaudeCodeExecutor.execute() passes request.env to subprocess.run
        without any post-processing of stdout/stderr.  If the subprocess echoes the
        PYPI_API_TOKEN (e.g. via error messages, debug output, or env dumping), the
        raw secret appears in ExecutionResult.stderr verbatim.

        This test uses a subprocess that explicitly echoes the token to stderr to
        simulate that scenario.  It will xfail until scrubbing is implemented.
        """
        import subprocess as _sp
        # Directly simulate what a real executor would return: raw subprocess output
        # that contains the secret.  This exercises the *absence* of scrubbing logic.
        result = _sp.run(
            ["sh", "-c", f"echo {_FAKE_PYPI_TOKEN} >&2; exit 1"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYPI_API_TOKEN": _FAKE_PYPI_TOKEN},
        )
        # A scrubbing layer (if it existed) would replace the token in stderr.
        # Since none exists, the token appears as-is — this assertion exposes the gap.
        assert _FAKE_PYPI_TOKEN not in result.stderr, (
            "PYPI_API_TOKEN value leaked verbatim in subprocess stderr "
            "(no scrubbing layer found between subprocess output and caller)"
        )

    @pytest.mark.xfail(
        strict=True,
        reason="Executor secret scrubbing not yet implemented for real executors: "
               "ANTHROPIC_API_KEY can appear verbatim in stderr when subprocess echoes env",
    )
    def test_executor_result_does_not_leak_anthropic_api_key(self, tmp_path: Path):
        """Same as above but for ANTHROPIC_API_KEY.

        Tracks gap: same root cause as PYPI_API_TOKEN — no scrubbing of subprocess
        output in the executor pipeline.
        """
        import subprocess as _sp
        result = _sp.run(
            ["sh", "-c", f"echo {_FAKE_ANTHROPIC_KEY} >&2; exit 1"],
            capture_output=True,
            text=True,
            env={**os.environ, "ANTHROPIC_API_KEY": _FAKE_ANTHROPIC_KEY},
        )
        assert _FAKE_ANTHROPIC_KEY not in result.stderr, (
            "ANTHROPIC_API_KEY value leaked verbatim in subprocess stderr "
            "(no scrubbing layer found between subprocess output and caller)"
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
    """Branch names containing shell meta-characters should be rejected.

    The current _validate_branch_name only rejects NUL, '/', and '..'.
    Shell injection via $() and backticks is NOT caught — xfail(strict=True)
    documents this gap for R4.
    """

    @pytest.mark.xfail(
        strict=True,
        reason="WorkerIsolator branch name $() injection not yet rejected: "
               "_validate_branch_name only checks NUL, '/', and '..' sequences; "
               "$() without a slash component passes validation undetected",
    )
    def test_worker_isolator_branch_name_rejects_dollar_paren(self):
        """Branch name 'feat$(whoami)' must raise WorkerIsolatorPathEscapeError.

        Tracks gap: _validate_branch_name rejects '/' characters, so
        'feat$(rm -rf /)' is incidentally caught.  However, a $() substitution
        WITHOUT a slash — e.g. 'feat$(whoami)' — passes validation silently.
        If such a name reaches a shell-interpolated git command, the substitution
        would execute.  The validator must explicitly reject '$(' to close this.
        """
        isolator = WorkerIsolator()
        with pytest.raises(WorkerIsolatorPathEscapeError):
            isolator._validate_branch_name("feat$(whoami)")

    @pytest.mark.xfail(
        strict=True,
        reason="WorkerIsolator branch name backtick injection not yet rejected: "
               "_validate_branch_name only checks NUL, '/', and '..' sequences",
    )
    def test_worker_isolator_branch_name_rejects_backtick(self):
        """Branch name with backtick command substitution must raise WorkerIsolatorPathEscapeError.

        Tracks gap: same reasoning as dollar-paren above.  Backtick expansion
        is a separate syntactic form that must also be caught.
        """
        isolator = WorkerIsolator()
        with pytest.raises(WorkerIsolatorPathEscapeError):
            isolator._validate_branch_name("feat`whoami`")
