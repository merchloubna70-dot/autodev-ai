"""Reusable Textual widgets for the autodev TUI dashboard.

Requires ``textual>=0.60`` (optional dependency).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Static

# ---------------------------------------------------------------------------
# StatusBadge
# ---------------------------------------------------------------------------

_STATUS_COLOR: dict[str, str] = {
    "passed": "green",
    "failed": "red",
    "skipped": "yellow",
    "not_applicable": "dim",
    "ReleaseReady": "bold green",
    "NotReleaseReady": "red",
    "Blocked": "bold red",
    "complete": "green",
    "on-track": "cyan",
    "at-risk": "yellow",
    "blocked": "red",
    "unknown": "dim",
}


class StatusBadge(Static):
    """A colored label showing a status string."""

    DEFAULT_CSS = """
    StatusBadge {
        width: auto;
        padding: 0 1;
    }
    """

    status: reactive[str] = reactive("unknown")

    def __init__(self, status: str = "unknown", **kwargs) -> None:
        label = self._colored(status)
        super().__init__(label, **kwargs)
        self.status = status

    @staticmethod
    def _colored(status: str) -> str:
        color = _STATUS_COLOR.get(status, "white")
        return f"[{color}]{status}[/{color}]"

    def watch_status(self, value: str) -> None:
        self.update(self._colored(value))


# ---------------------------------------------------------------------------
# GateVerdictTable
# ---------------------------------------------------------------------------


class GateVerdictTable(Widget):
    """DataTable showing gate name -> status pairs."""

    DEFAULT_CSS = """
    GateVerdictTable {
        height: auto;
        max-height: 12;
    }
    """

    def compose(self) -> ComposeResult:
        yield DataTable(id="gate-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Gate", "Status")

    def update_gates(self, gate_statuses: dict[str, str]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for gate, status in gate_statuses.items():
            color = _STATUS_COLOR.get(status, "white")
            table.add_row(gate, f"[{color}]{status}[/{color}]")


# ---------------------------------------------------------------------------
# FindingsList
# ---------------------------------------------------------------------------


class FindingsList(Widget):
    """DataTable of severity findings."""

    DEFAULT_CSS = """
    FindingsList {
        height: auto;
        max-height: 14;
    }
    """

    def compose(self) -> ComposeResult:
        yield DataTable(id="findings-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Sev", "Category", "Title", "File")

    def update_findings(self, findings: list[dict]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        _sev_color = {
            "blocker": "bold red",
            "major": "red",
            "minor": "yellow",
            "nitpick": "dim",
        }
        for f in findings:
            sev = str(f.get("severity", "?"))
            color = _sev_color.get(sev, "white")
            table.add_row(
                f"[{color}]{sev}[/{color}]",
                str(f.get("category", "")),
                str(f.get("title", ""))[:60],
                str(f.get("file_path") or "")[:40],
            )
