"""R4-A — Preflight path-safety denial tests for MCP tools.

Covers all rejection patterns implemented in
``autodev.mcp_server.path_safety._validate_safe_path``:

  - Exact basenames: ``.env``, ``credentials.json``, ``secrets.toml``
  - Glob patterns:   ``.env.*``, ``*.pem``, ``*.key``
  - Basename substrings: ``secret``, ``token``, ``credential``
  - Path traversal:  segments containing ``..``
  - Allow-list sanity: safe paths must pass through
"""
from __future__ import annotations

import os
from unittest import mock

import pytest

from autodev.mcp_server.path_safety import MCPPathSafetyError, _validate_safe_path
from autodev.mcp_server.tools import (
    _ENV_AUDIT_LOG,
    _handle_deliver_project,
    _handle_list_runs,
    _handle_release_check,
    _handle_report,
    _handle_run_issue,
    _handle_scan,
)

# ---------------------------------------------------------------------------
# Helper: run a handler call with apply-mode env stripped (so denials come
# purely from path-safety, not apply-mode guard).
# ---------------------------------------------------------------------------

def _call_deliver(repo_path: str) -> dict:  # type: ignore[type-arg]
    """Call _handle_deliver_project with the given repo_path."""
    args = {"repo_path": repo_path, "brief_text": "test brief"}
    clean_env = {k: v for k, v in os.environ.items()
                 if k not in ("AUTODEV_MCP_ALLOW_APPLY", _ENV_AUDIT_LOG)}
    with mock.patch.dict(os.environ, clean_env, clear=True):
        return _handle_deliver_project(args)  # type: ignore[return-value]


def _call_scan(repo_path: str) -> dict:  # type: ignore[type-arg]
    args = {"repo_path": repo_path}
    return _handle_scan(args)  # type: ignore[return-value]


def _call_list_runs(repo_path: str) -> object:
    args = {"repo_path": repo_path}
    return _handle_list_runs(args)


# ---------------------------------------------------------------------------
# Unit tests: _validate_safe_path raises on bad paths
# ---------------------------------------------------------------------------


class TestValidateSafePathRejects:
    """_validate_safe_path raises MCPPathSafetyError for rejected paths."""

    def test_rejects_dot_env(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("/tmp/.env")

    def test_rejects_dot_env_production(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("/app/.env.production")

    def test_rejects_dot_env_local(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path(".env.local")

    def test_rejects_credentials_json(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("/home/user/credentials.json")

    def test_rejects_secrets_toml(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("secrets.toml")

    def test_rejects_key_pem(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("/etc/ssl/key.pem")

    def test_rejects_id_rsa_key(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("/home/user/.ssh/id_rsa.key")

    def test_rejects_secret_substring_in_basename(self):
        """my-secret-file.txt has 'secret' in the basename."""
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("/tmp/my-secret-file.txt")

    def test_rejects_path_traversal_dot_dot(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("../etc/passwd")

    def test_rejects_path_traversal_in_middle(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("/tmp/some/../../../etc/shadow")

    def test_rejects_token_in_basename(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("/home/user/github_token.txt")

    def test_rejects_credential_in_basename(self):
        with pytest.raises(MCPPathSafetyError):
            _validate_safe_path("/opt/app/credential_store.db")


class TestValidateSafePathAllows:
    """_validate_safe_path does NOT raise for safe paths."""

    def test_allows_regular_md_file(self):
        _validate_safe_path("examples/01-mdlines/brief.md")

    def test_allows_regular_repo_path(self):
        _validate_safe_path("/tmp/some/regular/repo")

    def test_allows_parent_dir_named_secret_but_safe_basename(self):
        """Parent directory named 'secret' should NOT be flagged — only basename."""
        _validate_safe_path("/Users/secret/dev/repo")

    def test_allows_tmp_path(self):
        _validate_safe_path("/tmp/my-project")

    def test_allows_dot_git(self):
        """A directory like .git-hooks should be allowed."""
        _validate_safe_path("/tmp/repo/.git")

    def test_allows_plain_json_file(self):
        _validate_safe_path("/data/config.json")

    def test_allows_readme_md(self):
        _validate_safe_path("/home/user/project/README.md")


# ---------------------------------------------------------------------------
# Integration tests: MCP handlers return isError for rejected paths
# ---------------------------------------------------------------------------


class TestMCPHandlerPathDenial:
    """MCP handlers return ``{"isError": true, ...}`` for rejected repo_path."""

    def test_deliver_project_rejects_dot_env(self):
        result = _call_deliver("/tmp/.env")
        assert result.get("isError") is True
        assert result["content"][0]["text"] == "Path rejected: matches secret-file pattern"

    def test_deliver_project_rejects_env_production(self):
        result = _call_deliver("/app/.env.production")
        assert result.get("isError") is True

    def test_deliver_project_rejects_credentials_json(self):
        result = _call_deliver("/home/user/credentials.json")
        assert result.get("isError") is True

    def test_deliver_project_rejects_path_traversal(self):
        result = _call_deliver("../etc/passwd")
        assert result.get("isError") is True

    def test_scan_rejects_dot_env(self):
        result = _call_scan("/srv/.env")
        assert result.get("isError") is True

    def test_list_runs_rejects_secret_path(self):
        result = _call_list_runs("/data/my-secret-file")
        assert isinstance(result, dict)
        assert result.get("isError") is True

    def test_deliver_project_allows_regular_path(self):
        """A safe repo path should NOT trigger a path-safety denial.

        We do not assert the full flow succeeds (it may fail for other reasons
        like missing executors), but we assert the result does NOT have
        isError set to True *due to path safety* — specifically, if isError is
        set, the reason must not be the path-safety message.
        """
        result = _call_deliver("/tmp/regular-repo")
        if result.get("isError"):
            text = result.get("content", [{}])[0].get("text", "")
            assert "Path rejected" not in text, (
                f"Safe path '/tmp/regular-repo' was incorrectly rejected: {text}"
            )

    def test_run_issue_rejects_dot_env(self):
        args = {
            "repo_path": "/tmp/.env",
            "issue_text": "some issue",
        }
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("AUTODEV_MCP_ALLOW_APPLY", _ENV_AUDIT_LOG)}
        with mock.patch.dict(os.environ, clean_env, clear=True):
            result = _handle_run_issue(args)
        assert result.get("isError") is True
        assert "Path rejected" in result["content"][0]["text"]

    def test_error_message_does_not_leak_path_content(self):
        """Error text must NOT echo back the original path."""
        result = _call_deliver("/tmp/.env")
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        # The path itself must not appear in the error message
        assert "/tmp/.env" not in text
        assert ".env" not in text or "Path rejected" in text

    def test_report_handler_rejects_dot_env(self):
        args = {"repo_path": "/tmp/.env", "run_id": "run-001"}
        result = _handle_report(args)
        assert isinstance(result, dict)
        assert result.get("isError") is True

    def test_release_check_rejects_secrets_toml(self):
        args = {"repo_path": "/tmp/secrets.toml", "run_id": "run-001"}
        result = _handle_release_check(args)
        assert result.get("isError") is True
