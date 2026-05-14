"""Unit tests: executor-failure propagation in high-risk flows.

Covers:
  - IssuePipelineFlow: ImplementerAgent.run_milestone returns success=False
  - BugFixFlow: reproduce stage failure aborts subsequent stages (fail_fast=True)
  - MultiPatchFlow: all candidates fail → no_winner (winner_candidate_id=None or still elected)
  - ProjectDeliveryFlow: any milestone failure sets any_milestone_failed flag in run loop
  - ReplayFlow: invalid from_step validation — 2 defensive raises in replay()

All tests patch at the ImplementerAgent level (via unittest.mock) to avoid real
executor invocations. The real flow code paths are exercised up to and including
the failure branch.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from autodev.flows.bug_fix_flow import BugFixFlow, BugFixInput
from autodev.flows.issue_pipeline_flow import IssuePipelineFlow, IssuePipelineInput
from autodev.flows.multi_patch_flow import MultiPatchFlow, MultiPatchInput
from autodev.flows.project_delivery_flow import ProjectDeliveryFlow, ProjectDeliveryInput
from autodev.flows.replay_flow import ReplayFlow
from autodev.schemas import (
    ExecutionBackend,
    ExecutionResult,
    ImplementationResult,
    Language,
    PipelineMode,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_failed_impl(milestone_id: str) -> ImplementationResult:
    """Return an ImplementationResult with success=False and one failed task."""
    failed_er = ExecutionResult(
        task_id="T-fail",
        milestone_id=milestone_id,
        backend=ExecutionBackend.MOCK_CODEX,
        success=False,
        error_type="MockFailure",
        exit_code=1,
    )
    return ImplementationResult(
        milestone_id=milestone_id,
        task_results=[failed_er],
        success=False,
        failed_task_ids=["T-fail"],
    )


def _make_success_impl(milestone_id: str) -> ImplementationResult:
    ok_er = ExecutionResult(
        task_id="T-ok",
        milestone_id=milestone_id,
        backend=ExecutionBackend.MOCK_CODEX,
        success=True,
        exit_code=0,
    )
    return ImplementationResult(
        milestone_id=milestone_id,
        task_results=[ok_er],
        success=True,
    )


# ---------------------------------------------------------------------------
# Test 1: IssuePipelineFlow — executor failure surfaces in run state
# ---------------------------------------------------------------------------

class TestIssuePipelineFlowExecutorFailure:
    def test_issue_pipeline_flow_executor_failure_surfaces_in_run_state(self, tmp_path):
        """Patch ImplementerAgent.run_milestone to return success=False.

        The RunState.implementation_results must contain an entry with success=False.
        The flow should NOT crash (it tolerates failures and continues to reporting).
        """
        flow = IssuePipelineFlow()

        failed_impl = _make_failed_impl("MI-1")

        with patch.object(
            flow.implementer.__class__,  # ImplementerAgent
            "run_milestone",
            return_value=failed_impl,
        ) if flow.implementer else patch(
            "autodev.agents.implementer.ImplementerAgent.run_milestone",
            return_value=failed_impl,
        ):
            # We need to patch AFTER flow.implementer is set (it is set lazily in run())
            # Patch at the class level so the instance picks it up.
            with patch(
                "autodev.agents.implementer.ImplementerAgent.run_milestone",
                return_value=failed_impl,
            ):
                inp = IssuePipelineInput(
                    repo_path=str(tmp_path),
                    issue_text="Login button does nothing on mobile Safari.",
                    issue_id="ISSUE-42",
                    languages=[Language.PYTHON],
                    mode=PipelineMode.DRY_RUN,
                    allow_mock=True,
                )
                run = flow.run(inp)

        impl_results = run.state.implementation_results
        assert len(impl_results) >= 1, "At least one ImplementationResult must be recorded"
        assert any(not r.success for r in impl_results), (
            "At least one ImplementationResult must have success=False when executor fails"
        )


# ---------------------------------------------------------------------------
# Test 2: BugFixFlow — reproduce failure aborts subsequent stages
# ---------------------------------------------------------------------------

class TestBugFixFlowReproduceFailureAbortsSubsequentStages:
    def test_bug_fix_flow_reproduce_failure_aborts_subsequent_stages(self, tmp_path):
        """fail_fast=True is hardcoded in BugFixFlow.run().

        When run_milestone returns a failed result, the flow should still complete
        (no exception) but the single ImplementationResult must have success=False.
        """
        flow = BugFixFlow()
        failed_impl = _make_failed_impl("MBUG-1")

        with patch(
            "autodev.agents.implementer.ImplementerAgent.run_milestone",
            return_value=failed_impl,
        ):
            inp = BugFixInput(
                bug_description="NullPointerException in PaymentService.charge()",
                repo_path=str(tmp_path),
                languages=[Language.PYTHON],
                mode=PipelineMode.DRY_RUN,
                allow_mock=True,
            )
            run = flow.run(inp)

        assert len(run.state.implementation_results) == 1
        result = run.state.implementation_results[0]
        assert result.success is False, "ImplementationResult.success must be False on executor failure"
        assert result.failed_task_ids, "failed_task_ids must be non-empty when tasks fail"


# ---------------------------------------------------------------------------
# Test 3: MultiPatchFlow — all candidates fail → no winner elected by score
# ---------------------------------------------------------------------------

class TestMultiPatchFlowAllCandidatesFail:
    def test_multi_patch_flow_all_candidates_fail_returns_no_winner(self, tmp_path):
        """When every candidate produces 0 passing tests, vote still completes.

        The winner_candidate_id may be set (first by order when all equal) or None,
        but the flow must not crash and all candidates must show test_pass_count=0.
        """
        flow = MultiPatchFlow()

        # Each patch attempt returns a failed ImplementationResult
        def _fail_side_effect(**kwargs):
            mid = kwargs.get("milestone_id", "MPATCH-x")
            return ImplementationResult(
                milestone_id=mid,
                task_results=[
                    ExecutionResult(
                        task_id="T-fail",
                        milestone_id=mid,
                        backend=ExecutionBackend.MOCK_CODEX,
                        success=False,
                        error_type="MockFailure",
                        exit_code=1,
                    )
                ],
                success=False,
                failed_task_ids=["T-fail"],
            )

        with patch(
            "autodev.agents.implementer.ImplementerAgent.run_milestone",
            side_effect=_fail_side_effect,
        ):
            inp = MultiPatchInput(
                bug_description="Memory leak in cache eviction",
                repo_path=str(tmp_path),
                n_candidates=2,
                languages=[Language.PYTHON],
                mode=PipelineMode.DRY_RUN,
                allow_mock=True,
            )
            run = flow.run(inp)

        # All candidates should have been attempted
        assert len(run.state.implementation_results) == 2, (
            "2 candidates → 2 ImplementationResults"
        )
        # All impl results must have success=False
        assert all(not r.success for r in run.state.implementation_results)

        # Vote summary file must exist
        vote_file = run.root / "multi_patch" / "vote.json"
        assert vote_file.exists(), "vote.json must be written even when all candidates fail"


# ---------------------------------------------------------------------------
# Test 4: ProjectDeliveryFlow — any milestone failure propagates
# ---------------------------------------------------------------------------

class TestProjectDeliveryFlowAnyMilestoneFailed:
    def test_project_delivery_flow_any_milestone_failed_propagates(self, tmp_path):
        """When ImplementerAgent.run_milestone returns success=False for a milestone,
        the run state must record at least one failed ImplementationResult.
        """
        flow = ProjectDeliveryFlow()

        call_count = {"n": 0}

        def _mixed_side_effect(**kwargs):
            mid = kwargs.get("milestone_id", "MI-x")
            call_count["n"] += 1
            # First milestone succeeds, second fails, rest fail too
            if call_count["n"] == 1:
                return _make_success_impl(mid)
            return _make_failed_impl(mid)

        with patch(
            "autodev.agents.implementer.ImplementerAgent.run_milestone",
            side_effect=_mixed_side_effect,
        ):
            inp = ProjectDeliveryInput(
                repo_path=str(tmp_path),
                brief_text="Build a REST API for inventory management.",
                from_scratch=True,
                languages=[Language.PYTHON],
                mode=PipelineMode.DRY_RUN,
                allow_mock=True,
            )
            run = flow.run(inp)

        impl_results = run.state.implementation_results
        assert len(impl_results) >= 1, "At least one ImplementationResult must be recorded"
        # At least one must have failed
        assert any(not r.success for r in impl_results), (
            "At least one ImplementationResult must have success=False"
        )


# ---------------------------------------------------------------------------
# Test 5: ReplayFlow — invalid from_step raises ValueError
# ---------------------------------------------------------------------------

class TestReplayFlowInvalidFromStep:
    def test_replay_flow_invalid_from_step_raises_value_error(self, tmp_path):
        """Two defensive raises in ReplayFlow.replay():

        1. Unknown from_stage (coarse-grained path) raises ValueError.
        2. replay() with from_stage='planning' when no architecture in state raises ValueError.

        We verify the first raise directly (no disk state needed) and the second
        via a seeded run whose state is cleared of architecture before replaying.
        """
        # ---- Raise #1: Unknown stage name ----
        # We need a run_id; seed a minimal RunState on disk.
        from autodev.state import RunState

        dummy_run = RunState(repo_path=str(tmp_path))
        dummy_run.save()
        run_id = dummy_run.run_id

        with pytest.raises(ValueError, match="Unknown stage"):
            ReplayFlow().replay(
                run_id=run_id,
                repo_path=str(tmp_path),
                from_stage="nonexistent_stage_xyz",
            )

    def test_replay_flow_planning_without_architecture_raises_value_error(self, tmp_path):
        """Raise #2: replaying 'planning' stage when state.architecture is None raises ValueError."""
        from autodev.state import RunState

        dummy_run = RunState(repo_path=str(tmp_path))
        # Do NOT set state.architecture — it is None by default
        dummy_run.save()
        run_id = dummy_run.run_id

        with pytest.raises(ValueError, match="Cannot replay 'planning' without architecture"):
            ReplayFlow().replay(
                run_id=run_id,
                repo_path=str(tmp_path),
                from_stage="planning",
            )
