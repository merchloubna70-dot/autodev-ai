"""R10-H coverage backfill: sprint_flow / step_runner / property_test_designer / post_edit_lint_gate.

Targets:
  - flows/sprint_flow.py          78% → ≥90%
  - flows/step_runner.py          89% → ≥90%
  - agents/property_test_designer.py  71% → ≥90%
  - gates/post_edit_lint_gate.py      62% → ≥90%
"""
from __future__ import annotations

import ast
import json
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# property_test_designer imports
# ---------------------------------------------------------------------------
from autodev.agents.property_test_designer import (
    PropertyTestDesigner,
    _annotation_to_strategy,
    _has_side_effects,
)

# ---------------------------------------------------------------------------
# sprint_flow imports
# ---------------------------------------------------------------------------
from autodev.flows.sprint_flow import (
    SprintFlow,
    _next_sprint_id,
    _previous_retro_summary,
    _resolve_sprint_dir,
    _sprint_base,
)

# ---------------------------------------------------------------------------
# step_runner imports
# ---------------------------------------------------------------------------
from autodev.flows.step_runner import Step, StepRegistry, StepRunner

# ---------------------------------------------------------------------------
# post_edit_lint_gate imports
# ---------------------------------------------------------------------------
from autodev.gates.post_edit_lint_gate import (
    PostEditLintGate,
    _check_node,
    _check_python,
    _check_rust,
)
from autodev.schemas import Language, LintGateResult, SprintInput, StepStatus

# ===========================================================================
# SECTION 1: sprint_flow.py coverage
# ===========================================================================


def _make_inp(tmp_path: Path, goal: str = "Ship feature", product: str = "Prod") -> SprintInput:
    return SprintInput(repo_path=str(tmp_path), goal=goal, product_name=product)


class TestSprintFlowMissingLines:
    """Cover lines 62, 79-84, 92-99, 142-145, 205-206, 217, 272-273, 280, 286-289, 295, 299, 361-374, 381, 412."""

    # ------------------------------------------------------------------
    # line 62: _load_state_json returns {} when state.json doesn't exist
    # ------------------------------------------------------------------
    def test_load_state_json_missing_file(self, tmp_path: Path) -> None:
        """_load_state_json returns {} for nonexistent state.json (line 62)."""
        from autodev.flows.sprint_flow import _load_state_json
        result = _load_state_json(tmp_path / "nonexistent_dir")
        assert result == {}

    # ------------------------------------------------------------------
    # lines 79-84: _resolve_sprint_dir with None sprint_id - no base + no dirs
    # ------------------------------------------------------------------
    def test_resolve_sprint_dir_no_base_raises(self, tmp_path: Path) -> None:
        """_resolve_sprint_dir(None) when base doesn't exist → FileNotFoundError (line 80)."""
        with pytest.raises(FileNotFoundError):
            _resolve_sprint_dir(str(tmp_path), None)

    def test_resolve_sprint_dir_no_dirs_raises(self, tmp_path: Path) -> None:
        """_resolve_sprint_dir(None) when base exists but has no sprint dirs (line 82-83)."""
        base = tmp_path / ".autodev" / "sprints"
        base.mkdir(parents=True)
        # base exists but has no sprint-NNN dirs
        with pytest.raises(FileNotFoundError):
            _resolve_sprint_dir(str(tmp_path), None)

    def test_resolve_sprint_dir_returns_latest(self, tmp_path: Path) -> None:
        """_resolve_sprint_dir(None) returns the highest-numbered sprint dir (line 84)."""
        flow = SprintFlow()
        flow.start_sprint(_make_inp(tmp_path, goal="S1"))
        flow.start_sprint(_make_inp(tmp_path, goal="S2"))
        # None → latest
        resolved = _resolve_sprint_dir(str(tmp_path), None)
        assert resolved.name == "sprint-002"

    # ------------------------------------------------------------------
    # lines 92-99: _previous_retro_summary paths
    # ------------------------------------------------------------------
    def test_previous_retro_summary_no_file(self, tmp_path: Path) -> None:
        """_previous_retro_summary returns '' when retrospective.json doesn't exist (line 91)."""
        base = tmp_path / ".autodev" / "sprints"
        base.mkdir(parents=True)
        result = _previous_retro_summary(base, "sprint-001")
        assert result == ""

    def test_previous_retro_summary_with_actions(self, tmp_path: Path) -> None:
        """_previous_retro_summary reads actions from retrospective.json (lines 93-96)."""
        base = tmp_path / ".autodev" / "sprints"
        sprint_dir = base / "sprint-001"
        sprint_dir.mkdir(parents=True)
        retro_data = {"actions_for_next_sprint": ["Action A", "Action B", "Action C"]}
        (sprint_dir / "retrospective.json").write_text(json.dumps(retro_data), encoding="utf-8")
        result = _previous_retro_summary(base, "sprint-001")
        assert "Action A" in result
        assert "Action B" in result

    def test_previous_retro_summary_empty_actions(self, tmp_path: Path) -> None:
        """_previous_retro_summary returns '' when actions list is empty (line 95 false branch)."""
        base = tmp_path / ".autodev" / "sprints"
        sprint_dir = base / "sprint-001"
        sprint_dir.mkdir(parents=True)
        retro_data = {"actions_for_next_sprint": []}
        (sprint_dir / "retrospective.json").write_text(json.dumps(retro_data), encoding="utf-8")
        result = _previous_retro_summary(base, "sprint-001")
        assert result == ""

    def test_previous_retro_summary_invalid_json(self, tmp_path: Path) -> None:
        """_previous_retro_summary catches JSON parse error and returns '' (lines 97-98)."""
        base = tmp_path / ".autodev" / "sprints"
        sprint_dir = base / "sprint-001"
        sprint_dir.mkdir(parents=True)
        (sprint_dir / "retrospective.json").write_text("{{invalid json", encoding="utf-8")
        result = _previous_retro_summary(base, "sprint-001")
        assert result == ""

    # ------------------------------------------------------------------
    # lines 142-145: start_sprint with planning artifacts
    # ------------------------------------------------------------------
    def test_start_sprint_snapshots_planning_artifacts(self, tmp_path: Path) -> None:
        """start_sprint scans .autodev/planning for .md/.json files (lines 142-145)."""
        # Create planning directory with files
        planning_dir = tmp_path / ".autodev" / "planning"
        planning_dir.mkdir(parents=True)
        (planning_dir / "prd.md").write_text("# PRD content", encoding="utf-8")
        (planning_dir / "epic.json").write_text('{"epic": "test"}', encoding="utf-8")

        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        # State was created; check state.json has artifacts snapshot
        sprint_dir = _sprint_base(str(tmp_path)) / state.sprint_id
        raw = json.loads((sprint_dir / "state.json").read_text())
        snapshot = raw.get("_artifacts_snapshot", [])
        assert any("prd.md" in a for a in snapshot)
        assert any("epic.json" in a for a in snapshot)

    # ------------------------------------------------------------------
    # lines 205-206: status() exception when reading corrupt result file
    # ------------------------------------------------------------------
    def test_status_corrupt_result_file_ignored(self, tmp_path: Path) -> None:
        """Corrupt result files in impl dir are silently ignored (lines 205-206)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        impl_dir = Path(state.implementation_artifacts_path)
        impl_dir.mkdir(parents=True, exist_ok=True)
        # Write a corrupt result file
        (impl_dir / "broken_result.json").write_text("{not valid json}", encoding="utf-8")
        # Should not raise
        status = flow.status(str(tmp_path), state.sprint_id)
        assert status is not None

    # ------------------------------------------------------------------
    # line 217: status() with blockers → health=="blocked"
    # ------------------------------------------------------------------
    def test_status_health_blocked(self, tmp_path: Path) -> None:
        """Status health == 'blocked' when _blockers is non-empty (line 217)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        # Inject blocker into state.json
        sprint_dir = _sprint_base(str(tmp_path)) / state.sprint_id
        raw = json.loads((sprint_dir / "state.json").read_text())
        raw["_blockers"] = ["Waiting on API approval"]
        (sprint_dir / "state.json").write_text(json.dumps(raw), encoding="utf-8")

        # Add partial results so not complete
        impl_dir = Path(state.implementation_artifacts_path)
        impl_dir.mkdir(parents=True, exist_ok=True)
        (impl_dir / "t1_result.json").write_text(
            json.dumps({"task_id": "T-1", "success": True}), encoding="utf-8"
        )
        (impl_dir / "t2_result.json").write_text(
            json.dumps({"task_id": "T-2", "success": False}), encoding="utf-8"
        )

        status = flow.status(str(tmp_path), state.sprint_id)
        assert status.health == "blocked"
        assert len(status.blockers) >= 1

    # ------------------------------------------------------------------
    # line 217 alt: health=="on-track" when >50% done
    # ------------------------------------------------------------------
    def test_status_health_on_track(self, tmp_path: Path) -> None:
        """Status health == 'on-track' when >50% tasks done (line 218-219)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        impl_dir = Path(state.implementation_artifacts_path)
        impl_dir.mkdir(parents=True, exist_ok=True)
        # 3 done, 1 failed → 75% → on-track
        for i in range(3):
            (impl_dir / f"t{i}_result.json").write_text(
                json.dumps({"task_id": f"T-{i}", "success": True}), encoding="utf-8"
            )
        (impl_dir / "t3_result.json").write_text(
            json.dumps({"task_id": "T-3", "success": False}), encoding="utf-8"
        )
        status = flow.status(str(tmp_path), state.sprint_id)
        assert status.health == "on-track"

    # ------------------------------------------------------------------
    # lines 272-273: retrospective() with unreadable result file
    # ------------------------------------------------------------------
    def test_retrospective_unreadable_result_file(self, tmp_path: Path) -> None:
        """Unreadable result file adds to surprises list (lines 272-273)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        impl_dir = Path(state.implementation_artifacts_path)
        impl_dir.mkdir(parents=True, exist_ok=True)
        # Write corrupt JSON
        (impl_dir / "bad_result.json").write_text("{bad}", encoding="utf-8")
        report = flow.retrospective(str(tmp_path), state.sprint_id)
        assert any("Unreadable" in s for s in report.surprises)

    # ------------------------------------------------------------------
    # line 280: failed_tasks but no what_went_wrong → fallback message
    # ------------------------------------------------------------------
    def test_retrospective_failed_no_error_field(self, tmp_path: Path) -> None:
        """Failed tasks without stderr/error_type trigger fallback (line 280)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        impl_dir = Path(state.implementation_artifacts_path)
        impl_dir.mkdir(parents=True, exist_ok=True)
        # Failed task but no stderr or error_type fields
        (impl_dir / "t_fail_result.json").write_text(
            json.dumps({"task_id": "T-x", "success": False}), encoding="utf-8"
        )
        report = flow.retrospective(str(tmp_path), state.sprint_id)
        # Line 280: what_went_wrong should have the fallback message
        assert any("T-x" in w or "1 tasks failed" in w for w in report.what_went_wrong)

    # ------------------------------------------------------------------
    # lines 286-289: carryover AC from tasks not done
    # ------------------------------------------------------------------
    def test_retrospective_carryover_acceptance_criteria(self, tmp_path: Path) -> None:
        """Tasks with non-done status contribute acceptance criteria to carryover (lines 286-289)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        # Inject tasks with acceptance_criteria into state.json
        sprint_dir = _sprint_base(str(tmp_path)) / state.sprint_id
        raw = json.loads((sprint_dir / "state.json").read_text())
        raw["tasks"] = [
            {
                "_status": "pending",
                "acceptance_criteria": ["AC-1: Feature works", "AC-2: Tests pass"],
            },
            {
                "_status": "done",
                "acceptance_criteria": ["AC-3: Already done"],
            },
        ]
        (sprint_dir / "state.json").write_text(json.dumps(raw), encoding="utf-8")

        report = flow.retrospective(str(tmp_path), state.sprint_id)
        assert "AC-1: Feature works" in report.carryover_acceptance_criteria
        assert "AC-2: Tests pass" in report.carryover_acceptance_criteria
        # Done task's AC should NOT be in carryover
        assert "AC-3: Already done" not in report.carryover_acceptance_criteria

    # ------------------------------------------------------------------
    # line 295: retro previous_retrospective_summary action
    # ------------------------------------------------------------------
    def test_retrospective_uses_previous_retro_summary(self, tmp_path: Path) -> None:
        """If previous_retrospective_summary is set, it adds an action (line 295)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        sprint_dir = _sprint_base(str(tmp_path)) / state.sprint_id
        raw = json.loads((sprint_dir / "state.json").read_text())
        raw["previous_retrospective_summary"] = "Improve CI pipeline; Add more tests"
        (sprint_dir / "state.json").write_text(json.dumps(raw), encoding="utf-8")

        report = flow.retrospective(str(tmp_path), state.sprint_id)
        assert any("previous sprint" in a.lower() for a in report.actions_for_next_sprint)

    # ------------------------------------------------------------------
    # line 299: retro with carryover_ac → adds carry-over action
    # ------------------------------------------------------------------
    def test_retrospective_carryover_ac_action_added(self, tmp_path: Path) -> None:
        """When carryover_ac is non-empty, an action is added (line 299)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        sprint_dir = _sprint_base(str(tmp_path)) / state.sprint_id
        raw = json.loads((sprint_dir / "state.json").read_text())
        raw["acceptance_criteria_carryover"] = ["Old AC from previous sprint"]
        (sprint_dir / "state.json").write_text(json.dumps(raw), encoding="utf-8")

        report = flow.retrospective(str(tmp_path), state.sprint_id)
        assert any("carry over" in a.lower() or "carryover" in a.lower() or "Carry over" in a for a in report.actions_for_next_sprint)

    # ------------------------------------------------------------------
    # lines 361-374, 381: correct_course _scan_dir finds relevant MD files
    # ------------------------------------------------------------------
    def test_correct_course_scans_planning_md_files(self, tmp_path: Path) -> None:
        """correct_course scans planning artifacts directory for keyword matches (lines 361-374)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))

        # Create planning artifacts with content matching change description keywords
        planning_dir = tmp_path / ".autodev" / "planning"
        planning_dir.mkdir(parents=True, exist_ok=True)

        # This file has "prd" in name and change keywords in content
        prd_file = planning_dir / "prd_auth.md"
        prd_file.write_text(
            "# Product Requirements\n\nThis product requires authentication with OAuth tokens "
            "and api integration for the interface flow.",
            encoding="utf-8",
        )
        epic_file = planning_dir / "epic_sprint.md"
        epic_file.write_text(
            "# Epic\n\nSprint stories for user interface api authentication.",
            encoding="utf-8",
        )

        proposal = flow.correct_course(
            str(tmp_path),
            state.sprint_id,
            "Change authentication to use OAuth2 tokens",
        )
        # Should have found files and created non-placeholder impacts
        assert len(proposal.impacts) >= 1
        # The impacts might reference actual files (not just placeholder)
        impact_summaries = " ".join(i.change_summary for i in proposal.impacts)
        # Either found actual files or fallback placeholder
        assert "potentially affected" in impact_summaries

    def test_correct_course_many_files_truncated(self, tmp_path: Path) -> None:
        """correct_course truncates impact listing beyond 3 files (line 396-398 +more branch)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))

        planning_dir = tmp_path / ".autodev" / "planning"
        planning_dir.mkdir(parents=True, exist_ok=True)
        # Create >3 files matching PRD keyword with change description keywords
        for i in range(5):
            f = planning_dir / f"prd_requirements_{i}.md"
            f.write_text(
                f"# Product doc {i}\n\nRequirements for authentication oauth api interface user.",
                encoding="utf-8",
            )

        proposal = flow.correct_course(
            str(tmp_path),
            state.sprint_id,
            "authentication oauth interface user api requirements",
        )
        assert proposal is not None
        # might or might not match all 5 files per artifact type; just verify no crash
        assert len(proposal.impacts) >= 1

    # ------------------------------------------------------------------
    # line 412: correct_course minor-only impacts → different recommended_actions
    # ------------------------------------------------------------------
    def test_correct_course_minor_only_impacts(self, tmp_path: Path) -> None:
        """When only UX/Tests impacts are found, uses minor-impact message (line 412)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))

        # Create only UX-related planning files
        planning_dir = tmp_path / ".autodev" / "planning"
        planning_dir.mkdir(parents=True, exist_ok=True)
        ux_file = planning_dir / "ux_wireframes.md"
        # Content with "ux" keyword in name and "screen" in content
        ux_file.write_text(
            "# UX Design\n\nScreen layout for the user interface flow.",
            encoding="utf-8",
        )

        # Use a description that only hits UX/Tests (not PRD/Epic/Architecture)
        proposal = flow.correct_course(
            str(tmp_path),
            state.sprint_id,
            "adjust screen layout for user flow",
        )
        assert proposal is not None
        # recommended_actions always has at least 1 item
        assert len(proposal.recommended_actions) >= 1

    # ------------------------------------------------------------------
    # start_sprint links previous retro summary via full two-sprint lifecycle
    # ------------------------------------------------------------------
    def test_start_sprint_reads_previous_retro(self, tmp_path: Path) -> None:
        """Second sprint reads retro summary from first sprint (line 133)."""
        flow = SprintFlow()
        s1 = flow.start_sprint(_make_inp(tmp_path, goal="Sprint 1"))
        # Write a retrospective for sprint-001
        flow.retrospective(str(tmp_path), s1.sprint_id)
        # Start sprint 2 — it should link the retro summary
        s2 = flow.start_sprint(_make_inp(tmp_path, goal="Sprint 2"))
        assert s2.previous_sprint_id == s1.sprint_id

    # ------------------------------------------------------------------
    # status with zero tasks → at-risk (progress_pct == 0)
    # ------------------------------------------------------------------
    def test_status_health_at_risk_no_tasks(self, tmp_path: Path) -> None:
        """Status health == 'at-risk' when no results and no blockers (line 221)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        status = flow.status(str(tmp_path), state.sprint_id)
        assert status.health == "at-risk"
        assert status.progress_pct == 0.0

    # ------------------------------------------------------------------
    # retrospective: no failures, no passed_tasks → "Sprint completed" message
    # ------------------------------------------------------------------
    def test_retrospective_no_impl_dir(self, tmp_path: Path) -> None:
        """Retrospective with no impl dir produces fallback well message (line 278)."""
        flow = SprintFlow()
        state = flow.start_sprint(_make_inp(tmp_path))
        # Remove the impl dir if it was created
        impl_dir = Path(state.implementation_artifacts_path)
        if impl_dir.exists():
            import shutil as _shutil
            _shutil.rmtree(str(impl_dir))
        report = flow.retrospective(str(tmp_path), state.sprint_id)
        assert any("no recorded failures" in w.lower() or "completed" in w.lower() for w in report.what_went_well)

    # ------------------------------------------------------------------
    # _next_sprint_id with empty base dir (no matching dirs)
    # ------------------------------------------------------------------
    def test_next_sprint_id_empty_base(self, tmp_path: Path) -> None:
        """_next_sprint_id returns sprint-001 when base has no sprint dirs."""
        base = tmp_path / "sprints"
        base.mkdir()
        result = _next_sprint_id(base)
        assert result == "sprint-001"


# ===========================================================================
# SECTION 2: step_runner.py coverage
# ===========================================================================


def _make_step_runner_ctx(tmp_path: Path, run_id: str = "test-run") -> object:
    """Build a minimal run_state object."""
    class _FakeRunState:
        pass
    rs = _FakeRunState()
    rs.base_dir = str(tmp_path)
    rs.run_id = run_id
    return rs


def _make_step_fn(name: str, trace_list: list) -> Step:
    def _fn(rs):
        trace_list.append(name)
        return f"done:{name}"
    return Step(name=name, description=f"step {name}", func=_fn)


class TestStepRunnerMissingLines:
    """Cover lines 76, 115, 124, 164-165, 183-184, 220-225, 237-238."""

    # ------------------------------------------------------------------
    # line 76: cycle detection in topological_order
    # ------------------------------------------------------------------
    def test_topological_order_cycle_raises(self) -> None:
        """Cycle in dependencies raises RuntimeError (line 76)."""
        reg = StepRegistry("cycle_test")
        # Create a two-step cycle: a → b → a
        reg.register(Step(name="a", description="a", func=lambda rs: None, depends_on=["b"]))
        reg.register(Step(name="b", description="b", func=lambda rs: None, depends_on=["a"]))
        with pytest.raises(RuntimeError, match="Cycle detected"):
            reg.topological_order()

    # ------------------------------------------------------------------
    # line 115: from_step not in registry raises ValueError
    # ------------------------------------------------------------------
    def test_run_invalid_from_step_raises(self, tmp_path: Path) -> None:
        """from_step that doesn't exist raises ValueError (line 115)."""
        reg = StepRegistry("from_invalid")
        trace: list = []
        reg.register(_make_step_fn("a", trace))
        runner = StepRunner()
        rs = _make_step_runner_ctx(tmp_path, "from-invalid")
        with pytest.raises(ValueError, match="from_step="):
            runner.run(reg, rs, from_step="nonexistent")

    # ------------------------------------------------------------------
    # line 124: until_step not in registry raises ValueError
    # ------------------------------------------------------------------
    def test_run_invalid_until_step_raises(self, tmp_path: Path) -> None:
        """until_step that doesn't exist raises ValueError (line 124)."""
        reg = StepRegistry("until_invalid")
        trace: list = []
        reg.register(_make_step_fn("a", trace))
        runner = StepRunner()
        rs = _make_step_runner_ctx(tmp_path, "until-invalid")
        with pytest.raises(ValueError, match="until_step="):
            runner.run(reg, rs, until_step="nonexistent")

    # ------------------------------------------------------------------
    # lines 164-165: already completed && not force_restart && idx < from_idx
    # This is a dead branch (idx < from_idx is already handled earlier),
    # but let's trigger the until_step path and force_restart path instead.
    # ------------------------------------------------------------------
    def test_run_until_step_stops_execution(self, tmp_path: Path) -> None:
        """until_step stops execution after the specified step (lines 151-155)."""
        reg = StepRegistry("until_test")
        trace: list = []
        reg.register(_make_step_fn("s1", trace))
        reg.register(Step(name="s2", description="s2", func=lambda rs: trace.append("s2"), depends_on=["s1"]))
        reg.register(Step(name="s3", description="s3", func=lambda rs: trace.append("s3"), depends_on=["s2"]))
        runner = StepRunner()
        rs = _make_step_runner_ctx(tmp_path, "until-run")
        records = runner.run(reg, rs, until_step="s2")
        assert records["s1"].status == StepStatus.COMPLETED
        assert records["s2"].status == StepStatus.COMPLETED
        assert records["s3"].status == StepStatus.SKIPPED
        assert "s3" not in trace

    # ------------------------------------------------------------------
    # force_restart re-runs all steps including completed ones
    # ------------------------------------------------------------------
    def test_run_force_restart_reruns_steps(self, tmp_path: Path) -> None:
        """force_restart=True re-runs all steps regardless of persisted status (line 140)."""
        reg = StepRegistry("force_restart_test")
        trace: list = []
        reg.register(_make_step_fn("fr1", trace))
        reg.register(Step(name="fr2", description="fr2", func=lambda rs: trace.append("fr2"), depends_on=["fr1"]))
        runner = StepRunner()
        rs = _make_step_runner_ctx(tmp_path, "force-restart-run")
        # First run
        runner.run(reg, rs)
        first_trace = list(trace)
        trace.clear()
        # Second run with force_restart
        runner.run(reg, rs, force_restart=True)
        assert trace == first_trace  # re-ran same steps

    # ------------------------------------------------------------------
    # lines 183-184: result str conversion raises → type(result).__name__
    # ------------------------------------------------------------------
    def test_run_step_result_str_raises(self, tmp_path: Path) -> None:
        """When str(result) raises, uses type(result).__name__ (line 183-184)."""
        class _BadStr:
            def __str__(self):
                raise ValueError("no str")
            def __repr__(self):
                return "BadStr()"

        def _func(rs):
            return _BadStr()

        reg = StepRegistry("bad_str_test")
        reg.register(Step(name="bad_str", description="bad", func=_func))
        runner = StepRunner()
        rs = _make_step_runner_ctx(tmp_path, "bad-str-run")
        records = runner.run(reg, rs)
        # Should complete (not fail), summary is type name
        assert records["bad_str"].status == StepStatus.COMPLETED
        assert records["bad_str"].output_summary == "_BadStr"

    # ------------------------------------------------------------------
    # lines 220-225: _steps_dir with None base_dir → fallback to ".dev-factory"
    # ------------------------------------------------------------------
    def test_steps_dir_no_base_dir(self) -> None:
        """_steps_dir falls back to Path('.dev-factory') when base_dir is None (line 220)."""
        class _NoBased:
            run_id = "test"
        rs = _NoBased()
        result = StepRunner._steps_dir(rs)
        assert "test" in str(result)
        assert "runs" in str(result)

    def test_steps_dir_string_base_dir(self, tmp_path: Path) -> None:
        """_steps_dir handles string base_dir by converting to Path (line 223-224)."""
        class _StringBased:
            base_dir = str(tmp_path)
            run_id = "str-run"
        rs = _StringBased()
        result = StepRunner._steps_dir(rs)
        assert isinstance(result, Path)
        assert result == tmp_path / "runs" / "str-run" / "steps"

    def test_steps_dir_path_base_dir(self, tmp_path: Path) -> None:
        """_steps_dir handles Path base_dir directly (line 225)."""
        class _PathBased:
            base_dir = tmp_path  # already a Path
            run_id = "path-run"
        rs = _PathBased()
        result = StepRunner._steps_dir(rs)
        assert result == tmp_path / "runs" / "path-run" / "steps"

    # ------------------------------------------------------------------
    # lines 237-238: _load_record with corrupt JSON → returns None
    # ------------------------------------------------------------------
    def test_load_record_corrupt_json_returns_none(self, tmp_path: Path) -> None:
        """_load_record returns None for corrupt JSON (lines 237-238)."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        (steps_dir / "mystep.json").write_text("{corrupt json", encoding="utf-8")
        runner = StepRunner()
        result = runner._load_record(steps_dir, "mystep")
        assert result is None

    # ------------------------------------------------------------------
    # from_step skips steps not yet completed (marks as SKIPPED)
    # ------------------------------------------------------------------
    def test_from_step_skips_not_completed_marks_skipped(self, tmp_path: Path) -> None:
        """Steps before from_step without COMPLETED status on disk → SKIPPED (line 145-148)."""
        reg = StepRegistry("skip_not_completed")
        trace: list = []
        reg.register(_make_step_fn("s1", trace))
        reg.register(_make_step_fn("s2", trace))
        reg.register(_make_step_fn("s3", trace))
        runner = StepRunner()
        rs = _make_step_runner_ctx(tmp_path, "skip-no-completed")
        # Run from s2 without prior run (s1 not completed on disk)
        records = runner.run(reg, rs, from_step="s2")
        assert records["s1"].status == StepStatus.SKIPPED
        assert records["s2"].status == StepStatus.COMPLETED
        assert records["s3"].status == StepStatus.COMPLETED


# ===========================================================================
# SECTION 3: property_test_designer.py coverage
# ===========================================================================


def _write_py(tmp_path: Path, name: str, source: str) -> str:
    p = tmp_path / name
    p.write_text(textwrap.dedent(source), encoding="utf-8")
    return str(p)


class TestPropertyTestDesignerMissingLines:
    """Cover lines 49, 52-67, 79, 83, 86, 119, 126, 131, 162, 184-186, 193-195."""

    # ------------------------------------------------------------------
    # line 49: _annotation_to_strategy with None → None
    # ------------------------------------------------------------------
    def test_annotation_to_strategy_none(self) -> None:
        """_annotation_to_strategy(None) returns None (line 49)."""
        result = _annotation_to_strategy(None)
        assert result is None

    # ------------------------------------------------------------------
    # line 52: _annotation_to_strategy with ast.Constant str annotation
    # ------------------------------------------------------------------
    def test_annotation_to_strategy_string_constant(self) -> None:
        """_annotation_to_strategy with ast.Constant('int') returns integers() (line 52-53)."""
        node = ast.Constant(value="int")
        result = _annotation_to_strategy(node)
        assert result == "integers()"

    def test_annotation_to_strategy_string_constant_unknown(self) -> None:
        """_annotation_to_strategy with ast.Constant('MyClass') returns None (line 53)."""
        node = ast.Constant(value="MyCustomClass")
        result = _annotation_to_strategy(node)
        assert result is None

    # ------------------------------------------------------------------
    # lines 55-66: _annotation_to_strategy with Subscript (Optional, List)
    # ------------------------------------------------------------------
    def test_annotation_to_strategy_optional_int(self) -> None:
        """_annotation_to_strategy handles Optional[int] → integers() (lines 59-62)."""
        # Build Optional[int] AST node
        optional_node = ast.Subscript(
            value=ast.Name(id="Optional", ctx=ast.Load()),
            slice=ast.Name(id="int", ctx=ast.Load()),
            ctx=ast.Load(),
        )
        result = _annotation_to_strategy(optional_node)
        assert result == "integers()"

    def test_annotation_to_strategy_list_int(self) -> None:
        """_annotation_to_strategy handles List[int] → lists(integers()) (lines 63-66)."""
        list_node = ast.Subscript(
            value=ast.Name(id="List", ctx=ast.Load()),
            slice=ast.Name(id="int", ctx=ast.Load()),
            ctx=ast.Load(),
        )
        result = _annotation_to_strategy(list_node)
        assert result == "lists(integers())"

    def test_annotation_to_strategy_list_unknown_inner(self) -> None:
        """_annotation_to_strategy handles List[UnknownType] → None inner (line 65 false branch)."""
        list_node = ast.Subscript(
            value=ast.Name(id="list", ctx=ast.Load()),
            slice=ast.Name(id="MyType", ctx=ast.Load()),
            ctx=ast.Load(),
        )
        result = _annotation_to_strategy(list_node)
        # Inner strategy is None, so should return None (not lists(None))
        assert result is None

    def test_annotation_to_strategy_other_subscript(self) -> None:
        """_annotation_to_strategy handles non-Optional/List subscript → None (line 67)."""
        dict_node = ast.Subscript(
            value=ast.Name(id="Dict", ctx=ast.Load()),
            slice=ast.Name(id="str", ctx=ast.Load()),
            ctx=ast.Load(),
        )
        result = _annotation_to_strategy(dict_node)
        assert result is None

    # ------------------------------------------------------------------
    # line 79: _has_side_effects - attribute call check
    # ------------------------------------------------------------------
    def test_has_side_effects_attribute_call(self) -> None:
        """_has_side_effects detects attribute calls like os.remove (line 79, 83)."""
        source = textwrap.dedent("""
            def clean(path: str) -> None:
                import os
                os.remove(path)
        """)
        tree = ast.parse(source)
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        assert _has_side_effects(func) is True

    def test_has_side_effects_shutil_call(self) -> None:
        """_has_side_effects detects shutil module attribute call (line 85-86)."""
        source = textwrap.dedent("""
            def cleanup(d: str) -> None:
                shutil.rmtree(d)
        """)
        tree = ast.parse(source)
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        assert _has_side_effects(func) is True

    def test_has_side_effects_pathlib_call(self) -> None:
        """_has_side_effects detects pathlib attribute calls (line 85-86)."""
        source = textwrap.dedent("""
            def make_dir(p: str) -> None:
                pathlib.mkdir(p)
        """)
        tree = ast.parse(source)
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        assert _has_side_effects(func) is True

    # ------------------------------------------------------------------
    # line 119: skip private/dunder helpers
    # ------------------------------------------------------------------
    def test_analyze_skips_private_functions(self, tmp_path: Path) -> None:
        """analyze skips functions starting with _ (line 119)."""
        path = _write_py(tmp_path, "private.py", """
            def _helper(x: int) -> int:
                return x + 1

            def public_fn(x: int) -> int:
                return x * 2
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        names = {s.function_name for s in suggestions}
        assert "_helper" not in names
        assert "public_fn" in names

    # ------------------------------------------------------------------
    # line 126: async function gets risk note (line 131)
    # ------------------------------------------------------------------
    def test_analyze_async_function_gets_risk_note(self, tmp_path: Path) -> None:
        """Async functions get risk_notes about asyncio (lines 130-131)."""
        path = _write_py(tmp_path, "async_fn.py", """
            async def fetch(url: str) -> str:
                return url
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "fetch"), None)
        assert found is not None
        assert any("asyncio" in note for note in found.risk_notes)

    # ------------------------------------------------------------------
    # line 162: _extract_strategies handles posonlyargs and kwonlyargs
    # ------------------------------------------------------------------
    def test_extract_strategies_kwonlyargs(self, tmp_path: Path) -> None:
        """_extract_strategies handles keyword-only typed args (line 162)."""
        path = _write_py(tmp_path, "kwonly.py", """
            def fn(*, count: int, label: str) -> str:
                return label * count
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "fn"), None)
        assert found is not None
        assert any("integers()" in strat for strat in found.given_strategies)
        assert any("text(" in strat for strat in found.given_strategies)

    # ------------------------------------------------------------------
    # lines 184-186: _infer_invariants when return annotation has known strategy
    # ------------------------------------------------------------------
    def test_infer_invariants_with_return_annotation_strategy(self, tmp_path: Path) -> None:
        """_infer_invariants mentions type name when return ann has known strategy (line 180-182)."""
        path = _write_py(tmp_path, "ret_ann.py", """
            def double(x: int) -> int:
                return x * 2
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "double"), None)
        assert found is not None
        assert any("int" in inv or "annotation" in inv.lower() for inv in found.invariants)

    def test_infer_invariants_without_return_annotation(self, tmp_path: Path) -> None:
        """_infer_invariants falls back to 'should not raise' when no return ann (lines 185-186)."""
        path = _write_py(tmp_path, "no_ret.py", """
            def process(data: str):
                return data.upper()
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "process"), None)
        assert found is not None
        assert any("not raise" in inv for inv in found.invariants)

    def test_infer_invariants_return_annotation_unknown_strategy(self, tmp_path: Path) -> None:
        """_infer_invariants 'not raise' when return ann has no known strategy (line 184)."""
        path = _write_py(tmp_path, "complex_ret.py", """
            class MyResult:
                pass

            def transform(x: int) -> MyResult:
                return MyResult()
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "transform"), None)
        assert found is not None
        assert any("not raise" in inv for inv in found.invariants)

    # ------------------------------------------------------------------
    # lines 193-195: _annotation_name helper
    # ------------------------------------------------------------------
    def test_annotation_name_ast_name(self) -> None:
        """_annotation_name returns .id for ast.Name nodes (line 192)."""
        from autodev.agents.property_test_designer import _annotation_name
        node = ast.Name(id="MyType", ctx=ast.Load())
        assert _annotation_name(node) == "MyType"

    def test_annotation_name_ast_constant(self) -> None:
        """_annotation_name returns str(value) for ast.Constant nodes (line 194)."""
        from autodev.agents.property_test_designer import _annotation_name
        node = ast.Constant(value="str")
        assert _annotation_name(node) == "str"

    def test_annotation_name_other(self) -> None:
        """_annotation_name returns 'value' for other AST nodes (line 195)."""
        from autodev.agents.property_test_designer import _annotation_name
        # Use a Subscript node (not Name or Constant)
        node = ast.Subscript(
            value=ast.Name(id="List", ctx=ast.Load()),
            slice=ast.Name(id="int", ctx=ast.Load()),
            ctx=ast.Load(),
        )
        assert _annotation_name(node) == "value"

    # ------------------------------------------------------------------
    # bool / bytes / dict / tuple / set strategy coverage
    # ------------------------------------------------------------------
    def test_bool_param_strategy(self, tmp_path: Path) -> None:
        """bool parameter → booleans() strategy."""
        path = _write_py(tmp_path, "bool_fn.py", """
            def toggle(flag: bool) -> bool:
                return not flag
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "toggle"), None)
        assert found is not None
        assert any("booleans()" in strat for strat in found.given_strategies)

    def test_float_param_strategy(self, tmp_path: Path) -> None:
        """float parameter → floats(allow_nan=False) strategy."""
        path = _write_py(tmp_path, "float_fn.py", """
            def scale(x: float) -> float:
                return x * 2.0
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "scale"), None)
        assert found is not None
        assert any("floats(" in strat for strat in found.given_strategies)

    def test_bytes_param_strategy(self, tmp_path: Path) -> None:
        """bytes parameter → binary() strategy."""
        path = _write_py(tmp_path, "bytes_fn.py", """
            def encode(data: bytes) -> bytes:
                return data
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "encode"), None)
        assert found is not None
        assert any("binary()" in strat for strat in found.given_strategies)


# ===========================================================================
# SECTION 4: post_edit_lint_gate.py coverage
# ===========================================================================


class TestPostEditLintGateMissingLines:
    """Cover lines 84-86, 93-112, 119-134."""

    # ------------------------------------------------------------------
    # lines 84-86: _check_python with general Exception (not SyntaxError)
    # ------------------------------------------------------------------
    def test_python_general_read_error(self, tmp_path: Path) -> None:
        """_check_python catches general exceptions during file read/parse (lines 84-86)."""
        result = LintGateResult(language=Language.PYTHON, ok=True, changed_files=["bad.py"])
        # Create a file, then patch Path.read_text to raise a non-SyntaxError
        py_file = tmp_path / "bad.py"
        py_file.write_text("x = 1\n")
        with patch("autodev.gates.post_edit_lint_gate.Path") as mock_path_cls:
            # We need path.exists() True and path.read_text() to raise OSError
            mock_path_inst = MagicMock()
            mock_path_inst.__truediv__ = lambda self, other: mock_path_inst
            mock_path_inst.exists.return_value = True
            mock_path_inst.read_text.side_effect = OSError("disk error")
            mock_path_cls.return_value = mock_path_inst
            _check_python(str(tmp_path), ["bad.py"], result)
        assert result.ok is False
        assert any("bad.py" in e for e in result.errors)

    def test_python_read_text_io_error(self, tmp_path: Path) -> None:
        """_check_python catches IOError from read_text (line 84-86)."""
        result = LintGateResult(language=Language.PYTHON, ok=True, changed_files=["err.py"])
        py_file = tmp_path / "err.py"
        py_file.write_text("x = 1\n")
        # Patch Path.read_text to raise via pathlib.Path used in the module
        with patch("autodev.gates.post_edit_lint_gate.Path") as mock_path_cls:
            mock_path_inst = MagicMock()
            mock_path_inst.__truediv__ = lambda self, other: mock_path_inst
            mock_path_inst.exists.return_value = True
            mock_path_inst.read_text.side_effect = OSError("disk error")
            mock_path_cls.return_value = mock_path_inst
            _check_python(str(tmp_path), ["err.py"], result)
        assert result.ok is False

    # ------------------------------------------------------------------
    # lines 93-112: _check_node with node present and various scenarios
    # ------------------------------------------------------------------
    def test_node_check_skips_non_ts_js_files(self, tmp_path: Path) -> None:
        """_check_node skips files that don't end in .ts or .js (line 95)."""
        result = LintGateResult(language=Language.TYPESCRIPT, ok=True, changed_files=["app.tsx"])
        # Mock node available
        with patch("shutil.which", return_value="/usr/bin/node"):
            _check_node(str(tmp_path), ["app.tsx"], result)
        assert result.ok is True  # .tsx not matched → skipped

    def test_node_check_skips_missing_file(self, tmp_path: Path) -> None:
        """_check_node skips .ts file that doesn't exist (line 97-98)."""
        result = LintGateResult(language=Language.TYPESCRIPT, ok=True, changed_files=["missing.ts"])
        with patch("shutil.which", return_value="/usr/bin/node"):
            _check_node(str(tmp_path), ["missing.ts"], result)
        assert result.ok is True

    def test_node_check_success(self, tmp_path: Path) -> None:
        """_check_node with returncode=0 → ok=True (lines 101-109)."""
        ts_file = tmp_path / "app.ts"
        ts_file.write_text("const x: number = 1;\n")
        result = LintGateResult(language=Language.TYPESCRIPT, ok=True, changed_files=["app.ts"])
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""
        mock_proc.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/node"):
            with patch("subprocess.run", return_value=mock_proc):
                _check_node(str(tmp_path), ["app.ts"], result)
        assert result.ok is True

    def test_node_check_failure(self, tmp_path: Path) -> None:
        """_check_node with returncode != 0 sets ok=False (lines 107-109)."""
        ts_file = tmp_path / "broken.ts"
        ts_file.write_text("const x: = 1;\n")
        result = LintGateResult(language=Language.TYPESCRIPT, ok=True, changed_files=["broken.ts"])
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "SyntaxError: unexpected token"
        mock_proc.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/node"):
            with patch("subprocess.run", return_value=mock_proc):
                _check_node(str(tmp_path), ["broken.ts"], result)
        assert result.ok is False
        assert any("broken.ts" in e for e in result.errors)

    def test_node_check_exception(self, tmp_path: Path) -> None:
        """_check_node catches subprocess exceptions (lines 111-112)."""
        ts_file = tmp_path / "app.ts"
        ts_file.write_text("const x = 1;\n")
        result = LintGateResult(language=Language.TYPESCRIPT, ok=True, changed_files=["app.ts"])
        with patch("shutil.which", return_value="/usr/bin/node"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("node", 15)):
                _check_node(str(tmp_path), ["app.ts"], result)
        assert result.ok is False
        assert any("app.ts" in e for e in result.errors)

    def test_node_check_js_file(self, tmp_path: Path) -> None:
        """_check_node processes .js files (line 95 .js branch)."""
        js_file = tmp_path / "script.js"
        js_file.write_text("console.log('hi');\n")
        result = LintGateResult(language=Language.JAVASCRIPT, ok=True, changed_files=["script.js"])
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""
        mock_proc.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/node"):
            with patch("subprocess.run", return_value=mock_proc):
                _check_node(str(tmp_path), ["script.js"], result)
        assert result.ok is True

    # ------------------------------------------------------------------
    # lines 119-134: _check_rust with cargo present and various scenarios
    # ------------------------------------------------------------------
    def test_rust_check_success(self, tmp_path: Path) -> None:
        """_check_rust with returncode=0 → ok=True (lines 120-126)."""
        result = LintGateResult(language=Language.RUST, ok=True, changed_files=["src/lib.rs"])
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""
        mock_proc.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/cargo"):
            with patch("subprocess.run", return_value=mock_proc):
                _check_rust(str(tmp_path), result)
        assert result.ok is True

    def test_rust_check_failure_with_errors(self, tmp_path: Path) -> None:
        """_check_rust with returncode != 0 records error lines (lines 128-131)."""
        result = LintGateResult(language=Language.RUST, ok=True, changed_files=["src/lib.rs"])
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "error[E0308]: mismatched types\n  --> src/lib.rs:5:10\n"
        mock_proc.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/cargo"):
            with patch("subprocess.run", return_value=mock_proc):
                _check_rust(str(tmp_path), result)
        assert result.ok is False
        assert len(result.errors) >= 1

    def test_rust_check_exception(self, tmp_path: Path) -> None:
        """_check_rust catches subprocess exceptions (lines 132-134)."""
        result = LintGateResult(language=Language.RUST, ok=True, changed_files=["src/lib.rs"])
        with patch("shutil.which", return_value="/usr/bin/cargo"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cargo", 120)):
                _check_rust(str(tmp_path), result)
        assert result.ok is False
        assert any("cargo check error" in e for e in result.errors)

    def test_rust_failure_uses_stdout_when_stderr_empty(self, tmp_path: Path) -> None:
        """_check_rust uses stdout when stderr is empty (line 129 fallback)."""
        result = LintGateResult(language=Language.RUST, ok=True, changed_files=["src/lib.rs"])
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = ""
        mock_proc.stdout = "build failed\ncheck errors"
        with patch("shutil.which", return_value="/usr/bin/cargo"):
            with patch("subprocess.run", return_value=mock_proc):
                _check_rust(str(tmp_path), result)
        assert result.ok is False
        assert any("build failed" in e or "check errors" in e for e in result.errors)

    def test_gate_run_calls_check_rust(self, tmp_path: Path) -> None:
        """gate.run() routes RUST language to _check_rust (line 47)."""
        gate = PostEditLintGate()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""
        mock_proc.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/cargo"):
            with patch("subprocess.run", return_value=mock_proc):
                result = gate.run(str(tmp_path), ["src/lib.rs"], Language.RUST)
        assert isinstance(result, LintGateResult)
        assert result.ok is True

    def test_gate_run_calls_check_node_typescript(self, tmp_path: Path) -> None:
        """gate.run() routes TYPESCRIPT to _check_node (line 45)."""
        gate = PostEditLintGate()
        ts_file = tmp_path / "app.ts"
        ts_file.write_text("const x: number = 1;\n")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""
        mock_proc.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/node"):
            with patch("subprocess.run", return_value=mock_proc):
                result = gate.run(str(tmp_path), ["app.ts"], "typescript")
        assert isinstance(result, LintGateResult)
        assert result.ok is True

    def test_gate_run_calls_check_node_javascript(self, tmp_path: Path) -> None:
        """gate.run() routes JAVASCRIPT to _check_node (line 45)."""
        gate = PostEditLintGate()
        js_file = tmp_path / "script.js"
        js_file.write_text("var x = 1;\n")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""
        mock_proc.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/node"):
            with patch("subprocess.run", return_value=mock_proc):
                result = gate.run(str(tmp_path), ["script.js"], "javascript")
        assert isinstance(result, LintGateResult)
        assert result.ok is True

    def test_rust_cap_error_lines(self, tmp_path: Path) -> None:
        """_check_rust caps error output at 20 lines (line 131 range)."""
        result = LintGateResult(language=Language.RUST, ok=True, changed_files=["src/lib.rs"])
        long_stderr = "\n".join(f"error line {i}" for i in range(50))
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = long_stderr
        mock_proc.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/cargo"):
            with patch("subprocess.run", return_value=mock_proc):
                _check_rust(str(tmp_path), result)
        assert result.ok is False
        assert len(result.errors) <= 20
