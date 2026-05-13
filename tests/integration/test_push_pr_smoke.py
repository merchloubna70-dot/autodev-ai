"""Integration smoke tests for push / PR commands — all off by default."""
from __future__ import annotations

from autodev.agents.commit_agent import CommitAgent, CommitArtifacts
from autodev.schemas import (
    ExecutionBackend,
    Language,
    PipelineMode,
    PipelineRunState,
)
from autodev.utils.command_safety import is_command_allowed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_state(tmp_path) -> PipelineRunState:
    state = PipelineRunState(
        run_id="smoke-run-001",
        flow="issue_pipeline_flow",
        repo_path=str(tmp_path),
        mode=PipelineMode.DRY_RUN,
        languages=[Language.PYTHON],
        mock_execution_used=True,
    )
    state.backends_used = [ExecutionBackend.MOCK_CODEX]
    return state


def _make_artifacts() -> CommitArtifacts:
    return CommitArtifacts(
        branch_name="feature/smoke-test",
        commit_message="test commit",
        pr_body=(
            "# PR\n\n## Summary\nTest.\n\n## Scope\n- n/a\n\n## Milestones\n\n"
            "## Quality Gates\n\n## Release Gate Result\n\n## Known Limitations\n"
            "- MockExecutionUsed: `True`\n"
        ),
    )


# ---------------------------------------------------------------------------
# maybe_push — off by default
# ---------------------------------------------------------------------------


def test_maybe_push_disabled_returns_zero(tmp_path):
    """maybe_push with enabled=False must be a no-op returning 0."""
    rc = CommitAgent().maybe_push(str(tmp_path), branch="some-branch", enabled=False)
    assert rc == 0


def test_maybe_push_enabled_but_no_git_returns_zero(tmp_path):
    """No .git dir → even enabled=True is a safe no-op."""
    rc = CommitAgent().maybe_push(str(tmp_path), branch="some-branch", enabled=True)
    assert rc == 0


# ---------------------------------------------------------------------------
# maybe_create_pr — off by default
# ---------------------------------------------------------------------------


def test_maybe_create_pr_disabled_returns_noop(tmp_path):
    """enabled=False must return a failure dict, never raise."""
    result = CommitAgent().maybe_create_pr(
        str(tmp_path), _make_artifacts(), base="main", draft=True, enabled=False
    )
    assert isinstance(result, dict)
    assert result["success"] is False


def test_maybe_create_pr_enabled_but_gh_unavailable_or_unauthed(tmp_path, monkeypatch):
    """With enabled=True the function must return a dict with success=False and error set.

    We cannot create a real PR in CI/offline, so we accept any failure as long as
    the function does NOT raise and returns the expected shape.
    """
    # Simulate gh not installed
    import shutil as _shutil

    original_which = _shutil.which

    def _no_gh(name: str, *args, **kwargs):
        if name == "gh":
            return None
        return original_which(name, *args, **kwargs)

    monkeypatch.setattr(_shutil, "which", _no_gh)

    result = CommitAgent().maybe_create_pr(
        str(tmp_path), _make_artifacts(), base="main", draft=True, enabled=True
    )
    assert isinstance(result, dict)
    assert result["success"] is False
    # Some error key must be present
    assert "error" in result or "reason" in result


# ---------------------------------------------------------------------------
# command_safety — force-push protection
# ---------------------------------------------------------------------------


def test_force_push_is_denied():
    """git push --force must be rejected by the denylist."""
    verdict = is_command_allowed("git push --force")
    assert verdict.allowed is False, f"Expected denied but got allowed; reason={verdict.reason}"


def test_force_flag_alone_is_denied():
    """Any command containing --force must be rejected."""
    verdict = is_command_allowed("gh pr create --force")
    assert verdict.allowed is False


def test_git_push_origin_main_is_allowed():
    """git push origin main must pass the allowlist."""
    verdict = is_command_allowed("git push origin main")
    assert verdict.allowed is True, f"Expected allowed but got denied; reason={verdict.reason}"


def test_git_push_origin_is_allowed():
    """git push origin must pass."""
    verdict = is_command_allowed("git push origin")
    assert verdict.allowed is True


def test_git_push_bare_is_allowed():
    """Plain 'git push' must pass."""
    verdict = is_command_allowed("git push")
    assert verdict.allowed is True
