"""Textual TUI dashboard for autodev pipeline runs.

Four-pane layout:
  1. Run history list  — left sidebar
  2. Run detail        — top-right (milestones, tasks, gate verdicts, findings)
  3. Sprint retros     — bottom-right, tab 1
  4. Roundtable convos — bottom-right, tab 2

Usage::

    autodev dashboard --root .dev-factory
    # or directly:
    python -m autodev.tui.dashboard --root .dev-factory
"""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)

from .loaders import (
    ConversationRecord,
    RunRecord,
    SprintRecord,
    load_conversations,
    load_runs,
    load_sprints,
)
from .widgets import FindingsList, GateVerdictTable

# ---------------------------------------------------------------------------
# Sub-widgets
# ---------------------------------------------------------------------------


class RunDetailPane(Widget):
    """Shows detail for the currently selected run."""

    DEFAULT_CSS = """
    RunDetailPane {
        height: 1fr;
        border: round $accent;
        padding: 1 2;
        overflow-y: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("[b]Run Detail[/b]", id="detail-title")
        yield Static("(select a run)", id="detail-meta")
        yield Label("[b]Gate Verdicts[/b]")
        yield GateVerdictTable(id="gate-widget")
        yield Label("[b]Severity Findings[/b]")
        yield FindingsList(id="findings-widget")

    def show_run(self, run: RunRecord) -> None:
        finished = run.finished_at or "running"
        mock = " [yellow](mock)[/yellow]" if run.mock_execution_used else ""
        errors_txt = f" [red]errors={len(run.errors)}[/red]" if run.errors else ""
        meta = (
            f"[b]{run.run_id}[/b]{mock}{errors_txt}\n"
            f"mode={run.mode}  flow={run.flow or '—'}\n"
            f"started: {run.started_at[:19] if run.started_at else '?'}\n"
            f"finished: {finished[:19] if finished != 'running' else finished}\n"
            f"milestones: {run.milestone_count}  tasks: {run.task_count}\n"
            f"langs: {', '.join(run.languages) or '—'}"
        )
        self.query_one("#detail-meta", Static).update(meta)
        self.query_one(GateVerdictTable).update_gates(run.gate_statuses)
        self.query_one(FindingsList).update_findings(run.severity_findings)


class SprintPane(Widget):
    """Tabbed pane: sprint retros + roundtable conversations."""

    DEFAULT_CSS = """
    SprintPane {
        height: 1fr;
        border: round $accent;
    }
    """

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("Sprints", id="tab-sprints"):
                yield DataTable(id="sprint-table")
            with TabPane("Conversations", id="tab-convos"):
                yield DataTable(id="convo-table")

    def on_mount(self) -> None:
        st = self.query_one("#sprint-table", DataTable)
        st.add_columns("Sprint", "Health", "Progress", "Goal")

        ct = self.query_one("#convo-table", DataTable)
        ct.add_columns("ID", "Agents", "Msgs", "Preview")

    def load_sprints(self, sprints: list[SprintRecord]) -> None:
        st = self.query_one("#sprint-table", DataTable)
        st.clear()
        _health_color = {
            "complete": "green",
            "on-track": "cyan",
            "at-risk": "yellow",
            "blocked": "red",
            "unknown": "dim",
        }
        for s in sprints:
            c = _health_color.get(s.health, "white")
            st.add_row(
                s.sprint_id,
                f"[{c}]{s.health}[/{c}]",
                f"{s.progress_pct:.0f}% ({s.tasks_done}/{s.tasks_total})",
                (s.goal[:50] or "—"),
            )

    def load_conversations(self, convos: list[ConversationRecord]) -> None:
        ct = self.query_one("#convo-table", DataTable)
        ct.clear()
        for c in convos:
            ct.add_row(
                c.conversation_id[:28],
                ", ".join(c.participating_cards[:3]) or "—",
                str(c.message_count),
                (c.preview[:60] or "—"),
            )


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------


class DashboardApp(App):
    """Autodev pipeline run dashboard."""

    TITLE = "autodev dashboard"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    CSS = """
    Screen {
        layout: horizontal;
    }
    #sidebar {
        width: 30;
        border: round $accent;
        height: 1fr;
    }
    #main-col {
        width: 1fr;
        layout: vertical;
    }
    """

    _root: Path
    _runs: list[RunRecord] = []
    _sprints: list[SprintRecord] = []
    _convos: list[ConversationRecord] = []
    _selected_index: reactive[int] = reactive(-1)

    def __init__(self, root: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._root = root

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView(id="sidebar")
        with Widget(id="main-col"):
            yield RunDetailPane(id="detail-pane")
            yield SprintPane(id="sprint-pane")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        self._runs = load_runs(self._root)
        self._sprints = load_sprints(self._root)
        self._convos = load_conversations(self._root)
        self._refresh_sidebar()
        self.query_one(SprintPane).load_sprints(self._sprints)
        self.query_one(SprintPane).load_conversations(self._convos)
        if self._runs:
            self._select_run(0)

    def _refresh_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        sidebar.clear()
        for run in self._runs:
            finished = "done" if run.finished_at else "running"
            mock_mark = " M" if run.mock_execution_used else ""
            err_mark = f" E{len(run.errors)}" if run.errors else ""
            label = f"{run.run_id[:22]}\n  {run.mode} {finished}{mock_mark}{err_mark}"
            sidebar.append(ListItem(Label(label)))

    def _select_run(self, index: int) -> None:
        if 0 <= index < len(self._runs):
            self._selected_index = index
            self.query_one(RunDetailPane).show_run(self._runs[index])

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        children = list(sidebar.query(ListItem))
        try:
            idx = children.index(event.item)
            self._select_run(idx)
        except ValueError:
            pass

    def action_refresh(self) -> None:
        self._load_data()

    async def action_quit(self) -> None:
        self.exit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(root: str = ".dev-factory") -> None:
    """Launch the dashboard. Called by ``autodev dashboard``."""
    DashboardApp(root=Path(root)).run()


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="autodev TUI dashboard")
    parser.add_argument("--root", default=".dev-factory", help="dev-factory root directory")
    args = parser.parse_args()
    run(root=args.root)
