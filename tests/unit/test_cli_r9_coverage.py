"""R9 coverage backfill for src/autodev/cli.py.

Goal: raise cli.py coverage from 46.9% to ≥85%.

Strategy
--------
- Unit-test every command body by invoking via typer.testing.CliRunner with
  mocked collaborators (patch autodev.cli.<Class>) so no real executors,
  flows, or network calls happen.
- Covers: helper functions, all 35 command bodies, @friendly_errors paths,
  continue-run scenarios (0/1/multi remaining milestones), replay, push,
  create-pr, dashboard ImportError, etc.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from autodev.cli import app
from autodev.schemas import (
    ExecutionBackend,
    ImplementationResult,
    Milestone,
    MilestonePlan,
    PipelineMode,
    PipelineRunState,
)
from autodev.state import RunState

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_state_dict(
    run_id: str = "run-r9-001",
    mode: str = "dry-run",
    milestones: list[dict] | None = None,
    impl_results: list[dict] | None = None,
    mock_execution_used: bool = True,
) -> dict:
    """Return a minimal run_state.json payload."""
    return {
        "run_id": run_id,
        "started_at": "2025-01-01T00:00:00+00:00",
        "mode": mode,
        "flow": "project_delivery_flow",
        "repo_path": "/tmp/r9-fake-repo",
        "languages": ["python"],
        "mock_execution_used": mock_execution_used,
        "errors": [],
        "milestone_plan": {
            "milestones": milestones or [],
            "tasks": [],
        } if milestones is not None else None,
        "implementation_results": impl_results or [],
    }


def _write_run(tmp_path: Path, run_id: str, state_dict: dict) -> Path:
    """Create .dev-factory/runs/<run_id>/run_state.json and required subdirs."""
    run_dir = tmp_path / ".dev-factory" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("input", "product", "architecture", "planning", "execution",
                "quality", "verification", "delivery"):
        (run_dir / sub).mkdir(exist_ok=True)
    (run_dir / "run_state.json").write_text(
        json.dumps(state_dict), encoding="utf-8"
    )
    return run_dir


# ---------------------------------------------------------------------------
# Helper functions in cli.py
# ---------------------------------------------------------------------------


class TestParseLanguages:
    def test_single(self):
        from autodev.cli import _parse_languages
        from autodev.schemas import Language
        assert _parse_languages("python") == [Language.PYTHON]

    def test_comma_separated(self):
        from autodev.cli import _parse_languages
        from autodev.schemas import Language
        result = _parse_languages("python,typescript")
        assert Language.PYTHON in result
        assert Language.TYPESCRIPT in result

    def test_unknown_falls_back(self):
        from autodev.cli import _parse_languages
        from autodev.schemas import Language
        result = _parse_languages("notareal")
        assert result == [Language.UNKNOWN]

    def test_empty_string_default(self):
        from autodev.cli import _parse_languages
        from autodev.schemas import Language
        result = _parse_languages("")
        assert result == [Language.PYTHON]


class TestParseMode:
    def test_apply(self):
        from autodev.cli import _parse_mode
        assert _parse_mode("apply") == PipelineMode.APPLY

    def test_dry_run(self):
        from autodev.cli import _parse_mode
        assert _parse_mode("dry-run") == PipelineMode.DRY_RUN

    def test_default_empty(self):
        from autodev.cli import _parse_mode
        assert _parse_mode("") == PipelineMode.DRY_RUN


class TestParseBackend:
    def test_known(self):
        from autodev.cli import _parse_backend
        assert _parse_backend("codex") == ExecutionBackend.CODEX

    def test_unknown_auto(self):
        from autodev.cli import _parse_backend
        assert _parse_backend("bogus") == ExecutionBackend.AUTO

    def test_auto(self):
        from autodev.cli import _parse_backend
        assert _parse_backend("auto") == ExecutionBackend.AUTO


class TestParseTriBool:
    def test_true_values(self):
        from autodev.cli import _parse_tri_bool
        for val in ("true", "1", "yes", "y", "on"):
            assert _parse_tri_bool(val) is True, f"Expected True for {val!r}"

    def test_false_values(self):
        from autodev.cli import _parse_tri_bool
        for val in ("false", "0", "no", "n", "off"):
            assert _parse_tri_bool(val) is False, f"Expected False for {val!r}"

    def test_none(self):
        from autodev.cli import _parse_tri_bool
        assert _parse_tri_bool(None) is None

    def test_empty(self):
        from autodev.cli import _parse_tri_bool
        assert _parse_tri_bool("") is None


class TestRead:
    def test_reads_file(self, tmp_path):
        from autodev.cli import _read
        f = tmp_path / "foo.txt"
        f.write_text("hello", encoding="utf-8")
        assert _read(str(f)) == "hello"


class TestBuildConfig:
    def test_returns_factory_config(self):
        from autodev.cli import _build_config
        cfg = _build_config(
            mode=PipelineMode.DRY_RUN,
            allow_mock=True,
            fail_fast=True,
            continue_and_report=False,
            concurrency=2,
            codex_timeout=300,
            claude_timeout=600,
        )
        from autodev.config import FactoryConfig
        assert isinstance(cfg, FactoryConfig)
        assert cfg.allow_mock_executor is True
        assert cfg.concurrency == 2

    def test_allow_mock_none_inferred_from_mode(self):
        from autodev.cli import _build_config
        cfg = _build_config(
            mode=PipelineMode.DRY_RUN,
            allow_mock=None,
            fail_fast=False,
            continue_and_report=False,
            concurrency=1,
            codex_timeout=300,
            claude_timeout=600,
        )
        assert cfg.allow_mock_executor is True  # DRY_RUN → True

    def test_allow_mock_none_apply_mode(self):
        from autodev.cli import _build_config
        cfg = _build_config(
            mode=PipelineMode.APPLY,
            allow_mock=None,
            fail_fast=False,
            continue_and_report=False,
            concurrency=1,
            codex_timeout=300,
            claude_timeout=600,
        )
        assert cfg.allow_mock_executor is False  # APPLY → False


# ---------------------------------------------------------------------------
# run-issue command
# ---------------------------------------------------------------------------


class TestRunIssueCLI:
    def test_run_issue_dry_run(self, tmp_path):
        """run-issue with a mock executor should succeed and echo run_id."""
        issue_file = tmp_path / "issue.txt"
        issue_file.write_text("Fix the bug in module X", encoding="utf-8")

        mock_run = MagicMock()
        mock_run.run_id = "run-r9-issue-001"
        mock_run.state.mock_execution_used = True

        with patch("autodev.cli.IssuePipelineFlow") as MockFlow:
            MockFlow.return_value.run.return_value = mock_run
            result = runner.invoke(app, [
                "run-issue",
                "--issue-file", str(issue_file),
                "--repo-path", str(tmp_path),
                "--mode", "dry-run",
            ])

        assert result.exit_code == 0, result.output
        assert "run_id=run-r9-issue-001" in result.output

    def test_run_issue_with_url(self, tmp_path):
        """run-issue with --issue-url constructs synthetic text and runs."""
        mock_run = MagicMock()
        mock_run.run_id = "run-r9-url-001"
        mock_run.state.mock_execution_used = True

        with patch("autodev.cli.IssuePipelineFlow") as MockFlow:
            MockFlow.return_value.run.return_value = mock_run
            result = runner.invoke(app, [
                "run-issue",
                "--issue-url", "https://github.com/owner/repo/issues/42",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "run_id=" in result.output


# ---------------------------------------------------------------------------
# deliver-project command
# ---------------------------------------------------------------------------


class TestDeliverProjectCLI:
    def test_deliver_project_with_valid_scale(self, tmp_path):
        brief_file = tmp_path / "brief.txt"
        brief_file.write_text("Build a todo app", encoding="utf-8")

        mock_run = MagicMock()
        mock_run.run_id = "run-r9-deliver-001"
        mock_run.state.mock_execution_used = True
        mock_run.state.release_check = None

        with patch("autodev.cli.ProjectDeliveryFlow") as MockFlow:
            MockFlow.return_value.run.return_value = mock_run
            result = runner.invoke(app, [
                "deliver-project",
                "--project-brief", str(brief_file),
                "--scale", "small",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "run_id=run-r9-deliver-001" in result.output

    def test_deliver_project_invalid_scale_exits_nonzero(self, tmp_path):
        brief_file = tmp_path / "brief.txt"
        brief_file.write_text("Build a todo app", encoding="utf-8")

        result = runner.invoke(app, [
            "deliver-project",
            "--project-brief", str(brief_file),
            "--scale", "galaxy-brain",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code != 0
        assert "unknown scale" in result.output

    def test_deliver_project_no_scale_auto_inferred(self, tmp_path):
        brief_file = tmp_path / "brief.txt"
        brief_file.write_text("Build something", encoding="utf-8")

        mock_run = MagicMock()
        mock_run.run_id = "run-r9-deliver-002"
        mock_run.state.mock_execution_used = True
        mock_run.state.release_check = None

        with patch("autodev.cli.ProjectDeliveryFlow") as MockFlow:
            MockFlow.return_value.run.return_value = mock_run
            result = runner.invoke(app, [
                "deliver-project",
                "--project-brief", str(brief_file),
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# classify-input command
# ---------------------------------------------------------------------------


class TestClassifyInputCLI:
    def test_classify_input_returns_json(self, tmp_path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("PROJ-42: fix the login bug", encoding="utf-8")

        mock_cls = MagicMock()
        mock_cls.model_dump_json.return_value = '{"kind": "bug_report"}'

        with patch("autodev.cli.InputClassifierAgent") as MockAgent:
            MockAgent.return_value.classify.return_value = mock_cls
            result = runner.invoke(app, [
                "classify-input",
                "--input", str(input_file),
            ])

        assert result.exit_code == 0, result.output
        assert "kind" in result.output


# ---------------------------------------------------------------------------
# create-prd command
# ---------------------------------------------------------------------------


class TestCreatePrdCLI:
    def test_create_prd_writes_output(self, tmp_path):
        brief_file = tmp_path / "brief.txt"
        brief_file.write_text("Build an invoicing SaaS", encoding="utf-8")
        output_file = tmp_path / "output.md"

        mock_prd = MagicMock()
        mock_prd.model_dump.return_value = {}
        mock_prd_writer = MagicMock()
        mock_prd_writer.write.return_value = mock_prd
        mock_prd_writer.render_markdown.return_value = "# PRD\n"

        with patch("autodev.cli.ProductManagerAgent") as MockPM, \
             patch("autodev.cli.RequirementAnalystAgent") as MockRA, \
             patch("autodev.cli.PRDWriterAgent") as MockPW, \
             patch("autodev.cli.write_text") as MockWT, \
             patch("autodev.cli.write_json") as MockWJ:
            MockPW.return_value = mock_prd_writer
            MockPM.return_value.build_brief.return_value = MagicMock()
            MockRA.return_value.derive.return_value = ([], [], [])

            result = runner.invoke(app, [
                "create-prd",
                "--project-brief", str(brief_file),
                "--output", str(output_file),
            ])

        assert result.exit_code == 0, result.output
        assert "wrote" in result.output


# ---------------------------------------------------------------------------
# plan-project command
# ---------------------------------------------------------------------------


class TestPlanProjectCLI:
    def test_plan_project_outputs_json(self, tmp_path):
        prd_file = tmp_path / "prd.md"
        prd_file.write_text("# PRD\nBuild something.", encoding="utf-8")

        mock_arch = MagicMock()
        mock_arch.model_dump_json.return_value = '{"type": "microservices"}'

        with patch("autodev.cli.RepoExplorerAgent") as MockRE, \
             patch("autodev.cli.ProductManagerAgent") as MockPM, \
             patch("autodev.cli.RequirementAnalystAgent") as MockRA, \
             patch("autodev.cli.PRDWriterAgent") as MockPW, \
             patch("autodev.cli.SystemArchitectAgent") as MockSA:
            MockRE.return_value.explore.return_value = MagicMock()
            MockPM.return_value.build_brief.return_value = MagicMock()
            MockRA.return_value.derive.return_value = ([], [], [])
            MockPW.return_value.write.return_value = MagicMock()
            MockSA.return_value.design.return_value = mock_arch

            result = runner.invoke(app, [
                "plan-project",
                "--prd", str(prd_file),
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "type" in result.output


# ---------------------------------------------------------------------------
# plan-milestones command
# ---------------------------------------------------------------------------


class TestPlanMilestonesCLI:
    def test_plan_milestones_outputs_list(self, tmp_path):
        prd_file = tmp_path / "prd.md"
        prd_file.write_text("# PRD\nBuild something.", encoding="utf-8")

        mock_milestone = MagicMock()
        mock_milestone.model_dump.return_value = {"milestone_id": "M1", "title": "MVP"}

        with patch("autodev.cli.ProductManagerAgent") as MockPM, \
             patch("autodev.cli.RequirementAnalystAgent") as MockRA, \
             patch("autodev.cli.PRDWriterAgent") as MockPW, \
             patch("autodev.cli.RepoExplorerAgent") as MockRE, \
             patch("autodev.cli.SystemArchitectAgent") as MockSA, \
             patch("autodev.cli.MilestonePlannerAgent") as MockMP:
            MockPM.return_value.build_brief.return_value = MagicMock()
            MockRA.return_value.derive.return_value = ([], [], [])
            MockPW.return_value.write.return_value = MagicMock()
            MockRE.return_value.explore.return_value = MagicMock()
            MockSA.return_value.design.return_value = MagicMock()
            MockMP.return_value.plan.return_value = [mock_milestone]

            result = runner.invoke(app, [
                "plan-milestones",
                "--prd", str(prd_file),
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# plan-tasks command
# ---------------------------------------------------------------------------


class TestPlanTasksCLI:
    def test_plan_tasks_no_run_exits_2(self, tmp_path):
        """plan-tasks with no existing run exits with code 2."""
        result = runner.invoke(app, [
            "plan-tasks",
            "--milestone-id", "M1",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2

    def test_plan_tasks_no_milestone_plan_exits_2(self, tmp_path):
        """plan-tasks when run has no milestone_plan exits with code 2."""
        state = _make_run_state_dict(run_id="run-pt-001", milestones=None)
        state["milestone_plan"] = None
        _write_run(tmp_path, "run-pt-001", state)

        result = runner.invoke(app, [
            "plan-tasks",
            "--milestone-id", "M1",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2

    def test_plan_tasks_with_valid_run(self, tmp_path):
        state = _make_run_state_dict(
            run_id="run-pt-002",
            milestones=[{"milestone_id": "M1", "title": "Init", "objective": "x"}],
        )
        # DeliveryTask requires: task_id, milestone_id, title, description
        state["milestone_plan"]["tasks"] = [
            {
                "task_id": "T1",
                "milestone_id": "M1",
                "title": "Task",
                "description": "Do the work",
            }
        ]
        _write_run(tmp_path, "run-pt-002", state)

        result = runner.invoke(app, [
            "plan-tasks",
            "--milestone-id", "M1",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# execute-milestone command
# ---------------------------------------------------------------------------


class TestExecuteMilestoneCLI:
    def test_execute_milestone_success(self, tmp_path):
        state = _make_run_state_dict(
            run_id="run-em-001",
            milestones=[{"milestone_id": "M1", "title": "Init", "objective": "x"}],
        )
        _write_run(tmp_path, "run-em-001", state)

        mock_impl = MagicMock()
        mock_impl.milestone_id = "M1"
        mock_impl.success = True
        mock_impl.mock_used = True
        mock_impl.failed_task_ids = []

        with patch("autodev.cli.MilestoneFlow") as MockMF:
            MockMF.return_value.run.return_value = mock_impl
            result = runner.invoke(app, [
                "execute-milestone",
                "--run-id", "run-em-001",
                "--milestone-id", "M1",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "milestone=M1" in result.output
        assert "success=True" in result.output

    def test_execute_milestone_file_not_found(self, tmp_path):
        """execute-milestone with non-existent run_id triggers @friendly_errors exit 2."""
        result = runner.invoke(app, [
            "execute-milestone",
            "--run-id", "does-not-exist",
            "--milestone-id", "M1",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# continue-run command
# ---------------------------------------------------------------------------


class TestContinueRunCLI:
    def test_continue_run_no_milestone_plan_exits_2(self, tmp_path):
        """continue-run when run has no milestone_plan exits with code 2."""
        state = _make_run_state_dict(run_id="run-cr-noplan", milestones=None)
        state["milestone_plan"] = None
        _write_run(tmp_path, "run-cr-noplan", state)

        result = runner.invoke(app, [
            "continue-run",
            "--run-id", "run-cr-noplan",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2
        assert "nothing to continue: no milestone_plan" in result.output

    def test_continue_run_all_done_exits_2(self, tmp_path):
        """continue-run when all milestones are already completed exits with code 2."""
        state = _make_run_state_dict(
            run_id="run-cr-alldone",
            milestones=[{"milestone_id": "M1", "title": "Init", "objective": "x"}],
            impl_results=[{"milestone_id": "M1", "success": True, "mock_used": True, "task_results": [], "failed_task_ids": []}],
        )
        _write_run(tmp_path, "run-cr-alldone", state)

        result = runner.invoke(app, [
            "continue-run",
            "--run-id", "run-cr-alldone",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2
        assert "all milestones already completed" in result.output

    def test_continue_run_one_remaining(self, tmp_path):
        """continue-run with one remaining milestone executes it."""
        state = _make_run_state_dict(
            run_id="run-cr-one",
            milestones=[
                {"milestone_id": "M1", "title": "Done", "objective": "x"},
                {"milestone_id": "M2", "title": "Remaining", "objective": "x"},
            ],
            impl_results=[
                {"milestone_id": "M1", "success": True, "mock_used": True, "task_results": [], "failed_task_ids": []}
            ],
        )
        _write_run(tmp_path, "run-cr-one", state)

        mock_impl = MagicMock()
        mock_impl.milestone_id = "M2"
        mock_impl.success = True
        mock_impl.mock_used = True

        # After continue-run finishes, RunState.load is called again; we need
        # to return an updated state showing M2 is also done.
        updated_state = _make_run_state_dict(
            run_id="run-cr-one",
            milestones=[
                {"milestone_id": "M1", "title": "Done", "objective": "x"},
                {"milestone_id": "M2", "title": "Remaining", "objective": "x"},
            ],
            impl_results=[
                {"milestone_id": "M1", "success": True, "mock_used": True, "task_results": [], "failed_task_ids": []},
                {"milestone_id": "M2", "success": True, "mock_used": True, "task_results": [], "failed_task_ids": []},
            ],
        )

        with patch("autodev.cli.MilestoneFlow") as MockMF:
            MockMF.return_value.run.return_value = mock_impl
            # Second RunState.load (for the finish check) reads from disk
            # naturally — we write the updated state before invoking.
            result = runner.invoke(app, [
                "continue-run",
                "--run-id", "run-cr-one",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "continue-run done" in result.output
        assert "1 milestones" in result.output

    def test_continue_run_multiple_remaining(self, tmp_path):
        """continue-run with multiple remaining milestones executes all."""
        state = _make_run_state_dict(
            run_id="run-cr-multi",
            milestones=[
                {"milestone_id": "M1", "title": "First", "objective": "x"},
                {"milestone_id": "M2", "title": "Second", "objective": "x"},
                {"milestone_id": "M3", "title": "Third", "objective": "x"},
            ],
            impl_results=[],
        )
        _write_run(tmp_path, "run-cr-multi", state)

        call_count = 0

        def _fake_flow_run(inp):
            nonlocal call_count
            call_count += 1
            m = MagicMock()
            m.milestone_id = inp.milestone_id
            m.success = True
            m.mock_used = True
            return m

        with patch("autodev.cli.MilestoneFlow") as MockMF:
            MockMF.return_value.run.side_effect = _fake_flow_run
            result = runner.invoke(app, [
                "continue-run",
                "--run-id", "run-cr-multi",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert call_count == 3
        assert "3 milestones" in result.output

    def test_continue_run_allow_mock_explicit_true(self, tmp_path):
        """continue-run with --allow-mock-executor true resolves correctly."""
        state = _make_run_state_dict(
            run_id="run-cr-mock",
            milestones=[{"milestone_id": "M1", "title": "T", "objective": "x"}],
            impl_results=[],
        )
        _write_run(tmp_path, "run-cr-mock", state)

        mock_impl = MagicMock()
        mock_impl.milestone_id = "M1"
        mock_impl.success = True
        mock_impl.mock_used = True

        with patch("autodev.cli.MilestoneFlow") as MockMF:
            MockMF.return_value.run.return_value = mock_impl
            result = runner.invoke(app, [
                "continue-run",
                "--run-id", "run-cr-mock",
                "--repo-path", str(tmp_path),
                "--allow-mock-executor", "true",
            ])

        assert result.exit_code == 0, result.output

    def test_continue_run_file_not_found_exits_2(self, tmp_path):
        """continue-run with non-existent run_id triggers @friendly_errors exit 2."""
        result = runner.invoke(app, [
            "continue-run",
            "--run-id", "totally-missing",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# replay command
# ---------------------------------------------------------------------------


class TestReplayCLI:
    def test_replay_from_stage(self, tmp_path):
        state = _make_run_state_dict(run_id="run-replay-001")
        _write_run(tmp_path, "run-replay-001", state)

        mock_run = MagicMock()
        mock_run.run_id = "run-replay-001"

        # ReplayFlow is imported lazily inside the command, patch at its origin
        with patch("autodev.flows.replay_flow.ReplayFlow") as MockRF:
            MockRF.return_value.replay.return_value = mock_run
            result = runner.invoke(app, [
                "replay",
                "--run-id", "run-replay-001",
                "--repo-path", str(tmp_path),
                "--from-stage", "planning",
            ])

        assert result.exit_code == 0, result.output
        assert "run_id=run-replay-001" in result.output
        assert "stage=planning" in result.output

    def test_replay_from_step(self, tmp_path):
        state = _make_run_state_dict(run_id="run-replay-002")
        _write_run(tmp_path, "run-replay-002", state)

        mock_run = MagicMock()
        mock_run.run_id = "run-replay-002"

        with patch("autodev.flows.replay_flow.ReplayFlow") as MockRF:
            MockRF.return_value.replay.return_value = mock_run
            result = runner.invoke(app, [
                "replay",
                "--run-id", "run-replay-002",
                "--repo-path", str(tmp_path),
                "--from-stage", "execution",
                "--from-step", "impl_step",
            ])

        assert result.exit_code == 0, result.output
        assert "step=impl_step" in result.output

    def test_replay_file_not_found_exits_2(self, tmp_path):
        """replay with missing run triggers @friendly_errors exit 2."""
        with patch("autodev.flows.replay_flow.ReplayFlow") as MockRF:
            MockRF.return_value.replay.side_effect = FileNotFoundError("run not found")
            result = runner.invoke(app, [
                "replay",
                "--run-id", "gone",
                "--repo-path", str(tmp_path),
            ])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# scan command
# ---------------------------------------------------------------------------


class TestScanCLI:
    def test_scan_outputs_json(self, tmp_path):
        mock_scan = MagicMock()
        mock_scan.model_dump_json.return_value = '{"files": 5}'

        with patch("autodev.cli.RepoExplorerAgent") as MockRE:
            MockRE.return_value.explore.return_value = mock_scan
            result = runner.invoke(app, [
                "scan",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "files" in result.output


# ---------------------------------------------------------------------------
# verify command
# ---------------------------------------------------------------------------


class TestVerifyCLI:
    def test_verify_success(self, tmp_path):
        state = _make_run_state_dict(run_id="run-v-001")
        _write_run(tmp_path, "run-v-001", state)

        # VerifierAgent is imported lazily; patch at its source module.
        # The verify command calls run.save_json and run.save using the real RunState
        # so we let them proceed normally (tmp_path is writable).
        result = runner.invoke(app, [
            "verify",
            "--run-id", "run-v-001",
            "--repo-path", str(tmp_path),
        ])

        # VerifierAgent.verify is deterministic with no mocks needed —
        # state has no errors and mock_execution_used=True so it should pass OK
        assert result.exit_code == 0, result.output
        # Output should be valid JSON with status field
        import json as _json
        data = _json.loads(result.output.strip())
        assert "status" in data

    def test_verify_file_not_found_exits_2(self, tmp_path):
        result = runner.invoke(app, [
            "verify",
            "--run-id", "missing-run",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# release-check command
# ---------------------------------------------------------------------------


class TestReleaseCheckCLI:
    def test_release_check_file_not_found_exits_2(self, tmp_path):
        result = runner.invoke(app, [
            "release-check",
            "--run-id", "missing-run",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2

    def test_release_check_success(self, tmp_path):
        state = _make_run_state_dict(run_id="run-rc-001")
        _write_run(tmp_path, "run-rc-001", state)

        mock_rc = MagicMock()
        mock_rc.model_dump_json.return_value = '{"decision": "NotReleaseReady"}'

        with patch("autodev.cli.ReleaseFlow") as MockRF:
            MockRF.return_value.check.return_value = mock_rc
            result = runner.invoke(app, [
                "release-check",
                "--run-id", "run-rc-001",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "decision" in result.output


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------


class TestReportCLI:
    def test_report_file_not_found_exits_2(self, tmp_path):
        result = runner.invoke(app, [
            "report",
            "--run-id", "missing-run",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2

    def test_report_success(self, tmp_path):
        state = _make_run_state_dict(run_id="run-rpt-001")
        _write_run(tmp_path, "run-rpt-001", state)

        with patch("autodev.cli.Reporter") as MockR:
            MockR.return_value.write_final_report.return_value = None
            result = runner.invoke(app, [
                "report",
                "--run-id", "run-rpt-001",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# export-delivery command
# ---------------------------------------------------------------------------


class TestExportDeliveryCLI:
    def test_export_delivery_file_not_found_exits_2(self, tmp_path):
        result = runner.invoke(app, [
            "export-delivery",
            "--run-id", "missing-run",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 2

    def test_export_delivery_success(self, tmp_path):
        state = _make_run_state_dict(run_id="run-exp-001")
        _write_run(tmp_path, "run-exp-001", state)

        output_dir = tmp_path / "delivery_pkg"

        result = runner.invoke(app, [
            "export-delivery",
            "--run-id", "run-exp-001",
            "--repo-path", str(tmp_path),
            "--output", str(output_dir),
        ])

        assert result.exit_code == 0, result.output
        assert output_dir.exists()


# ---------------------------------------------------------------------------
# push command
# ---------------------------------------------------------------------------


class TestPushCLI:
    def test_push_disabled_by_default(self, tmp_path):
        """push without --enable true should emit disabled JSON and exit 0."""
        result = runner.invoke(app, [
            "push",
            "--run-id", "run-push-001",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output.strip())
        assert data["success"] is False
        assert "disabled" in data["reason"]

    def test_push_enabled(self, tmp_path):
        """push --enable true calls CommitAgent.maybe_push."""
        # CommitAgent is imported lazily; patch at its source module
        with patch("autodev.agents.commit_agent.CommitAgent") as MockCA:
            MockCA.return_value.maybe_push.return_value = 0
            result = runner.invoke(app, [
                "push",
                "--run-id", "run-push-001",
                "--repo-path", str(tmp_path),
                "--enable", "true",
            ])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output.strip())
        assert data["success"] is True


# ---------------------------------------------------------------------------
# create-pr command
# ---------------------------------------------------------------------------


class TestCreatePrCLI:
    def test_create_pr_disabled_by_default(self, tmp_path):
        result = runner.invoke(app, [
            "create-pr",
            "--run-id", "run-pr-001",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output.strip())
        assert data["success"] is False
        assert "disabled" in data["reason"]

    def test_create_pr_enabled_gh_not_available(self, tmp_path):
        """create-pr --enable true when gh not available returns gh-not-installed."""
        # GitHubAdapter and CommitAgent are lazy imports; patch at source modules
        with patch("autodev.adapters.github_adapter.GitHubAdapter") as MockGH:
            MockGH.return_value.gh_available.return_value = False
            result = runner.invoke(app, [
                "create-pr",
                "--run-id", "run-pr-001",
                "--repo-path", str(tmp_path),
                "--enable", "true",
            ])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output.strip())
        assert data["success"] is False
        assert "gh-not-installed" in data["reason"]

    def test_create_pr_enabled_run_not_found_exits_2(self, tmp_path):
        """create-pr --enable true with missing run exits 2."""
        with patch("autodev.adapters.github_adapter.GitHubAdapter") as MockGH:
            MockGH.return_value.gh_available.return_value = True
            result = runner.invoke(app, [
                "create-pr",
                "--run-id", "does-not-exist",
                "--repo-path", str(tmp_path),
                "--enable", "true",
            ])

        assert result.exit_code == 2, result.output

    def test_create_pr_enabled_success(self, tmp_path):
        """create-pr --enable true with valid run calls CommitAgent."""
        state = _make_run_state_dict(run_id="run-pr-002")
        _write_run(tmp_path, "run-pr-002", state)

        with patch("autodev.adapters.github_adapter.GitHubAdapter") as MockGH, \
             patch("autodev.agents.commit_agent.CommitAgent") as MockCA:
            MockGH.return_value.gh_available.return_value = True
            MockCA.return_value.build_artifacts.return_value = MagicMock()
            MockCA.return_value.maybe_create_pr.return_value = {
                "success": True, "pr_url": "https://github.com/test/test/pull/1"
            }
            result = runner.invoke(app, [
                "create-pr",
                "--run-id", "run-pr-002",
                "--repo-path", str(tmp_path),
                "--enable", "true",
            ])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output.strip())
        assert data["success"] is True


# ---------------------------------------------------------------------------
# fix-bug command
# ---------------------------------------------------------------------------


class TestFixBugCLI:
    def test_fix_bug_dry_run(self, tmp_path):
        mock_run = MagicMock()
        mock_run.run_id = "run-fb-001"
        mock_impl = MagicMock()
        mock_impl.success = True
        mock_impl.mock_used = True
        mock_run.state.implementation_results = [mock_impl]

        # BugFixFlow is imported lazily; patch at source module
        with patch("autodev.flows.bug_fix_flow.BugFixFlow") as MockBFF:
            MockBFF.return_value.run.return_value = mock_run
            result = runner.invoke(app, [
                "fix-bug",
                "--bug", "NullPointerException in login handler",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "run_id=run-fb-001" in result.output
        assert "success=True" in result.output

    def test_fix_bug_no_impl_results(self, tmp_path):
        """fix-bug with empty implementation_results gracefully shows False."""
        mock_run = MagicMock()
        mock_run.run_id = "run-fb-002"
        mock_run.state.implementation_results = []

        with patch("autodev.flows.bug_fix_flow.BugFixFlow") as MockBFF:
            MockBFF.return_value.run.return_value = mock_run
            result = runner.invoke(app, [
                "fix-bug",
                "--bug", "Some bug",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "success=False" in result.output


# ---------------------------------------------------------------------------
# multi-patch-fix-bug command
# ---------------------------------------------------------------------------


class TestMultiPatchFixBugCLI:
    def test_multi_patch_fix_bug(self, tmp_path):
        mock_run = MagicMock()
        mock_run.run_id = "run-mpfb-001"
        mock_run.state.mock_execution_used = True

        # MultiPatchFlow is imported lazily; patch at source module
        with patch("autodev.flows.multi_patch_flow.MultiPatchFlow") as MockMPF:
            MockMPF.return_value.run.return_value = mock_run
            result = runner.invoke(app, [
                "multi-patch-fix-bug",
                "--bug", "Divide by zero in calculator",
                "--candidates", "2",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "run_id=run-mpfb-001" in result.output
        assert "candidates=2" in result.output


# ---------------------------------------------------------------------------
# mcp-serve command
# ---------------------------------------------------------------------------


class TestMcpServeCLI:
    def test_mcp_serve_runs_server(self):
        """mcp-serve should call MCPServer().run()."""
        # MCPServer is a lazy import inside the command; patch at the source module
        with patch("autodev.mcp_server.server.MCPServer") as MockMCP:
            MockMCP.return_value.run.return_value = None
            result = runner.invoke(app, ["mcp-serve"])

        # MCPServer.run() either blocks or returns; we just check it was called
        MockMCP.return_value.run.assert_called_once()


# ---------------------------------------------------------------------------
# a2a-serve command
# ---------------------------------------------------------------------------


class TestA2aServeCLI:
    def test_a2a_serve_starts_server(self):
        """a2a-serve should call A2AHttpServer.serve_forever()."""
        # A2AHttpServer is imported lazily; patch at source module
        with patch("autodev.adapters.a2a.server.A2AHttpServer") as MockServer:
            MockServer.return_value.serve_forever.return_value = None
            result = runner.invoke(app, [
                "a2a-serve",
                "--port", "9999",
                "--bind", "127.0.0.1",
            ])

        assert "A2A server on" in result.output
        MockServer.return_value.serve_forever.assert_called_once()


# ---------------------------------------------------------------------------
# a2a-register command
# ---------------------------------------------------------------------------


class TestA2aRegisterCLI:
    def test_a2a_register_card_none_exits_2(self):
        """a2a-register when discover_agent_card returns None exits 2."""
        # A2AHttpTransport is imported lazily; patch at source module
        with patch("autodev.adapters.a2a.transports.http.A2AHttpTransport") as MockT:
            MockT.return_value.discover_agent_card.return_value = None
            result = runner.invoke(app, [
                "a2a-register",
                "--endpoint", "http://localhost:9999",
            ])

        assert result.exit_code == 2
        data = json.loads(result.output.strip())
        assert data["success"] is False

    def test_a2a_register_success(self, tmp_path):
        """a2a-register with valid card writes roster file."""
        from autodev.schemas import AgentCard

        mock_card = AgentCard(
            name="TestAgent",
            transport="a2a-http",
            endpoint="http://localhost:9999",
            skills=["default"],
        )

        roster_path = tmp_path / "roster.json"

        with patch("autodev.adapters.a2a.transports.http.A2AHttpTransport") as MockT:
            MockT.return_value.discover_agent_card.return_value = mock_card
            result = runner.invoke(app, [
                "a2a-register",
                "--endpoint", "http://localhost:9999",
                "--save-to", str(roster_path),
            ])

        assert result.exit_code == 0, result.output
        assert roster_path.exists()
        data = json.loads(roster_path.read_text())
        assert isinstance(data, list)
        assert len(data) == 1

    def test_a2a_register_with_name_override(self, tmp_path):
        """a2a-register --name overrides the card name."""
        from autodev.schemas import AgentCard

        mock_card = AgentCard(
            name="OriginalAgent",
            transport="a2a-http",
            endpoint="http://localhost:9999",
            skills=["default"],
        )

        roster_path = tmp_path / "roster_named.json"

        with patch("autodev.adapters.a2a.transports.http.A2AHttpTransport") as MockT:
            MockT.return_value.discover_agent_card.return_value = mock_card
            result = runner.invoke(app, [
                "a2a-register",
                "--endpoint", "http://localhost:9999",
                "--name", "MyRenamedAgent",
                "--save-to", str(roster_path),
            ])

        assert result.exit_code == 0, result.output
        roster = json.loads(roster_path.read_text())
        assert roster[0]["card"]["name"] == "MyRenamedAgent"

    def test_a2a_register_appends_to_existing_roster(self, tmp_path):
        """a2a-register appends to existing roster and deduplicates."""
        from autodev.schemas import AgentCard

        roster_path = tmp_path / "roster2.json"
        existing = [
            {
                "card": {
                    "name": "OtherAgent",
                    "transport": "a2a-http",
                    "endpoint": "http://other:9999",
                    "skills": [],
                },
                "registered_via": "discovered",
            }
        ]
        roster_path.write_text(json.dumps(existing), encoding="utf-8")

        mock_card = AgentCard(
            name="NewAgent",
            transport="a2a-http",
            endpoint="http://localhost:9999",
            skills=["default"],
        )

        with patch("autodev.adapters.a2a.transports.http.A2AHttpTransport") as MockT:
            MockT.return_value.discover_agent_card.return_value = mock_card
            result = runner.invoke(app, [
                "a2a-register",
                "--endpoint", "http://localhost:9999",
                "--save-to", str(roster_path),
            ])

        assert result.exit_code == 0, result.output
        roster = json.loads(roster_path.read_text())
        assert len(roster) == 2


# ---------------------------------------------------------------------------
# a2a-call command
# ---------------------------------------------------------------------------


class TestA2aCallCLI:
    def test_a2a_call_plain_text(self):
        """a2a-call with plain JSON object task-json sends task to transport."""
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "id": "task-123", "status": "completed", "history": []
        }

        # A2AHttpTransport is imported lazily; patch at source module
        with patch("autodev.adapters.a2a.transports.http.A2AHttpTransport") as MockT:
            MockT.return_value.send_task.return_value = mock_result
            result = runner.invoke(app, [
                "a2a-call",
                "--endpoint", "http://localhost:9999",
                "--skill", "planning",
                "--task-json", '{"text": "Build a login form"}',
            ])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output.strip())
        assert "id" in data

    def test_a2a_call_bare_string(self):
        """a2a-call with a bare JSON string falls through to text content."""
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"id": "task-456", "status": "completed", "history": []}

        with patch("autodev.adapters.a2a.transports.http.A2AHttpTransport") as MockT:
            MockT.return_value.send_task.return_value = mock_result
            result = runner.invoke(app, [
                "a2a-call",
                "--endpoint", "http://localhost:9999",
                "--task-json", '"plain string"',
            ])

        assert result.exit_code == 0, result.output

    def test_a2a_call_invalid_json(self):
        """a2a-call with invalid JSON uses the raw string as text."""
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"id": "task-789", "status": "completed", "history": []}

        with patch("autodev.adapters.a2a.transports.http.A2AHttpTransport") as MockT:
            MockT.return_value.send_task.return_value = mock_result
            result = runner.invoke(app, [
                "a2a-call",
                "--endpoint", "http://localhost:9999",
                "--task-json", "not-json-at-all",
            ])

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# investigate command
# ---------------------------------------------------------------------------


class TestInvestigateCLI:
    def test_investigate_with_file_path(self, tmp_path):
        """investigate emits file= line when case.file_path is set."""
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.slug = "test-slug"
        mock_case.mode = "defect-chasing"
        mock_case.file_path = str(tmp_path / "case.md")
        mock_case.evidence = ["e1", "e2"]

        # InvestigationFlow is imported lazily; patch at source module
        with patch("autodev.flows.investigation_flow.InvestigationFlow") as MockIF:
            MockIF.return_value.run.return_value = mock_case
            result = runner.invoke(app, [
                "investigate",
                "--input", "PROJ-101",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "case_id=case-001" in result.output
        assert "file=" in result.output

    def test_investigate_no_file_path(self, tmp_path):
        """investigate without file_path skips the file= line."""
        mock_case = MagicMock()
        mock_case.case_id = "case-002"
        mock_case.slug = "no-file"
        mock_case.mode = "calibrating"
        mock_case.file_path = None
        mock_case.evidence = []

        with patch("autodev.flows.investigation_flow.InvestigationFlow") as MockIF:
            MockIF.return_value.run.return_value = mock_case
            result = runner.invoke(app, [
                "investigate",
                "--input", "some-error",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "file=" not in result.output


# ---------------------------------------------------------------------------
# dashboard command
# ---------------------------------------------------------------------------


class TestDashboardCLI:
    def test_dashboard_import_error_exits_1(self):
        """dashboard with missing textual exits with code 1 and helpful message."""
        with patch.dict("sys.modules", {"autodev.tui.dashboard": None}):
            result = runner.invoke(app, ["dashboard"])

        # The ImportError path should give exit code 1
        assert result.exit_code == 1
        assert "Textual is not installed" in result.output

    def test_dashboard_runs_tui(self, tmp_path):
        """dashboard with textual available calls run(root=...)."""
        mock_run = MagicMock()

        import types
        fake_tui_module = types.ModuleType("autodev.tui.dashboard")
        fake_tui_module.run = mock_run

        import sys
        original = sys.modules.get("autodev.tui.dashboard")
        sys.modules["autodev.tui.dashboard"] = fake_tui_module
        try:
            result = runner.invoke(app, [
                "dashboard",
                "--root", str(tmp_path / ".dev-factory"),
            ])
        finally:
            if original is None:
                sys.modules.pop("autodev.tui.dashboard", None)
            else:
                sys.modules["autodev.tui.dashboard"] = original

        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# sprint-start previous_sprint_id branch
# ---------------------------------------------------------------------------


class TestSprintStartPreviousBranch:
    def test_sprint_start_shows_previous_if_set(self, tmp_path):
        """sprint-start --goal emits 'previous=...' if a previous sprint existed."""
        from autodev.flows.sprint_flow import SprintFlow

        mock_state = MagicMock()
        mock_state.sprint_id = "sprint-002"
        mock_state.started_at = "2025-01-01T00:00:00+00:00"
        mock_state.planning_artifacts_path = str(tmp_path / ".autodev/sprints/sprint-002/planning")
        mock_state.implementation_artifacts_path = str(tmp_path / ".autodev/sprints/sprint-002/implementation")
        mock_state.previous_sprint_id = "sprint-001"

        with patch.object(SprintFlow, "start_sprint", return_value=mock_state):
            result = runner.invoke(app, [
                "sprint-start",
                "--repo-path", str(tmp_path),
                "--goal", "Ship v2",
            ])

        assert result.exit_code == 0, result.output
        assert "previous=sprint-001" in result.output


# ---------------------------------------------------------------------------
# sprint-status blockers branch
# ---------------------------------------------------------------------------


class TestSprintStatusBlockersBranch:
    def test_sprint_status_shows_blockers(self, tmp_path):
        """sprint-status emits 'blockers=...' line when blockers are present."""
        from autodev.flows.sprint_flow import SprintFlow

        mock_status = MagicMock()
        mock_status.sprint_id = "sprint-001"
        mock_status.health = "at-risk"
        mock_status.tasks_total = 5
        mock_status.tasks_done = 2
        mock_status.tasks_failed = 1
        mock_status.progress_pct = 40.0
        mock_status.blockers = ["Blocked by infra", "API key missing"]

        with patch.object(SprintFlow, "status", return_value=mock_status):
            result = runner.invoke(app, [
                "sprint-status",
                "--repo-path", str(tmp_path),
                "--sprint-id", "sprint-001",
            ])

        assert result.exit_code == 0, result.output
        assert "blockers=" in result.output
        assert "Blocked by infra" in result.output


# ---------------------------------------------------------------------------
# @friendly_errors — JSON decode and validation error paths
# ---------------------------------------------------------------------------


class TestFriendlyErrorsDecorator:
    def test_json_decode_error_exits_3(self, tmp_path):
        """Commands decorated with @friendly_errors should exit 3 on JSONDecodeError."""
        # Write corrupt run_state.json
        run_id = "run-corrupt-001"
        run_dir = tmp_path / ".dev-factory" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_state.json").write_text("{corrupt json{{", encoding="utf-8")

        result = runner.invoke(app, [
            "release-check",
            "--run-id", run_id,
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 3

    def test_validation_error_exits_4(self, tmp_path):
        """Commands decorated with @friendly_errors should exit 4 on ValidationError."""
        # Write run_state.json with invalid enum value
        run_id = "run-invalid-001"
        run_dir = tmp_path / ".dev-factory" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        invalid_state = {
            "run_id": run_id,
            "started_at": "2025-01-01T00:00:00+00:00",
            "mode": "not-a-valid-mode",  # invalid PipelineMode enum
            "repo_path": str(tmp_path),
        }
        (run_dir / "run_state.json").write_text(
            json.dumps(invalid_state), encoding="utf-8"
        )

        result = runner.invoke(app, [
            "release-check",
            "--run-id", run_id,
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 4


# ---------------------------------------------------------------------------
# continue-run: finish() branch when all milestones complete after loop
# ---------------------------------------------------------------------------


class TestContinueRunFinishBranch:
    def test_continue_run_finishes_all(self, tmp_path):
        """continue-run calls run.finish() when all milestones complete after loop."""
        state = _make_run_state_dict(
            run_id="run-cr-finish",
            milestones=[{"milestone_id": "M1", "title": "Only", "objective": "x"}],
            impl_results=[],  # none done yet
        )
        _write_run(tmp_path, "run-cr-finish", state)

        mock_impl = MagicMock()
        mock_impl.milestone_id = "M1"
        mock_impl.success = True
        mock_impl.mock_used = True

        def _fake_run(inp):
            # After MilestoneFlow.run, write the updated state showing M1 is done
            updated = _make_run_state_dict(
                run_id="run-cr-finish",
                milestones=[{"milestone_id": "M1", "title": "Only", "objective": "x"}],
                impl_results=[{
                    "milestone_id": "M1", "success": True, "mock_used": True,
                    "task_results": [], "failed_task_ids": [],
                }],
            )
            run_dir = tmp_path / ".dev-factory" / "runs" / "run-cr-finish"
            (run_dir / "run_state.json").write_text(
                json.dumps(updated), encoding="utf-8"
            )
            return mock_impl

        with patch("autodev.flows.milestone_flow.MilestoneFlow") as MockMF:
            MockMF.return_value.run.side_effect = _fake_run
            result = runner.invoke(app, [
                "continue-run",
                "--run-id", "run-cr-finish",
                "--repo-path", str(tmp_path),
            ])

        assert result.exit_code == 0, result.output
        assert "1 milestones" in result.output
        # Verify run was marked finished
        state_data = json.loads(
            (tmp_path / ".dev-factory" / "runs" / "run-cr-finish" / "run_state.json").read_text()
        )
        assert state_data.get("finished_at") is not None


# ---------------------------------------------------------------------------
# a2a-register: invalid roster JSON is treated as empty list (lines 791-793)
# ---------------------------------------------------------------------------


class TestA2aRegisterInvalidRoster:
    def test_a2a_register_invalid_roster_json(self, tmp_path):
        """a2a-register gracefully handles corrupt roster.json."""
        from autodev.schemas import AgentCard

        roster_path = tmp_path / "bad_roster.json"
        roster_path.write_text("{not valid json{{", encoding="utf-8")

        mock_card = AgentCard(
            name="NewAgent",
            transport="a2a-http",
            endpoint="http://localhost:9999",
            skills=["default"],
        )

        with patch("autodev.adapters.a2a.transports.http.A2AHttpTransport") as MockT:
            MockT.return_value.discover_agent_card.return_value = mock_card
            result = runner.invoke(app, [
                "a2a-register",
                "--endpoint", "http://localhost:9999",
                "--save-to", str(roster_path),
            ])

        assert result.exit_code == 0, result.output
        # Should have written a new single-item list
        roster = json.loads(roster_path.read_text())
        assert len(roster) == 1

    def test_a2a_register_non_list_roster(self, tmp_path):
        """a2a-register when roster.json is a dict (not a list) treats it as empty."""
        from autodev.schemas import AgentCard

        roster_path = tmp_path / "dict_roster.json"
        roster_path.write_text('{"key": "value"}', encoding="utf-8")

        mock_card = AgentCard(
            name="Agent2",
            transport="a2a-http",
            endpoint="http://localhost:9999",
            skills=["default"],
        )

        with patch("autodev.adapters.a2a.transports.http.A2AHttpTransport") as MockT:
            MockT.return_value.discover_agent_card.return_value = mock_card
            result = runner.invoke(app, [
                "a2a-register",
                "--endpoint", "http://localhost:9999",
                "--save-to", str(roster_path),
            ])

        assert result.exit_code == 0, result.output
        roster = json.loads(roster_path.read_text())
        assert isinstance(roster, list)
        assert len(roster) == 1


# ---------------------------------------------------------------------------
# design-ux: unknown language fallback (lines 908-909)
# ---------------------------------------------------------------------------


class TestDesignUxUnknownLanguage:
    def test_design_ux_unknown_language_falls_back(self, tmp_path):
        """design-ux with an unknown language appends Language.UNKNOWN without crashing."""
        result = runner.invoke(app, [
            "design-ux",
            "--project-name", "FallbackLangApp",
            "--languages", "notareallanguage",
            "--repo-path", str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        assert "FallbackLangApp" in result.output


# ---------------------------------------------------------------------------
# _version_callback: PackageNotFoundError branch (lines 37-38)
# ---------------------------------------------------------------------------


class TestVersionCallbackNotFound:
    def test_version_package_not_found(self):
        """--version emits 'unknown' when package metadata is not found."""
        from importlib.metadata import PackageNotFoundError as _PNFE

        # _pkg_version is imported lazily inside _version_callback;
        # patch it via importlib.metadata.version at the module level
        with patch("importlib.metadata.version", side_effect=_PNFE("autodev-ai")):
            result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0, result.output
        assert "unknown" in result.output
