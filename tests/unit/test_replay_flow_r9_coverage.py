"""R9-B4 coverage backfill for src/autodev/flows/replay_flow.py.

Target: raise coverage from 65% → ≥85%.

Missing regions (from coverage report lines 109-155, 186-197, 201-212,
216-228, 237-242, 248):
  * from_step fine-grained resume path (lines 109-155)
  * classification stage (lines 186-197)
  * product stage (lines 201-212)
  * architecture stage including fallback PRD (lines 216-228)
  * planning ValueError when no architecture in state (lines 237-242)
  * implementation ValueError when no milestone_plan in state (line 248)
  * _snapshot_run() helper (F1-added, lines 67-90)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autodev.flows.project_delivery_flow import (
    ProjectDeliveryFlow,
    ProjectDeliveryInput,
)
from autodev.flows.replay_flow import ReplayFlow, _snapshot_run
from autodev.schemas import Language, PipelineMode
from autodev.state import RunState

# ---------------------------------------------------------------------------
# Shared seed helper — identical to test_replay_flow.py to build a real run
# ---------------------------------------------------------------------------

def _seed_run(tmp_path: Path) -> RunState:
    """Run ProjectDeliveryFlow once to produce a seeded RunState on disk."""
    flow = ProjectDeliveryFlow()
    return flow.run(
        ProjectDeliveryInput(
            repo_path=str(tmp_path),
            brief_text="A simple test project for R9 coverage.",
            from_scratch=True,
            languages=[Language.PYTHON],
            mode=PipelineMode.DRY_RUN,
            allow_mock=True,
        )
    )


# ===========================================================================
# _snapshot_run() helper — F1-added, explicitly tested per task spec
# ===========================================================================

class TestSnapshotRun:
    """Cover _snapshot_run() directly (lines 67-90)."""

    def test_creates_snapshot_dir(self, tmp_path: Path):
        """_snapshot_run creates replays/<replay_id>/ under run_root."""
        run_root = tmp_path / "run1"
        run_root.mkdir()
        replay_id = _snapshot_run(run_root, "planning")
        assert replay_id.startswith("replay_")
        snapshot_dir = run_root / "replays" / replay_id
        assert snapshot_dir.is_dir()

    def test_returns_replay_id_string(self, tmp_path: Path):
        """Return value is a non-empty string with expected prefix."""
        run_root = tmp_path / "run2"
        run_root.mkdir()
        result = _snapshot_run(run_root, "quality")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_copies_run_state_json(self, tmp_path: Path):
        """run_state.json is copied into the snapshot dir when present."""
        run_root = tmp_path / "run3"
        run_root.mkdir()
        state_file = run_root / "run_state.json"
        state_file.write_text(json.dumps({"run_id": "test", "repo_path": str(tmp_path)}))

        replay_id = _snapshot_run(run_root, "release")
        snapshot_dir = run_root / "replays" / replay_id
        assert (snapshot_dir / "run_state.json").is_file()

    def test_no_run_state_json_ok(self, tmp_path: Path):
        """_snapshot_run succeeds even when run_state.json does not exist."""
        run_root = tmp_path / "run4"
        run_root.mkdir()
        replay_id = _snapshot_run(run_root, "verification")
        snapshot_dir = run_root / "replays" / replay_id
        assert snapshot_dir.is_dir()
        assert not (snapshot_dir / "run_state.json").exists()

    def test_copies_existing_subdirs(self, tmp_path: Path):
        """Existing stage subdirs are copied into the snapshot."""
        run_root = tmp_path / "run5"
        run_root.mkdir()
        planning_dir = run_root / "planning"
        planning_dir.mkdir()
        (planning_dir / "milestones.json").write_text('{"milestones": []}')

        replay_id = _snapshot_run(run_root, "implementation")
        snapshot_dir = run_root / "replays" / replay_id
        assert (snapshot_dir / "planning" / "milestones.json").is_file()

    def test_missing_subdirs_are_skipped(self, tmp_path: Path):
        """Stage subdirs that don't exist are skipped without error."""
        run_root = tmp_path / "run6"
        run_root.mkdir()
        # Only create one subdir; others should be silently skipped
        (run_root / "delivery").mkdir()
        (run_root / "delivery" / "readme.md").write_text("# Hello")

        replay_id = _snapshot_run(run_root, "planning")
        snapshot_dir = run_root / "replays" / replay_id
        assert (snapshot_dir / "delivery" / "readme.md").is_file()
        # Non-existent dirs don't appear in snapshot
        assert not (snapshot_dir / "planning").exists()

    def test_two_consecutive_calls_produce_distinct_dirs(self, tmp_path: Path):
        """Two calls with different stages produce distinct snapshot subdirs.

        The replay_id includes stage in the hash, so different stages are
        guaranteed to produce different IDs even within the same second.
        """
        run_root = tmp_path / "run7"
        run_root.mkdir()
        id1 = _snapshot_run(run_root, "planning")
        id2 = _snapshot_run(run_root, "release")  # different stage → different hash
        assert id1 != id2, "Expected different replay IDs for different stages"
        snapshot_parent = run_root / "replays"
        subdirs = {p.name for p in snapshot_parent.iterdir()}
        assert len(subdirs) == 2, f"Expected 2 snapshot dirs, got: {subdirs}"

    def test_all_snapshot_subdirs_in_constant(self, tmp_path: Path):
        """All _SNAPSHOT_SUBDIRS are considered (line 54-64 constant coverage)."""
        from autodev.flows.replay_flow import _SNAPSHOT_SUBDIRS

        run_root = tmp_path / "run8"
        run_root.mkdir()
        for sub in _SNAPSHOT_SUBDIRS:
            d = run_root / sub
            d.mkdir()
            (d / "marker.txt").write_text(sub)

        replay_id = _snapshot_run(run_root, "classification")
        snapshot_dir = run_root / "replays" / replay_id
        for sub in _SNAPSHOT_SUBDIRS:
            assert (snapshot_dir / sub / "marker.txt").is_file(), f"Missing {sub}"


# ===========================================================================
# Snapshot integration via ReplayFlow.replay() (coarse-grained path)
# ===========================================================================

class TestReplayFlowSnapshot:
    """Verify the coarse-grained replay path calls _snapshot_run() correctly."""

    def test_replay_creates_snapshot_under_run_root(self, tmp_path: Path):
        """After replay, a replays/<id>/ dir must exist under the run root."""
        run = _seed_run(tmp_path)
        run_id = run.run_id
        run_root = run.root

        ReplayFlow().replay(run_id=run_id, repo_path=str(tmp_path), from_stage="release")

        replays_dir = run_root / "replays"
        assert replays_dir.is_dir(), "replays/ dir was not created"
        subdirs = list(replays_dir.iterdir())
        assert len(subdirs) >= 1, "No snapshot subdirectory found"

    def test_two_consecutive_replays_two_snapshots(self, tmp_path: Path):
        """Two replays from different stages produce two distinct snapshots.

        Different stage names produce different SHA hashes so this is stable
        even when both replays occur within the same wall-clock second.
        """
        run = _seed_run(tmp_path)
        run_id = run.run_id

        ReplayFlow().replay(run_id=run_id, repo_path=str(tmp_path), from_stage="release")
        ReplayFlow().replay(run_id=run_id, repo_path=str(tmp_path), from_stage="verification")

        replays_dir = run.root / "replays"
        subdirs = list(replays_dir.iterdir())
        assert len(subdirs) == 2, f"Expected 2 snapshots, got {len(subdirs)}"

    def test_snapshot_contains_run_state_json(self, tmp_path: Path):
        """Snapshot dir must contain run_state.json copied from run root."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        ReplayFlow().replay(run_id=run_id, repo_path=str(tmp_path), from_stage="verification")

        replays_dir = run.root / "replays"
        snapshot_dirs = list(replays_dir.iterdir())
        assert snapshot_dirs, "No snapshot dirs"
        assert (snapshot_dirs[0] / "run_state.json").is_file()


# ===========================================================================
# Coarse-grained stage coverage — classification, product, architecture
# ===========================================================================

class TestReplayStages:
    """Cover stage entry points not exercised by existing tests."""

    def test_replay_from_classification(self, tmp_path: Path):
        """Replaying from classification stage runs and notes are recorded."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        replayed = ReplayFlow().replay(
            run_id=run_id, repo_path=str(tmp_path), from_stage="classification"
        )
        notes = replayed.state.errors
        assert any("replayed from stage classification" in n for n in notes)

    def test_replay_from_product(self, tmp_path: Path):
        """Replaying from product stage runs and notes are recorded."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        replayed = ReplayFlow().replay(
            run_id=run_id, repo_path=str(tmp_path), from_stage="product"
        )
        notes = replayed.state.errors
        assert any("replayed from stage product" in n for n in notes)

    def test_replay_from_architecture(self, tmp_path: Path):
        """Replaying from architecture stage runs and notes are recorded."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        replayed = ReplayFlow().replay(
            run_id=run_id, repo_path=str(tmp_path), from_stage="architecture"
        )
        notes = replayed.state.errors
        assert any("replayed from stage architecture" in n for n in notes)

    def test_replay_from_planning(self, tmp_path: Path):
        """Replaying from planning stage runs and notes are recorded."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        replayed = ReplayFlow().replay(
            run_id=run_id, repo_path=str(tmp_path), from_stage="planning"
        )
        notes = replayed.state.errors
        assert any("replayed from stage planning" in n for n in notes)

    def test_replay_from_quality(self, tmp_path: Path):
        """Replaying from quality stage runs and notes are recorded."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        replayed = ReplayFlow().replay(
            run_id=run_id, repo_path=str(tmp_path), from_stage="quality"
        )
        notes = replayed.state.errors
        assert any("replayed from stage quality" in n for n in notes)

    def test_replay_from_verification(self, tmp_path: Path):
        """Replaying from verification stage runs and notes are recorded."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        replayed = ReplayFlow().replay(
            run_id=run_id, repo_path=str(tmp_path), from_stage="verification"
        )
        notes = replayed.state.errors
        assert any("replayed from stage verification" in n for n in notes)

    def test_replay_architecture_fallback_prd(self, tmp_path: Path):
        """Architecture stage creates a fallback PRD when state.prd is None."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        # Clear prd from state so the fallback path (lines 221-224) is hit
        run.state.prd = None
        run.save()

        replayed = ReplayFlow().replay(
            run_id=run_id, repo_path=str(tmp_path), from_stage="architecture"
        )
        # Replay must still complete and record a note
        notes = replayed.state.errors
        assert any("replayed from stage architecture" in n for n in notes)


# ===========================================================================
# Error paths — missing arch / missing plan
# ===========================================================================

class TestReplayErrors:
    """Cover ValueError guard lines 237-242 and 248."""

    def test_planning_without_architecture_raises(self, tmp_path: Path):
        """Replaying 'planning' with no architecture in state raises ValueError."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        # Strip architecture from persisted state
        run.state.architecture = None
        run.save()

        with pytest.raises(ValueError, match="architecture"):
            ReplayFlow().replay(
                run_id=run_id, repo_path=str(tmp_path), from_stage="planning"
            )

    def test_implementation_without_milestone_plan_raises(self, tmp_path: Path):
        """Replaying 'implementation' with no milestone_plan raises ValueError."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        # Strip milestone_plan from persisted state
        run.state.milestone_plan = None
        run.save()

        with pytest.raises(ValueError, match="milestone_plan"):
            ReplayFlow().replay(
                run_id=run_id, repo_path=str(tmp_path), from_stage="implementation"
            )


# ===========================================================================
# Fine-grained from_step resume (lines 109-155)
# ===========================================================================

class TestReplayFromStep:
    """Cover the from_step path in ReplayFlow.replay()."""

    def test_from_step_records_step_note(self, tmp_path: Path):
        """Replaying from a step records an error note mentioning the step."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        # Use a late step that is cheap to replay
        replayed = ReplayFlow().replay(
            run_id=run_id,
            repo_path=str(tmp_path),
            from_step="release_check",
        )

        notes = replayed.state.errors
        assert any("replayed from step release_check" in n for n in notes), (
            f"Expected step note, got: {notes}"
        )

    def test_from_step_saves_state(self, tmp_path: Path):
        """After from_step replay, run state is persisted to disk."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        ReplayFlow().replay(
            run_id=run_id,
            repo_path=str(tmp_path),
            from_step="final_report",
        )

        # Reload from disk and confirm note is present
        reloaded = RunState.load(str(tmp_path), run_id)
        notes = reloaded.state.errors
        assert any("replayed from step final_report" in n for n in notes)

    def test_from_step_returns_run_state(self, tmp_path: Path):
        """from_step path returns a RunState object."""
        run = _seed_run(tmp_path)
        run_id = run.run_id

        result = ReplayFlow().replay(
            run_id=run_id,
            repo_path=str(tmp_path),
            from_step="release_check",
        )

        assert isinstance(result, RunState)
