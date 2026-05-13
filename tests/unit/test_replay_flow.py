"""Tests for ReplayFlow — stage-aware pipeline replay."""
from __future__ import annotations

import pytest

from crewai_multicli_factory.flows.project_delivery_flow import (
    ProjectDeliveryFlow,
    ProjectDeliveryInput,
)
from crewai_multicli_factory.flows.replay_flow import ReplayFlow
from crewai_multicli_factory.schemas import Language, PipelineMode


def _seed_run(tmp_path):
    """Run ProjectDeliveryFlow once to seed a RunState on disk."""
    flow = ProjectDeliveryFlow()
    run = flow.run(
        ProjectDeliveryInput(
            repo_path=str(tmp_path),
            brief_text="A simple test project.",
            from_scratch=True,
            languages=[Language.PYTHON],
            mode=PipelineMode.DRY_RUN,
            allow_mock=True,
        )
    )
    return run


def test_replay_release_adds_note(tmp_path):
    run = _seed_run(tmp_path)
    run_id = run.run_id

    replayed = ReplayFlow().replay(run_id=run_id, repo_path=str(tmp_path), from_stage="release")

    notes = replayed.state.errors
    assert any(n.startswith("replayed from stage release") for n in notes), (
        f"Expected note in errors, got: {notes}"
    )


def test_replay_implementation_repopulates_results(tmp_path):
    run = _seed_run(tmp_path)
    run_id = run.run_id

    replayed = ReplayFlow().replay(
        run_id=run_id, repo_path=str(tmp_path), from_stage="implementation"
    )

    assert isinstance(replayed.state.implementation_results, list)
    # At least one milestone implementation result should be present
    assert len(replayed.state.implementation_results) >= 1

    notes = replayed.state.errors
    assert any(n.startswith("replayed from stage implementation") for n in notes)


def test_replay_bogus_stage_raises(tmp_path):
    run = _seed_run(tmp_path)
    run_id = run.run_id

    with pytest.raises(ValueError, match="bogus"):
        ReplayFlow().replay(run_id=run_id, repo_path=str(tmp_path), from_stage="bogus")
