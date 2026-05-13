"""Release-only flow used by `release-check` / `report` CLI commands."""
from __future__ import annotations

from ..agents.release_manager import ReleaseManagerAgent
from ..reports.reporter import Reporter
from ..schemas import ReleaseCheckReport
from ..state import RunState


class ReleaseFlow:
    def __init__(self) -> None:
        self.release_manager = ReleaseManagerAgent()
        self.reporter = Reporter()

    def check(self, run: RunState) -> ReleaseCheckReport:
        rc = self.release_manager.check(run.state)
        run.state.release_check = rc
        run.save_json("verification/release_check.json", rc)
        # ensure final_report.md reflects the new gate decision
        self.reporter.write_final_report(run)
        run.save()
        return rc
