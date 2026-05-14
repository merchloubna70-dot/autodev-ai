"""MCP apply-mode guardrail integration tests.

Tests the server-side security controls that prevent arbitrary code execution
via mode='apply' in autodev_deliver_project and autodev_run_issue.

Strategy: call handler functions directly (no subprocess) so the tests are
fast and isolated from LLM/subprocess dependencies. The handlers are pure
Python functions that perform guardrail checks before touching any flow code.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest import mock

# ---------------------------------------------------------------------------
# Import the handler functions under test directly.
# This avoids subprocess overhead and any flow-level dependencies.
# ---------------------------------------------------------------------------
from autodev.mcp_server.tools import (
    _ENV_ALLOW_APPLY,
    _ENV_AUDIT_LOG,
    _check_apply_mode_allowed,
    _handle_deliver_project,
    _handle_run_issue,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_DELIVER_ARGS: dict[str, Any] = {
    "repo_path": "/tmp/test-repo",
    "brief_text": "Build a hello world app",
}

_MINIMAL_ISSUE_ARGS: dict[str, Any] = {
    "repo_path": "/tmp/test-repo",
    "issue_text": "Fix the null pointer dereference in main.py",
}


def _strip_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return os.environ without the apply-guardrail env vars, plus any extras."""
    base = {k: v for k, v in os.environ.items() if k not in (_ENV_ALLOW_APPLY, _ENV_AUDIT_LOG)}
    if extra:
        base.update(extra)
    return base


# ---------------------------------------------------------------------------
# 1. Default mode is dry-run (no apply attempted)
# ---------------------------------------------------------------------------

class TestDefaultDryRun:
    """Default mode must be dry-run; no apply should be triggered."""

    def test_deliver_project_default_mode_is_dry_run(self):
        """autodev_deliver_project defaults to dry-run without raising apply guardrail."""
        args = {**_MINIMAL_DELIVER_ARGS}
        # Patch the flow so we never hit real LLM/subprocess
        mock_run = mock.MagicMock()
        mock_run.run_id = "test-run-001"
        mock_run.state.release_check = None

        with mock.patch(
            "autodev.flows.project_delivery_flow.ProjectDeliveryFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(os.environ, _strip_env(), clear=True):
            result = _handle_deliver_project(args)

        # dry-run does NOT return isError
        assert result.get("isError") is not True, f"Unexpected error in dry-run: {result}"
        assert result["run_id"] == "test-run-001"

    def test_run_issue_default_mode_is_dry_run(self):
        """autodev_run_issue defaults to dry-run without raising apply guardrail."""
        args = {**_MINIMAL_ISSUE_ARGS}
        mock_run = mock.MagicMock()
        mock_run.run_id = "test-run-002"
        mock_run.state.mock_execution_used = True

        with mock.patch(
            "autodev.flows.issue_pipeline_flow.IssuePipelineFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(os.environ, _strip_env(), clear=True):
            result = _handle_run_issue(args)

        assert result.get("isError") is not True, f"Unexpected error in dry-run: {result}"
        assert result["run_id"] == "test-run-002"


# ---------------------------------------------------------------------------
# 2. Apply without allow_apply param denied
# ---------------------------------------------------------------------------

class TestApplyDeniedNoAllowApplyParam:
    """apply mode without allow_apply=True must be rejected immediately."""

    def test_deliver_project_apply_without_allow_apply_denied(self):
        """mode='apply' without allow_apply returns isError with opt-in message."""
        args = {**_MINIMAL_DELIVER_ARGS, "mode": "apply"}  # allow_apply absent/False

        with mock.patch.dict(
            os.environ, _strip_env({_ENV_ALLOW_APPLY: "1"}), clear=True
        ):
            result = _handle_deliver_project(args)

        assert result.get("isError") is True, f"Expected isError=true: {result}"
        text = result["content"][0]["text"]
        assert "allow_apply=true" in text

    def test_run_issue_apply_without_allow_apply_denied(self):
        """mode='apply' without allow_apply returns isError with opt-in message."""
        args = {**_MINIMAL_ISSUE_ARGS, "mode": "apply"}  # allow_apply absent

        with mock.patch.dict(
            os.environ, _strip_env({_ENV_ALLOW_APPLY: "1"}), clear=True
        ):
            result = _handle_run_issue(args)

        assert result.get("isError") is True, f"Expected isError=true: {result}"
        text = result["content"][0]["text"]
        assert "allow_apply=true" in text

    def test_deliver_project_apply_with_explicit_false_denied(self):
        """mode='apply' with explicit allow_apply=False must be denied."""
        args = {**_MINIMAL_DELIVER_ARGS, "mode": "apply", "allow_apply": False}

        with mock.patch.dict(
            os.environ, _strip_env({_ENV_ALLOW_APPLY: "1"}), clear=True
        ):
            result = _handle_deliver_project(args)

        assert result.get("isError") is True


# ---------------------------------------------------------------------------
# 3. Apply with allow_apply=True but no env var denied
# ---------------------------------------------------------------------------

class TestApplyDeniedNoEnvVar:
    """apply mode with allow_apply=True but missing server env var must be rejected."""

    def test_deliver_project_apply_no_env_var_denied(self):
        """allow_apply=True but AUTODEV_MCP_ALLOW_APPLY not set → denied."""
        args = {**_MINIMAL_DELIVER_ARGS, "mode": "apply", "allow_apply": True}

        # Env var NOT set
        with mock.patch.dict(os.environ, _strip_env(), clear=True):
            result = _handle_deliver_project(args)

        assert result.get("isError") is True, f"Expected isError=true: {result}"
        text = result["content"][0]["text"]
        assert _ENV_ALLOW_APPLY in text

    def test_run_issue_apply_no_env_var_denied(self):
        """allow_apply=True but AUTODEV_MCP_ALLOW_APPLY not set → denied for run_issue."""
        args = {**_MINIMAL_ISSUE_ARGS, "mode": "apply", "allow_apply": True}

        with mock.patch.dict(os.environ, _strip_env(), clear=True):
            result = _handle_run_issue(args)

        assert result.get("isError") is True, f"Expected isError=true: {result}"
        text = result["content"][0]["text"]
        assert _ENV_ALLOW_APPLY in text

    def test_env_var_value_zero_not_enough(self):
        """AUTODEV_MCP_ALLOW_APPLY=0 must not permit apply mode."""
        args = {**_MINIMAL_DELIVER_ARGS, "mode": "apply", "allow_apply": True}

        with mock.patch.dict(
            os.environ, _strip_env({_ENV_ALLOW_APPLY: "0"}), clear=True
        ):
            result = _handle_deliver_project(args)

        assert result.get("isError") is True


# ---------------------------------------------------------------------------
# 4. Apply with allow_apply=True AND env var=1 → allowed; commit/push/tag default False
# ---------------------------------------------------------------------------

class TestApplyAllowedDefaultCommitPushTag:
    """When both guardrails pass, the tool runs but commit/push/tag default to False."""

    def test_deliver_project_apply_allowed_defaults(self):
        """apply with both guards satisfied returns run_id and commit/push/tag=False."""
        args = {
            **_MINIMAL_DELIVER_ARGS,
            "mode": "apply",
            "allow_apply": True,
            # commit/push/tag intentionally NOT supplied → must default to False
        }
        mock_run = mock.MagicMock()
        mock_run.run_id = "test-run-apply-001"
        mock_run.state.release_check = None

        with mock.patch(
            "autodev.flows.project_delivery_flow.ProjectDeliveryFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(
            os.environ, _strip_env({_ENV_ALLOW_APPLY: "1"}), clear=True
        ):
            result = _handle_deliver_project(args)

        assert result.get("isError") is not True, f"Unexpected denial: {result}"
        assert result["run_id"] == "test-run-apply-001"
        assert result["commit"] is False, "commit must default to False"
        assert result["push"] is False, "push must default to False"
        assert result["tag"] is False, "tag must default to False"

    def test_run_issue_apply_allowed_defaults(self):
        """apply with both guards satisfied returns run_id and commit/push/tag=False."""
        args = {
            **_MINIMAL_ISSUE_ARGS,
            "mode": "apply",
            "allow_apply": True,
        }
        mock_run = mock.MagicMock()
        mock_run.run_id = "test-run-apply-002"
        mock_run.state.mock_execution_used = False

        with mock.patch(
            "autodev.flows.issue_pipeline_flow.IssuePipelineFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(
            os.environ, _strip_env({_ENV_ALLOW_APPLY: "1"}), clear=True
        ):
            result = _handle_run_issue(args)

        assert result.get("isError") is not True, f"Unexpected denial: {result}"
        assert result["commit"] is False
        assert result["push"] is False
        assert result["tag"] is False


# ---------------------------------------------------------------------------
# 5. Audit log contains required fields when apply is requested (allowed path)
# ---------------------------------------------------------------------------

class TestAuditLogAllowed:
    """Audit log must be written with required fields when apply is permitted."""

    def test_audit_log_allowed_fields(self, tmp_path: Path):
        """Allowed apply writes a JSON audit entry with timestamp/tool/repo/decision."""
        audit_file = str(tmp_path / "audit.log")
        args = {
            "repo_path": "/tmp/test-repo",
            "mode": "apply",
            "allow_apply": True,
        }

        with mock.patch.dict(
            os.environ,
            _strip_env({_ENV_ALLOW_APPLY: "1", _ENV_AUDIT_LOG: audit_file}),
            clear=True,
        ):
            denial = _check_apply_mode_allowed("autodev_deliver_project", args, "/tmp/test-repo")

        assert denial is None, "Expected allowed"
        entries = Path(audit_file).read_text().strip().splitlines()
        assert len(entries) >= 1
        entry = json.loads(entries[-1])
        assert "timestamp" in entry
        assert entry["tool"] == "autodev_deliver_project"
        assert entry["repo_path"] == "/tmp/test-repo"
        assert entry["decision"] == "allowed"


# ---------------------------------------------------------------------------
# 6. Audit log contains denial reason when apply is denied
# ---------------------------------------------------------------------------

class TestAuditLogDenied:
    """Audit log must record the denial reason."""

    def test_audit_log_denial_no_param(self, tmp_path: Path):
        """Denial due to missing allow_apply param writes reason to audit log."""
        audit_file = str(tmp_path / "audit_denied.log")
        args = {
            "repo_path": "/tmp/test-repo",
            "mode": "apply",
            # allow_apply missing
        }

        with mock.patch.dict(
            os.environ,
            _strip_env({_ENV_ALLOW_APPLY: "1", _ENV_AUDIT_LOG: audit_file}),
            clear=True,
        ):
            denial = _check_apply_mode_allowed("autodev_deliver_project", args, "/tmp/test-repo")

        assert denial is not None, "Expected denial"
        entries = Path(audit_file).read_text().strip().splitlines()
        assert len(entries) >= 1
        entry = json.loads(entries[-1])
        assert entry["decision"] == "denied"
        assert "reason" in entry
        assert "allow_apply" in entry["reason"]

    def test_audit_log_denial_no_env_var(self, tmp_path: Path):
        """Denial due to missing env var writes env var name to reason field."""
        audit_file = str(tmp_path / "audit_denied_env.log")
        args = {
            "repo_path": "/tmp/test-repo",
            "allow_apply": True,
        }

        with mock.patch.dict(
            os.environ,
            _strip_env({_ENV_AUDIT_LOG: audit_file}),  # AUTODEV_MCP_ALLOW_APPLY NOT set
            clear=True,
        ):
            denial = _check_apply_mode_allowed("autodev_deliver_project", args, "/tmp/test-repo")

        assert denial is not None, "Expected denial"
        entries = Path(audit_file).read_text().strip().splitlines()
        entry = json.loads(entries[-1])
        assert entry["decision"] == "denied"
        assert _ENV_ALLOW_APPLY in entry["reason"]


# ---------------------------------------------------------------------------
# 7. run_issue: apply requires BOTH flags
# ---------------------------------------------------------------------------

class TestRunIssueBothFlagsRequired:
    """autodev_run_issue apply guardrail requires both allow_apply param AND env var."""

    def test_run_issue_apply_only_param_no_env_denied(self):
        """allow_apply=True but no env → denied for run_issue."""
        args = {**_MINIMAL_ISSUE_ARGS, "mode": "apply", "allow_apply": True}

        with mock.patch.dict(os.environ, _strip_env(), clear=True):
            result = _handle_run_issue(args)

        assert result.get("isError") is True

    def test_run_issue_apply_only_env_no_param_denied(self):
        """env=1 but allow_apply missing → denied for run_issue."""
        args = {**_MINIMAL_ISSUE_ARGS, "mode": "apply"}  # allow_apply absent

        with mock.patch.dict(
            os.environ, _strip_env({_ENV_ALLOW_APPLY: "1"}), clear=True
        ):
            result = _handle_run_issue(args)

        assert result.get("isError") is True

    def test_run_issue_apply_both_flags_allowed(self):
        """Both allow_apply=True and env=1 allows run_issue in apply mode."""
        args = {**_MINIMAL_ISSUE_ARGS, "mode": "apply", "allow_apply": True}

        mock_run = mock.MagicMock()
        mock_run.run_id = "issue-apply-ok"
        mock_run.state.mock_execution_used = False

        with mock.patch(
            "autodev.flows.issue_pipeline_flow.IssuePipelineFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(
            os.environ, _strip_env({_ENV_ALLOW_APPLY: "1"}), clear=True
        ):
            result = _handle_run_issue(args)

        assert result.get("isError") is not True
        assert result["run_id"] == "issue-apply-ok"


# ---------------------------------------------------------------------------
# 8. Invalid mode value rejected
# ---------------------------------------------------------------------------

class TestInvalidMode:
    """An unrecognised mode value must be rejected with isError."""

    def test_deliver_project_invalid_mode(self):
        """Unknown mode string returns isError=True."""
        args = {**_MINIMAL_DELIVER_ARGS, "mode": "YOLO"}

        with mock.patch.dict(os.environ, _strip_env(), clear=True):
            result = _handle_deliver_project(args)

        assert result.get("isError") is True
        assert "YOLO" in result["content"][0]["text"]

    def test_run_issue_invalid_mode(self):
        """Unknown mode string returns isError=True for run_issue."""
        args = {**_MINIMAL_ISSUE_ARGS, "mode": "execute-now"}

        with mock.patch.dict(os.environ, _strip_env(), clear=True):
            result = _handle_run_issue(args)

        assert result.get("isError") is True
        assert "execute-now" in result["content"][0]["text"]


# ---------------------------------------------------------------------------
# 9. Audit log default path fallback
# ---------------------------------------------------------------------------

class TestAuditLogDefaultPath:
    """When AUTODEV_MCP_AUDIT_LOG is unset, write to _DEFAULT_AUDIT_LOG."""

    def test_default_audit_log_path_used(self, tmp_path: Path):
        """Audit entries go to DEFAULT_AUDIT_LOG when env var not set."""
        # Use a temp file as the default path via monkeypatching the module constant
        audit_file = str(tmp_path / "default_audit.log")

        args = {"repo_path": "/tmp/repo", "allow_apply": True}

        with mock.patch("autodev.mcp_server.tools._DEFAULT_AUDIT_LOG", audit_file), \
             mock.patch.dict(
                 os.environ,
                 _strip_env({_ENV_ALLOW_APPLY: "1"}),  # no _ENV_AUDIT_LOG
                 clear=True,
             ):
            denial = _check_apply_mode_allowed("autodev_deliver_project", args, "/tmp/repo")

        assert denial is None  # allowed
        lines = Path(audit_file).read_text().strip().splitlines()
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["decision"] == "allowed"
