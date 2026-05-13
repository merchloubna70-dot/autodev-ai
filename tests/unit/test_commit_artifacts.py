"""Unit tests for CommitAgent.build_artifacts."""
from __future__ import annotations

from autodev.agents.commit_agent import CommitAgent
from autodev.schemas import (
    ExecutionBackend,
    Language,
    PipelineMode,
    PipelineRunState,
)


def _make_state(flow: str = "issue_pipeline_flow", mock: bool = True) -> PipelineRunState:
    state = PipelineRunState(
        run_id="test-run-001",
        flow=flow,
        repo_path="/tmp/repo",
        mode=PipelineMode.DRY_RUN,
        languages=[Language.PYTHON],
        mock_execution_used=mock,
    )
    state.backends_used = [ExecutionBackend.MOCK_CODEX]
    return state


def test_feature_branch_for_issue_flow():
    state = _make_state(flow="issue_pipeline_flow")
    artifacts = CommitAgent().build_artifacts(state=state, project_name="myproject")
    assert artifacts.branch_name.startswith("feature/")


def test_fix_branch_when_issue_id_provided():
    state = _make_state(flow="issue_pipeline_flow")
    artifacts = CommitAgent().build_artifacts(state=state, project_name="myproject", issue_id="BUG-42")
    assert artifacts.branch_name.startswith("fix/")


def test_delivery_branch_for_delivery_flow():
    state = _make_state(flow="project_delivery_flow")
    artifacts = CommitAgent().build_artifacts(state=state, project_name="myproject")
    assert artifacts.branch_name.startswith("delivery/")


def test_branch_starts_with_valid_prefix():
    """branch_name must start with feature/, fix/, or delivery/."""
    for flow, issue_id, expected_prefix in [
        ("issue_pipeline_flow", None, "feature/"),
        ("issue_pipeline_flow", "ISS-1", "fix/"),
        ("project_delivery_flow", None, "delivery/"),
    ]:
        state = _make_state(flow=flow)
        artifacts = CommitAgent().build_artifacts(
            state=state, project_name="proj", issue_id=issue_id
        )
        assert artifacts.branch_name.startswith(expected_prefix), (
            f"Expected prefix {expected_prefix!r}, got {artifacts.branch_name!r}"
        )


def test_pr_body_required_sections():
    """PR body must contain all required sections."""
    state = _make_state()
    artifacts = CommitAgent().build_artifacts(state=state, project_name="myproject")
    pr = artifacts.pr_body

    required_sections = [
        "## Summary",
        "## Scope",
        "## Milestones",
        "## Quality Gates",
        "## Release Gate Result",
        "## Known Limitations",
    ]
    for section in required_sections:
        assert section in pr, f"Missing section {section!r} in PR body"


def test_pr_body_contains_mock_execution_line():
    """PR body must contain the MockExecutionUsed: sentinel line."""
    state = _make_state(mock=True)
    artifacts = CommitAgent().build_artifacts(state=state, project_name="myproject")
    assert "MockExecutionUsed:" in artifacts.pr_body


def test_pr_body_mock_false():
    state = _make_state(mock=False)
    artifacts = CommitAgent().build_artifacts(state=state, project_name="myproject")
    # Line still present, just with False value
    assert "MockExecutionUsed:" in artifacts.pr_body
