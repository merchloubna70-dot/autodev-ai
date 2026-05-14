"""Tests for SandboxedExecutor.

Verifies that:
1. SandboxedExecutor wraps a MockCodexExecutor and returns results.
2. mock_used=True propagates through from the inner executor.
3. network_audit_only flag is honoured (reflected in selected_backend_reason).
4. allow_domains are propagated to the internal NetworkAllowlist.
"""
from __future__ import annotations

import pytest

from autodev.executors.mock_codex_executor import MockCodexExecutor
from autodev.executors.sandboxed_executor import SandboxedExecutor
from autodev.schemas import (
    ExecutionRequest,
    Language,
    PipelineMode,
)


def _make_request(task_id: str = "T-sandbox-1", repo_path: str = "/tmp") -> ExecutionRequest:
    return ExecutionRequest(
        task_id=task_id,
        milestone_id="MI-1",
        repo_path=repo_path,
        prompt="Add a hello-world function",
        language=Language.PYTHON,
        mode=PipelineMode.DRY_RUN,
    )


# ---------------------------------------------------------------------------
# Test 1: wraps inner MockCodex executor
# ---------------------------------------------------------------------------


def test_sandboxed_executor_wraps_inner_mock_codex(tmp_path):
    """SandboxedExecutor delegates to inner MockCodexExecutor and returns a result."""
    inner = MockCodexExecutor()
    sandboxed = SandboxedExecutor(inner, sandbox_provider="none")

    assert sandboxed.is_available() is True
    assert sandboxed.is_mock is True  # inherited from inner

    req = _make_request(repo_path=str(tmp_path))
    result = sandboxed.execute(req)

    assert result is not None
    assert result.task_id == req.task_id


# ---------------------------------------------------------------------------
# Test 2: mock_used=True passes through
# ---------------------------------------------------------------------------


def test_sandboxed_executor_passes_through_mock_used(tmp_path):
    """mock_used=True from the inner executor is preserved in the result."""
    inner = MockCodexExecutor()
    sandboxed = SandboxedExecutor(inner, sandbox_provider="none")

    req = _make_request(task_id="T-mock-passthrough", repo_path=str(tmp_path))
    result = sandboxed.execute(req)

    assert result.mock_used is True


# ---------------------------------------------------------------------------
# Test 3: audit_only flag annotates selected_backend_reason
# ---------------------------------------------------------------------------


def test_sandboxed_executor_audit_only_flag_honored(tmp_path):
    """When sandbox_provider='none', result includes audit_only annotation."""
    inner = MockCodexExecutor()
    sandboxed = SandboxedExecutor(inner, sandbox_provider="none", network_audit_only=True)

    req = _make_request(task_id="T-audit", repo_path=str(tmp_path))
    result = sandboxed.execute(req)

    assert "audit_only=True" in result.selected_backend_reason


def test_sandboxed_executor_audit_only_false_annotation(tmp_path):
    """network_audit_only=False is reflected in the annotation."""
    inner = MockCodexExecutor()
    sandboxed = SandboxedExecutor(inner, sandbox_provider="none", network_audit_only=False)

    req = _make_request(task_id="T-audit-false", repo_path=str(tmp_path))
    result = sandboxed.execute(req)

    assert "audit_only=False" in result.selected_backend_reason


# ---------------------------------------------------------------------------
# Test 4: network domain allowlist is propagated
# ---------------------------------------------------------------------------


def test_sandboxed_executor_allow_domains_propagated():
    """allow_domains are stored and passed into the internal NetworkAllowlist."""
    inner = MockCodexExecutor()
    domains = ["api.github.com", "*.pypi.org"]
    sandboxed = SandboxedExecutor(inner, allow_domains=domains, sandbox_provider="none")

    assert sandboxed.allow_domains == domains

    # Audit check uses the allowlist
    assert sandboxed.audit_domain("https://api.github.com/repos") is True
    # Domain not in the allow list should be denied (default_deny=True in NetworkAllowlistPolicy)
    assert sandboxed.audit_domain("https://malicious.example.com") is False


# ---------------------------------------------------------------------------
# Test 5: unsupported sandbox_provider raises NotImplementedError
# ---------------------------------------------------------------------------


def test_sandboxed_executor_unsupported_provider_raises(tmp_path):
    """Non-none sandbox_provider raises NotImplementedError (no actual E2B/Modal integration)."""
    inner = MockCodexExecutor()
    sandboxed = SandboxedExecutor(inner, sandbox_provider="e2b")

    req = _make_request(repo_path=str(tmp_path))
    with pytest.raises(NotImplementedError, match="e2b"):
        sandboxed.execute(req)
