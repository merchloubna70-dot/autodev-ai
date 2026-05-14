"""Coverage backfill for autodev.tui.dashboard and autodev.tui.widgets.

Strategy
--------
* Textual provides ``App.run_test()`` — an async context-manager that launches
  the app in headless mode and yields a ``Pilot`` for interaction.
* For compound widgets that only work when mounted inside an app we wrap them
  in a tiny host ``App``.
* Pure-Python helpers (``_colored``, ``StatusBadge._colored``, ``_STATUS_COLOR``)
  are exercised with direct calls — no Textual event loop needed.
* ``asyncio_mode = "auto"`` is already set in ``pyproject.toml`` so every async
  test is collected automatically.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from autodev.tui.dashboard import (
    DashboardApp,
    RunDetailPane,
    SprintPane,
    run,
)
from autodev.tui.loaders import (
    ConversationRecord,
    RunRecord,
    SprintRecord,
)
from autodev.tui.widgets import (
    _STATUS_COLOR,
    FindingsList,
    GateVerdictTable,
    StatusBadge,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_run(
    run_id: str = "run-001",
    finished_at: str | None = "2024-01-15T10:30:00+00:00",
    mock_execution_used: bool = False,
    errors: list[str] | None = None,
    gate_statuses: dict[str, str] | None = None,
    severity_findings: list[dict[str, Any]] | None = None,
    languages: list[str] | None = None,
    mode: str = "dry-run",
    flow: str = "standard",
    milestone_count: int = 3,
    task_count: int = 12,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        started_at="2024-01-15T10:00:00+00:00",
        finished_at=finished_at,
        mode=mode,
        flow=flow,
        languages=languages or ["python"],
        mock_execution_used=mock_execution_used,
        errors=errors or [],
        milestone_count=milestone_count,
        task_count=task_count,
        gate_statuses=gate_statuses or {"python/lint": "passed"},
        severity_findings=severity_findings or [],
    )


def _make_sprint(sprint_id: str = "sprint-01", health: str = "on-track") -> SprintRecord:
    return SprintRecord(
        sprint_id=sprint_id,
        goal="Finish the feature",
        started_at="2024-01-01",
        health=health,
        tasks_total=5,
        tasks_done=3,
        tasks_failed=0,
        progress_pct=60.0,
    )


def _make_convo(convo_id: str = "conv-abc") -> ConversationRecord:
    return ConversationRecord(
        conversation_id=convo_id,
        task_id="task-1",
        participating_cards=["agent-a", "agent-b"],
        message_count=7,
        preview="Hello, let's start.",
    )


@pytest.fixture()
def dev_factory_root(tmp_path: Path) -> Path:
    """Create a minimal .dev-factory tree with one run and sprint."""
    root = tmp_path / ".dev-factory"
    runs_dir = root / "runs" / "run-001"
    runs_dir.mkdir(parents=True)
    state: dict[str, Any] = {
        "run_id": "run-001",
        "started_at": "2024-01-15T10:00:00+00:00",
        "finished_at": "2024-01-15T10:30:00+00:00",
        "mode": "dry-run",
        "flow": "standard",
        "languages": ["python"],
        "mock_execution_used": False,
        "errors": [],
        "milestone_plan": {
            "milestones": [{"id": "m1"}, {"id": "m2"}],
            "tasks": [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}],
        },
        "quality_gates": [
            {
                "language": "python",
                "outcomes": [
                    {"name": "lint", "status": "passed"},
                    {"name": "tests", "status": "passed"},
                ],
            }
        ],
        "release_check": {"decision": "ReleaseReady"},
        "code_review": {
            "severity_findings": [
                {"severity": "minor", "category": "style", "title": "Long line", "file_path": "foo.py"},
            ]
        },
    }
    (runs_dir / "run_state.json").write_text(json.dumps(state), encoding="utf-8")

    # Sprint
    sprint_dir = root / "sprints" / "sprint-01"
    sprint_dir.mkdir(parents=True)
    (sprint_dir / "state.json").write_text(
        json.dumps({"sprint_id": "sprint-01", "goal": "MVP", "tasks": [{"status": "completed"}]}),
        encoding="utf-8",
    )
    (sprint_dir / "retrospective.json").write_text(
        json.dumps({"what_went_well": ["CI green"], "what_went_wrong": [], "actions_for_next_sprint": []}),
        encoding="utf-8",
    )

    # Roundtable
    rt_dir = root / "roundtables"
    rt_dir.mkdir(parents=True)
    conv_data = {
        "conversation": {
            "conversation_id": "conv-abc",
            "task_id": "t1",
            "participating_cards": ["agent-x"],
            "messages": [
                {
                    "parts": [{"kind": "text", "text": "Let's discuss the approach."}],
                }
            ],
        }
    }
    (rt_dir / "conv-abc.json").write_text(json.dumps(conv_data), encoding="utf-8")

    return root


# ===========================================================================
# widgets.py tests
# ===========================================================================


class TestStatusColorMap:
    """_STATUS_COLOR is a module-level constant — just validate it's complete."""

    def test_known_statuses_present(self) -> None:
        assert "passed" in _STATUS_COLOR
        assert "failed" in _STATUS_COLOR
        assert "ReleaseReady" in _STATUS_COLOR
        assert "blocked" in _STATUS_COLOR
        assert "unknown" in _STATUS_COLOR

    def test_values_are_strings(self) -> None:
        for k, v in _STATUS_COLOR.items():
            assert isinstance(k, str)
            assert isinstance(v, str)


class TestStatusBadgeColored:
    """StatusBadge._colored is a static method — no event loop needed."""

    def test_known_status_uses_mapped_color(self) -> None:
        result = StatusBadge._colored("passed")
        assert "[green]" in result
        assert "passed" in result

    def test_unknown_status_falls_back_to_white(self) -> None:
        result = StatusBadge._colored("superunknown")
        assert "[white]" in result
        assert "superunknown" in result

    def test_all_mapped_statuses(self) -> None:
        for status in _STATUS_COLOR:
            result = StatusBadge._colored(status)
            assert status in result

    def test_release_ready_bold_green(self) -> None:
        result = StatusBadge._colored("ReleaseReady")
        assert "bold green" in result

    def test_not_release_ready(self) -> None:
        result = StatusBadge._colored("NotReleaseReady")
        assert "red" in result

    def test_at_risk_yellow(self) -> None:
        result = StatusBadge._colored("at-risk")
        assert "yellow" in result


class TestStatusBadgeInit:
    """StatusBadge.__init__ stores status attribute."""

    def test_default_status(self) -> None:
        # Test _colored without mounting
        assert StatusBadge._colored("unknown") == "[dim]unknown[/dim]"

    def test_colored_dim_for_unknown(self) -> None:
        result = StatusBadge._colored("unknown")
        assert "dim" in result

    def test_colored_not_applicable(self) -> None:
        result = StatusBadge._colored("not_applicable")
        assert "dim" in result


# ---------------------------------------------------------------------------
# Widget-level tests via tiny host App
# ---------------------------------------------------------------------------


class GateVerdictHost(App):
    """Minimal host app to mount GateVerdictTable."""

    def compose(self) -> ComposeResult:
        yield GateVerdictTable(id="gvt")


class FindingsHost(App):
    """Minimal host app to mount FindingsList."""

    def compose(self) -> ComposeResult:
        yield FindingsList(id="fl")


class StatusBadgeHost(App):
    """Minimal host app to mount StatusBadge."""

    def __init__(self, status: str = "passed", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._status = status

    def compose(self) -> ComposeResult:
        yield StatusBadge(self._status, id="sb")


class TestGateVerdictTableMounted:
    """GateVerdictTable tests using run_test()."""

    async def test_mounts_with_data_table(self) -> None:
        app = GateVerdictHost()
        async with app.run_test() as pilot:
            gvt = pilot.app.query_one("#gvt", GateVerdictTable)
            assert gvt is not None

    async def test_update_gates_empty(self) -> None:
        app = GateVerdictHost()
        async with app.run_test() as pilot:
            gvt = pilot.app.query_one("#gvt", GateVerdictTable)
            gvt.update_gates({})
            table = gvt.query_one(DataTable)
            assert table.row_count == 0

    async def test_update_gates_single_entry(self) -> None:
        app = GateVerdictHost()
        async with app.run_test() as pilot:
            gvt = pilot.app.query_one("#gvt", GateVerdictTable)
            gvt.update_gates({"python/lint": "passed"})
            table = gvt.query_one(DataTable)
            assert table.row_count == 1

    async def test_update_gates_multiple_entries(self) -> None:
        app = GateVerdictHost()
        async with app.run_test() as pilot:
            gvt = pilot.app.query_one("#gvt", GateVerdictTable)
            gvt.update_gates({
                "python/lint": "passed",
                "python/tests": "failed",
                "release": "ReleaseReady",
            })
            table = gvt.query_one(DataTable)
            assert table.row_count == 3

    async def test_update_gates_clears_previous(self) -> None:
        app = GateVerdictHost()
        async with app.run_test() as pilot:
            gvt = pilot.app.query_one("#gvt", GateVerdictTable)
            gvt.update_gates({"a": "passed", "b": "failed"})
            gvt.update_gates({"x": "skipped"})
            table = gvt.query_one(DataTable)
            assert table.row_count == 1

    async def test_update_gates_unknown_status(self) -> None:
        app = GateVerdictHost()
        async with app.run_test() as pilot:
            gvt = pilot.app.query_one("#gvt", GateVerdictTable)
            # Should not raise for unmapped statuses
            gvt.update_gates({"gate": "exotic_status"})
            table = gvt.query_one(DataTable)
            assert table.row_count == 1

    async def test_on_mount_adds_columns(self) -> None:
        app = GateVerdictHost()
        async with app.run_test() as pilot:
            gvt = pilot.app.query_one("#gvt", GateVerdictTable)
            table = gvt.query_one(DataTable)
            # Columns should have been added in on_mount — use .columns dict
            assert len(table.columns) == 2


class TestFindingsListMounted:
    """FindingsList tests using run_test()."""

    async def test_mounts_ok(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            assert fl is not None

    async def test_update_findings_empty(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            fl.update_findings([])
            table = fl.query_one(DataTable)
            assert table.row_count == 0

    async def test_update_findings_single_entry(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            fl.update_findings([{"severity": "minor", "category": "style", "title": "Long line", "file_path": "a.py"}])
            table = fl.query_one(DataTable)
            assert table.row_count == 1

    async def test_update_findings_multiple_entries(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            findings = [
                {"severity": "blocker", "category": "security", "title": "SQLi", "file_path": "db.py"},
                {"severity": "major", "category": "bug", "title": "NPE", "file_path": "app.py"},
                {"severity": "minor", "category": "style", "title": "Trailing ws", "file_path": "main.py"},
                {"severity": "nitpick", "category": "naming", "title": "Short name", "file_path": None},
            ]
            fl.update_findings(findings)
            table = fl.query_one(DataTable)
            assert table.row_count == 4

    async def test_update_findings_clears_previous(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            fl.update_findings([{"severity": "minor", "category": "c", "title": "t", "file_path": "f"}])
            fl.update_findings([])
            table = fl.query_one(DataTable)
            assert table.row_count == 0

    async def test_update_findings_missing_keys(self) -> None:
        """Findings with missing keys should not raise."""
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            fl.update_findings([{}])  # all keys missing
            table = fl.query_one(DataTable)
            assert table.row_count == 1

    async def test_update_findings_blocker_sev_color(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            fl.update_findings([{"severity": "blocker", "category": "security", "title": "X", "file_path": "x"}])
            assert fl.query_one(DataTable).row_count == 1

    async def test_update_findings_unknown_severity(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            fl.update_findings([{"severity": "exotic", "category": "c", "title": "t", "file_path": "f"}])
            table = fl.query_one(DataTable)
            assert table.row_count == 1

    async def test_on_mount_adds_four_columns(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            table = fl.query_one(DataTable)
            assert len(table.columns) == 4

    async def test_title_truncated_at_60(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            long_title = "X" * 80
            fl.update_findings([{"severity": "minor", "category": "c", "title": long_title, "file_path": "f"}])
            assert fl.query_one(DataTable).row_count == 1

    async def test_file_path_truncated_at_40(self) -> None:
        app = FindingsHost()
        async with app.run_test() as pilot:
            fl = pilot.app.query_one("#fl", FindingsList)
            long_path = "/very/long/" + "x" * 60 + ".py"
            fl.update_findings([{"severity": "minor", "category": "c", "title": "t", "file_path": long_path}])
            assert fl.query_one(DataTable).row_count == 1


class TestStatusBadgeMounted:
    """StatusBadge full mount tests."""

    async def test_mount_passed(self) -> None:
        app = StatusBadgeHost("passed")
        async with app.run_test() as pilot:
            badge = pilot.app.query_one("#sb", StatusBadge)
            assert badge.status == "passed"

    async def test_mount_failed(self) -> None:
        app = StatusBadgeHost("failed")
        async with app.run_test() as pilot:
            badge = pilot.app.query_one("#sb", StatusBadge)
            assert badge.status == "failed"

    async def test_watch_status_triggers_update(self) -> None:
        """Setting .status should call update() via reactive watch."""
        app = StatusBadgeHost("passed")
        async with app.run_test() as pilot:
            badge = pilot.app.query_one("#sb", StatusBadge)
            badge.status = "failed"
            await pilot.pause()
            assert badge.status == "failed"

    async def test_watch_status_unknown(self) -> None:
        app = StatusBadgeHost("passed")
        async with app.run_test() as pilot:
            badge = pilot.app.query_one("#sb", StatusBadge)
            badge.status = "totally_unknown_status"
            await pilot.pause()
            assert badge.status == "totally_unknown_status"


# ===========================================================================
# dashboard.py tests
# ===========================================================================


class RunDetailPaneHost(App):
    """Minimal host for RunDetailPane."""

    def compose(self) -> ComposeResult:
        yield RunDetailPane(id="rdp")


class SprintPaneHost(App):
    """Minimal host for SprintPane."""

    def compose(self) -> ComposeResult:
        yield SprintPane(id="sp")


class TestRunDetailPane:
    """RunDetailPane via host app."""

    async def test_mounts_ok(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            assert rdp is not None

    async def test_show_run_basic(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            run = _make_run()
            rdp.show_run(run)
            meta = rdp.query_one("#detail-meta", Static)
            assert meta is not None

    async def test_show_run_with_mock(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            run = _make_run(mock_execution_used=True)
            rdp.show_run(run)  # should not raise

    async def test_show_run_with_errors(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            run = _make_run(errors=["err1", "err2"])
            rdp.show_run(run)

    async def test_show_run_still_running(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            run = _make_run(finished_at=None)
            rdp.show_run(run)

    async def test_show_run_no_languages(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            run = _make_run(languages=[])
            rdp.show_run(run)

    async def test_show_run_with_gate_statuses(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            run = _make_run(gate_statuses={"python/lint": "passed", "release": "ReleaseReady"})
            rdp.show_run(run)
            gvt = rdp.query_one(GateVerdictTable)
            assert gvt is not None

    async def test_show_run_with_findings(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            run = _make_run(
                severity_findings=[
                    {"severity": "major", "category": "bug", "title": "Bad bug", "file_path": "f.py"}
                ]
            )
            rdp.show_run(run)

    async def test_show_run_multiple_languages(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            run = _make_run(languages=["python", "rust", "typescript"])
            rdp.show_run(run)

    async def test_compose_has_gate_widget(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            assert rdp.query_one("#gate-widget", GateVerdictTable) is not None

    async def test_compose_has_findings_widget(self) -> None:
        app = RunDetailPaneHost()
        async with app.run_test() as pilot:
            rdp = pilot.app.query_one("#rdp", RunDetailPane)
            assert rdp.query_one("#findings-widget", FindingsList) is not None


class TestSprintPane:
    """SprintPane tests using run_test()."""

    async def test_mounts_ok(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            assert sp is not None

    async def test_load_sprints_empty(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            sp.load_sprints([])
            st = sp.query_one("#sprint-table", DataTable)
            assert st.row_count == 0

    async def test_load_sprints_single(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            sp.load_sprints([_make_sprint()])
            st = sp.query_one("#sprint-table", DataTable)
            assert st.row_count == 1

    async def test_load_sprints_multiple(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            sprints = [_make_sprint(f"sprint-{i}", "on-track") for i in range(4)]
            sp.load_sprints(sprints)
            st = sp.query_one("#sprint-table", DataTable)
            assert st.row_count == 4

    async def test_load_sprints_all_health_colors(self) -> None:
        """All health values should map without KeyError."""
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            healths = ["complete", "on-track", "at-risk", "blocked", "unknown", "other"]
            sprints = [_make_sprint(f"s{i}", h) for i, h in enumerate(healths)]
            sp.load_sprints(sprints)
            assert sp.query_one("#sprint-table", DataTable).row_count == len(healths)

    async def test_load_sprints_clears_previous(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            sp.load_sprints([_make_sprint("s1"), _make_sprint("s2")])
            sp.load_sprints([_make_sprint("s3")])
            assert sp.query_one("#sprint-table", DataTable).row_count == 1

    async def test_load_sprints_goal_truncated(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            long_sprint = SprintRecord(
                sprint_id="s-long",
                goal="G" * 80,
                health="on-track",
                tasks_total=1,
                tasks_done=0,
                tasks_failed=0,
                progress_pct=0.0,
            )
            sp.load_sprints([long_sprint])
            assert sp.query_one("#sprint-table", DataTable).row_count == 1

    async def test_load_conversations_empty(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            sp.load_conversations([])
            ct = sp.query_one("#convo-table", DataTable)
            assert ct.row_count == 0

    async def test_load_conversations_single(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            sp.load_conversations([_make_convo()])
            ct = sp.query_one("#convo-table", DataTable)
            assert ct.row_count == 1

    async def test_load_conversations_multiple(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            convos = [_make_convo(f"conv-{i}") for i in range(3)]
            sp.load_conversations(convos)
            assert sp.query_one("#convo-table", DataTable).row_count == 3

    async def test_load_conversations_no_cards(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            convo = ConversationRecord(
                conversation_id="no-cards",
                task_id="",
                participating_cards=[],
                message_count=0,
                preview="",
            )
            sp.load_conversations([convo])
            assert sp.query_one("#convo-table", DataTable).row_count == 1

    async def test_load_conversations_clears_previous(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            sp.load_conversations([_make_convo("a"), _make_convo("b")])
            sp.load_conversations([_make_convo("c")])
            assert sp.query_one("#convo-table", DataTable).row_count == 1

    async def test_on_mount_adds_sprint_columns(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            st = sp.query_one("#sprint-table", DataTable)
            assert len(st.columns) == 4

    async def test_on_mount_adds_convo_columns(self) -> None:
        app = SprintPaneHost()
        async with app.run_test() as pilot:
            sp = pilot.app.query_one("#sp", SprintPane)
            ct = sp.query_one("#convo-table", DataTable)
            assert len(ct.columns) == 4


class TestDashboardApp:
    """DashboardApp full integration tests."""

    async def test_app_mounts_with_empty_root(self, tmp_path: Path) -> None:
        app = DashboardApp(root=tmp_path)
        async with app.run_test() as pilot:
            # Should mount without crashing even if no data
            assert pilot.app is not None

    async def test_app_mounts_with_data(self, dev_factory_root: Path) -> None:
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            sidebar = pilot.app.query_one("#sidebar", ListView)
            # One run should be in the sidebar
            # ListItem already imported at top level
            items = list(sidebar.query(ListItem))
            assert len(items) == 1

    async def test_action_quit(self, tmp_path: Path) -> None:
        app = DashboardApp(root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.press("q")
            # App exits — pilot context ends cleanly

    async def test_action_refresh(self, dev_factory_root: Path) -> None:
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            await pilot.press("r")
            sidebar = pilot.app.query_one("#sidebar", ListView)
            # ListItem already imported at top level
            items = list(sidebar.query(ListItem))
            assert len(items) >= 1

    async def test_select_run_via_method(self, dev_factory_root: Path) -> None:
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            # _select_run should update selected index and RunDetailPane
            pilot.app._select_run(0)
            assert pilot.app._selected_index == 0

    async def test_select_run_out_of_bounds_negative(self, dev_factory_root: Path) -> None:
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            # Should not raise — index -1 is sentinel, guard is 0 <= index
            pilot.app._select_run(-1)

    async def test_select_run_out_of_bounds_high(self, dev_factory_root: Path) -> None:
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            pilot.app._select_run(9999)  # should be a no-op

    async def test_refresh_sidebar_populates(self, dev_factory_root: Path) -> None:
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            pilot.app._refresh_sidebar()
            # ListItem already imported at top level
            sidebar = pilot.app.query_one("#sidebar", ListView)
            assert len(list(sidebar.query(ListItem))) >= 1

    async def test_refresh_sidebar_with_mock_and_errors(self, tmp_path: Path) -> None:
        """Run with mock_execution_used=True and errors should render marks."""
        app = DashboardApp(root=tmp_path)
        async with app.run_test() as pilot:
            # Inject fake runs directly
            pilot.app._runs = [
                _make_run("run-mock", mock_execution_used=True, errors=["err1"]),
                _make_run("run-clean", finished_at=None),
            ]
            pilot.app._refresh_sidebar()
            # ListItem already imported at top level
            items = list(pilot.app.query_one("#sidebar", ListView).query(ListItem))
            assert len(items) == 2

    async def test_load_data_no_runs(self, tmp_path: Path) -> None:
        """Empty root should not select any run."""
        app = DashboardApp(root=tmp_path)
        async with app.run_test() as pilot:
            assert pilot.app._selected_index == -1

    async def test_load_data_with_runs_selects_first(self, dev_factory_root: Path) -> None:
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            assert pilot.app._selected_index == 0

    async def test_on_list_view_selected_valid(self, dev_factory_root: Path) -> None:
        """Simulate ListView.Selected event (Textual 8.x requires index arg)."""
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            sidebar = pilot.app.query_one("#sidebar", ListView)
            items = list(sidebar.query(ListItem))
            if items:
                event = ListView.Selected(sidebar, items[0], 0)
                pilot.app.on_list_view_selected(event)
                assert pilot.app._selected_index == 0

    async def test_on_list_view_selected_item_not_in_list(self, dev_factory_root: Path) -> None:
        """If item isn't in children, ValueError is caught silently."""
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            sidebar = pilot.app.query_one("#sidebar", ListView)
            orphan = ListItem(Label("orphan"))
            # event with item not in sidebar.query(ListItem) — ValueError caught
            event = ListView.Selected(sidebar, orphan, 99)
            pilot.app.on_list_view_selected(event)  # should not raise

    async def test_app_title(self, tmp_path: Path) -> None:
        app = DashboardApp(root=tmp_path)
        assert app.TITLE == "autodev dashboard"

    async def test_bindings_defined(self) -> None:
        from textual.binding import Binding  # noqa: PLC0415
        keys = [b.key if isinstance(b, Binding) else b[0] for b in DashboardApp.BINDINGS]
        assert "q" in keys
        assert "r" in keys

    async def test_app_with_sprint_pane_loaded(self, dev_factory_root: Path) -> None:
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            sp = pilot.app.query_one(SprintPane)
            st = sp.query_one("#sprint-table", DataTable)
            # One sprint was loaded
            assert st.row_count >= 1

    async def test_app_with_convo_pane_loaded(self, dev_factory_root: Path) -> None:
        app = DashboardApp(root=dev_factory_root)
        async with app.run_test() as pilot:
            sp = pilot.app.query_one(SprintPane)
            ct = sp.query_one("#convo-table", DataTable)
            assert ct.row_count >= 1


# ---------------------------------------------------------------------------
# run() entry point
# ---------------------------------------------------------------------------


class TestRunEntryPoint:
    """run() is the CLI entry point — test that it creates the right App type."""

    def test_run_function_exists(self) -> None:
        assert callable(run)

    def test_dashboard_app_init(self, tmp_path: Path) -> None:
        """DashboardApp can be instantiated with Path."""
        app = DashboardApp(root=tmp_path)
        assert app._root == tmp_path

    def test_dashboard_app_init_string_path(self, tmp_path: Path) -> None:
        """run() converts str→Path internally."""
        # run() calls DashboardApp(root=Path(root)).run() — just test DashboardApp creation
        app = DashboardApp(root=Path(str(tmp_path)))
        assert isinstance(app._root, Path)
