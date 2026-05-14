"""Unit tests for autodev.tui.loaders — pure filesystem loaders, no Textual required."""
from __future__ import annotations

import json
from pathlib import Path

from autodev.tui.loaders import (
    ConversationRecord,
    RunRecord,
    SprintRecord,
    load_conversations,
    load_runs,
    load_sprints,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_run_state(run_id: str = "run-001", **overrides) -> dict:
    base = {
        "run_id": run_id,
        "started_at": "2024-01-15T10:00:00+00:00",
        "finished_at": "2024-01-15T10:30:00+00:00",
        "mode": "dry-run",
        "flow": "project_delivery_flow",
        "repo_path": "/tmp/myproject",
        "languages": ["python"],
        "mock_execution_used": False,
        "errors": [],
        "milestone_plan": {
            "milestones": [
                {"milestone_id": "M1", "title": "Scaffold"},
                {"milestone_id": "M2", "title": "Core"},
            ],
            "tasks": [
                {"task_id": "T1", "milestone_id": "M1", "title": "Init"},
                {"task_id": "T2", "milestone_id": "M2", "title": "Feature"},
            ],
        },
        "quality_gates": [
            {
                "language": "python",
                "outcomes": [
                    {"name": "lint", "status": "passed"},
                    {"name": "tests", "status": "failed"},
                ],
                "overall_status": "failed",
            }
        ],
        "release_check": {"decision": "NotReleaseReady", "reasons": ["tests failed"]},
        "code_review": {
            "severity_findings": [
                {
                    "severity": "major",
                    "category": "correctness",
                    "title": "Missing null check",
                    "detail": "foo can be None",
                    "file_path": "src/foo.py",
                }
            ]
        },
        "security_review": {"severity_findings": []},
        "integration_review": {"severity_findings": []},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# load_runs
# ---------------------------------------------------------------------------


class TestLoadRuns:
    def test_empty_root_returns_empty(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        root.mkdir()
        assert load_runs(root) == []

    def test_no_runs_dir_returns_empty(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        root.mkdir()
        assert load_runs(root) == []

    def test_loads_single_run(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        run_dir = root / "runs" / "run-001"
        _write_json(run_dir / "run_state.json", _make_run_state("run-001"))

        runs = load_runs(root)
        assert len(runs) == 1
        r = runs[0]
        assert isinstance(r, RunRecord)
        assert r.run_id == "run-001"
        assert r.mode == "dry-run"
        assert r.milestone_count == 2
        assert r.task_count == 2
        assert r.finished_at == "2024-01-15T10:30:00+00:00"

    def test_gate_statuses_extracted(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        run_dir = root / "runs" / "run-001"
        _write_json(run_dir / "run_state.json", _make_run_state("run-001"))

        runs = load_runs(root)
        r = runs[0]
        assert r.gate_statuses.get("python/lint") == "passed"
        assert r.gate_statuses.get("python/tests") == "failed"
        assert r.gate_statuses.get("release") == "NotReleaseReady"

    def test_severity_findings_extracted(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        run_dir = root / "runs" / "run-001"
        _write_json(run_dir / "run_state.json", _make_run_state("run-001"))

        runs = load_runs(root)
        r = runs[0]
        assert len(r.severity_findings) == 1
        f = r.severity_findings[0]
        assert f["severity"] == "major"
        assert f["title"] == "Missing null check"

    def test_multiple_runs_sorted_by_name(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        for rid in ("run-003", "run-001", "run-002"):
            _write_json(
                root / "runs" / rid / "run_state.json",
                _make_run_state(rid),
            )

        runs = load_runs(root)
        assert len(runs) == 3
        assert [r.run_id for r in runs] == ["run-001", "run-002", "run-003"]

    def test_missing_state_file_skipped(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        # Create a dir without run_state.json
        ghost_dir = root / "runs" / "ghost-run"
        ghost_dir.mkdir(parents=True)
        # Real run
        _write_json(
            root / "runs" / "run-001" / "run_state.json",
            _make_run_state("run-001"),
        )

        runs = load_runs(root)
        assert len(runs) == 1
        assert runs[0].run_id == "run-001"

    def test_corrupt_json_skipped(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        bad_dir = root / "runs" / "bad-run"
        bad_dir.mkdir(parents=True)
        (bad_dir / "run_state.json").write_text("NOT JSON {{{", encoding="utf-8")

        runs = load_runs(root)
        assert runs == []

    def test_mock_execution_flag(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        _write_json(
            root / "runs" / "mock-run" / "run_state.json",
            _make_run_state("mock-run", mock_execution_used=True),
        )
        runs = load_runs(root)
        assert runs[0].mock_execution_used is True

    def test_run_with_errors(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        _write_json(
            root / "runs" / "err-run" / "run_state.json",
            _make_run_state("err-run", errors=["timeout", "exec failed"]),
        )
        runs = load_runs(root)
        assert len(runs[0].errors) == 2

    def test_no_milestone_plan(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        state = _make_run_state("no-plan")
        state.pop("milestone_plan")
        _write_json(root / "runs" / "no-plan" / "run_state.json", state)

        runs = load_runs(root)
        assert runs[0].milestone_count == 0
        assert runs[0].task_count == 0

    def test_run_dir_attribute_set(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        _write_json(
            root / "runs" / "run-001" / "run_state.json",
            _make_run_state("run-001"),
        )
        runs = load_runs(root)
        assert runs[0].run_dir == root / "runs" / "run-001"


# ---------------------------------------------------------------------------
# load_sprints
# ---------------------------------------------------------------------------


def _make_sprint_state(sprint_id: str, **overrides) -> dict:
    base = {
        "sprint_id": sprint_id,
        "goal": "Ship MVP",
        "started_at": "2024-02-01T00:00:00+00:00",
        "tasks": [
            {"task_id": "T1", "status": "completed"},
            {"task_id": "T2", "status": "completed"},
            {"task_id": "T3", "status": "pending"},
        ],
    }
    base.update(overrides)
    return base


def _make_retro(sprint_id: str) -> dict:
    return {
        "sprint_id": sprint_id,
        "what_went_well": ["CI was green", "Good collaboration"],
        "what_went_wrong": ["Scope creep"],
        "actions_for_next_sprint": ["Tighten scope"],
    }


class TestLoadSprints:
    def test_no_sprint_dir_returns_empty(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        root.mkdir()
        assert load_sprints(root) == []

    def test_loads_sprint_with_retro(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        sprint_dir = root.parent / ".autodev" / "sprints" / "sprint-001"
        sprint_dir.mkdir(parents=True)
        _write_json(sprint_dir / "state.json", _make_sprint_state("sprint-001"))
        _write_json(sprint_dir / "retrospective.json", _make_retro("sprint-001"))

        sprints = load_sprints(root)
        assert len(sprints) == 1
        s = sprints[0]
        assert isinstance(s, SprintRecord)
        assert s.sprint_id == "sprint-001"
        assert s.goal == "Ship MVP"
        assert s.tasks_total == 3
        assert s.tasks_done == 2
        assert len(s.what_went_well) == 2
        assert len(s.actions) == 1

    def test_progress_pct(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        sprint_dir = root.parent / ".autodev" / "sprints" / "sprint-001"
        sprint_dir.mkdir(parents=True)
        _write_json(sprint_dir / "state.json", _make_sprint_state("sprint-001"))
        _write_json(sprint_dir / "retrospective.json", {})

        sprints = load_sprints(root)
        # 2/3 done
        assert abs(sprints[0].progress_pct - 66.666) < 1.0

    def test_health_complete_when_all_done(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        sprint_dir = root.parent / ".autodev" / "sprints" / "sprint-002"
        sprint_dir.mkdir(parents=True)
        all_done = [{"task_id": f"T{i}", "status": "completed"} for i in range(4)]
        _write_json(sprint_dir / "state.json", _make_sprint_state("sprint-002", tasks=all_done))
        _write_json(sprint_dir / "retrospective.json", {})

        sprints = load_sprints(root)
        assert sprints[0].health == "complete"

    def test_health_blocked_when_failures(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        sprint_dir = root.parent / ".autodev" / "sprints" / "sprint-003"
        sprint_dir.mkdir(parents=True)
        tasks = [
            {"task_id": "T1", "status": "failed"},
            {"task_id": "T2", "status": "pending"},
        ]
        _write_json(sprint_dir / "state.json", _make_sprint_state("sprint-003", tasks=tasks))
        _write_json(sprint_dir / "retrospective.json", {})

        sprints = load_sprints(root)
        assert sprints[0].health == "blocked"

    def test_fallback_to_root_sprints_dir(self, tmp_path: Path) -> None:
        """load_sprints falls back to root/sprints if .autodev/sprints missing."""
        root = tmp_path / ".dev-factory"
        sprint_dir = root / "sprints" / "sprint-001"
        sprint_dir.mkdir(parents=True)
        _write_json(sprint_dir / "state.json", _make_sprint_state("sprint-001"))
        _write_json(sprint_dir / "retrospective.json", {})

        sprints = load_sprints(root)
        assert len(sprints) == 1


# ---------------------------------------------------------------------------
# load_conversations
# ---------------------------------------------------------------------------


def _make_conversation(conv_id: str, n_msgs: int = 3) -> dict:
    messages = []
    for i in range(n_msgs):
        messages.append({
            "message_id": f"msg-{i}",
            "role": "agent",
            "parts": [{"kind": "text", "text": f"Agent response {i} about the architecture."}],
            "created_at": "2024-03-01T00:00:00+00:00",
        })
    return {
        "conversation": {
            "conversation_id": conv_id,
            "task_id": "task-42",
            "participating_cards": ["architect", "security-reviewer", "perf-reviewer"],
            "messages": messages,
        },
        "synthesis": {"message_id": "synth-1", "role": "agent", "parts": []},
    }


class TestLoadConversations:
    def test_no_roundtables_dir_returns_empty(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        root.mkdir()
        assert load_conversations(root) == []

    def test_loads_single_conversation(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        rt_dir = root / "roundtables"
        rt_dir.mkdir(parents=True)
        _write_json(rt_dir / "conv-abc.json", _make_conversation("conv-abc", n_msgs=5))

        convos = load_conversations(root)
        assert len(convos) == 1
        c = convos[0]
        assert isinstance(c, ConversationRecord)
        assert c.conversation_id == "conv-abc"
        assert c.task_id == "task-42"
        assert c.message_count == 5
        assert len(c.participating_cards) == 3
        assert "Agent response 0" in c.preview

    def test_preview_truncated_to_120(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        rt_dir = root / "roundtables"
        rt_dir.mkdir(parents=True)
        long_text = "X" * 300
        conv_data = {
            "conversation": {
                "conversation_id": "long-conv",
                "task_id": "t1",
                "participating_cards": [],
                "messages": [
                    {
                        "message_id": "m1",
                        "role": "agent",
                        "parts": [{"kind": "text", "text": long_text}],
                    }
                ],
            }
        }
        _write_json(rt_dir / "long-conv.json", conv_data)

        convos = load_conversations(root)
        assert len(convos[0].preview) == 120

    def test_multiple_conversations_sorted(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        rt_dir = root / "roundtables"
        rt_dir.mkdir(parents=True)
        for cid in ("c003", "c001", "c002"):
            _write_json(rt_dir / f"{cid}.json", _make_conversation(cid))

        convos = load_conversations(root)
        assert [c.conversation_id for c in convos] == ["c001", "c002", "c003"]

    def test_corrupt_json_skipped(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        rt_dir = root / "roundtables"
        rt_dir.mkdir(parents=True)
        (rt_dir / "bad.json").write_text("{{{{", encoding="utf-8")
        _write_json(rt_dir / "good.json", _make_conversation("good-conv"))

        convos = load_conversations(root)
        assert len(convos) == 1

    def test_file_path_attribute(self, tmp_path: Path) -> None:
        root = tmp_path / ".dev-factory"
        rt_dir = root / "roundtables"
        rt_dir.mkdir(parents=True)
        _write_json(rt_dir / "conv-x.json", _make_conversation("conv-x"))

        convos = load_conversations(root)
        assert convos[0].file_path == rt_dir / "conv-x.json"
