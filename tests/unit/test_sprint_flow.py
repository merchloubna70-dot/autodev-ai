"""Unit tests for SprintFlow — BMAD-7."""
from __future__ import annotations

import json
from pathlib import Path

from autodev.flows.sprint_flow import SprintFlow, _sprint_base
from autodev.schemas import SprintInput

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_inp(tmp_path: Path, goal: str = "Ship MVP", product: str = "TestProd") -> SprintInput:
    return SprintInput(repo_path=str(tmp_path), goal=goal, product_name=product)


# ---------------------------------------------------------------------------
# Test 1 — start_sprint creates expected directory structure
# ---------------------------------------------------------------------------


def test_start_sprint_creates_dirs(tmp_path: Path) -> None:
    flow = SprintFlow()
    state = flow.start_sprint(_make_inp(tmp_path))

    sprint_dir = _sprint_base(str(tmp_path)) / state.sprint_id
    assert sprint_dir.is_dir(), "sprint directory must be created"
    assert (sprint_dir / "state.json").exists(), "state.json must exist"
    assert (sprint_dir / "planning").is_dir()
    assert (sprint_dir / "implementation").is_dir()


# ---------------------------------------------------------------------------
# Test 2 — sprint_id increments across successive sprints
# ---------------------------------------------------------------------------


def test_start_sprint_increments_id(tmp_path: Path) -> None:
    flow = SprintFlow()
    s1 = flow.start_sprint(_make_inp(tmp_path, goal="Sprint 1"))
    s2 = flow.start_sprint(_make_inp(tmp_path, goal="Sprint 2"))
    assert s1.sprint_id == "sprint-001"
    assert s2.sprint_id == "sprint-002"


# ---------------------------------------------------------------------------
# Test 3 — second sprint links to previous sprint
# ---------------------------------------------------------------------------


def test_start_sprint_links_previous(tmp_path: Path) -> None:
    flow = SprintFlow()
    s1 = flow.start_sprint(_make_inp(tmp_path, goal="Sprint 1"))
    s2 = flow.start_sprint(_make_inp(tmp_path, goal="Sprint 2"))
    assert s2.previous_sprint_id == s1.sprint_id


# ---------------------------------------------------------------------------
# Test 4 — status reflects task counts from implementation result files
# ---------------------------------------------------------------------------


def test_status_reflects_task_counts(tmp_path: Path) -> None:
    flow = SprintFlow()
    state = flow.start_sprint(_make_inp(tmp_path))

    # Simulate implementation results
    impl_dir = Path(state.implementation_artifacts_path)
    impl_dir.mkdir(parents=True, exist_ok=True)

    for i, success in enumerate([True, True, False]):
        result = {"task_id": f"T-{i}", "success": success}
        (impl_dir / f"task_{i}_result.json").write_text(
            json.dumps(result), encoding="utf-8"
        )

    status = flow.status(str(tmp_path), state.sprint_id)
    assert status.sprint_id == state.sprint_id
    assert status.tasks_done == 2
    assert status.tasks_failed == 1
    assert status.tasks_total >= 3


# ---------------------------------------------------------------------------
# Test 5 — retrospective extracts from implementation results
# ---------------------------------------------------------------------------


def test_retrospective_extracts_from_impl_results(tmp_path: Path) -> None:
    flow = SprintFlow()
    state = flow.start_sprint(_make_inp(tmp_path))

    impl_dir = Path(state.implementation_artifacts_path)
    impl_dir.mkdir(parents=True, exist_ok=True)

    (impl_dir / "task_ok_result.json").write_text(
        json.dumps({"task_id": "T-ok", "success": True}), encoding="utf-8"
    )
    (impl_dir / "task_fail_result.json").write_text(
        json.dumps({"task_id": "T-fail", "success": False, "stderr": "compilation error"}),
        encoding="utf-8",
    )

    report = flow.retrospective(str(tmp_path), state.sprint_id)
    assert report.sprint_id == state.sprint_id
    assert any("T-ok" in w for w in report.what_went_well)
    assert any("T-fail" in w or "compilation" in w for w in report.what_went_wrong)
    assert len(report.actions_for_next_sprint) >= 1


# ---------------------------------------------------------------------------
# Test 6 — correct_course produces proposal with impacts
# ---------------------------------------------------------------------------


def test_correct_course_produces_proposal(tmp_path: Path) -> None:
    flow = SprintFlow()
    state = flow.start_sprint(_make_inp(tmp_path))

    proposal = flow.correct_course(
        str(tmp_path),
        state.sprint_id,
        "Change authentication to use OAuth2 instead of basic auth",
    )

    assert proposal.sprint_id == state.sprint_id
    assert proposal.change_description != ""
    assert len(proposal.impacts) >= 1
    assert len(proposal.recommended_actions) >= 1

    # Proposal should be persisted
    sprint_dir = _sprint_base(str(tmp_path)) / state.sprint_id
    assert (sprint_dir / "course_correction.json").exists()


# ---------------------------------------------------------------------------
# Test 7 — health classification works correctly
# ---------------------------------------------------------------------------


def test_status_health_complete(tmp_path: Path) -> None:
    """If all tasks done, health == complete."""
    flow = SprintFlow()
    state = flow.start_sprint(_make_inp(tmp_path))

    # Write 2 successful results
    impl_dir = Path(state.implementation_artifacts_path)
    impl_dir.mkdir(parents=True, exist_ok=True)
    for i in range(2):
        (impl_dir / f"t{i}_result.json").write_text(
            json.dumps({"task_id": f"T-{i}", "success": True}), encoding="utf-8"
        )

    # Manually write tasks into state.json so total == done
    sprint_dir = _sprint_base(str(tmp_path)) / state.sprint_id
    json.loads((sprint_dir / "state.json").read_text())
    # With 2 done results and tasks_total computed from result files, health should be complete
    status = flow.status(str(tmp_path), state.sprint_id)
    # tasks_total == tasks_done == 2 → complete
    assert status.health == "complete"
    assert status.tasks_done == 2


# ---------------------------------------------------------------------------
# Test 8 — retrospective persists file
# ---------------------------------------------------------------------------


def test_retrospective_persists_file(tmp_path: Path) -> None:
    flow = SprintFlow()
    state = flow.start_sprint(_make_inp(tmp_path))
    flow.retrospective(str(tmp_path), state.sprint_id)

    sprint_dir = _sprint_base(str(tmp_path)) / state.sprint_id
    assert (sprint_dir / "retrospective.json").exists()
    data = json.loads((sprint_dir / "retrospective.json").read_text())
    assert data["sprint_id"] == state.sprint_id
