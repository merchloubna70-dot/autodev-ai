"""Python quality gate — pytest, ruff, mypy (mypy optional)."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..executors.shell_executor import ShellExecutor
from ..schemas import GateOutcome, GateStatus, Language, QualityGateResult


class PythonGate:
    def run(self, repo_path: str, *, dry_run: bool = True) -> QualityGateResult:
        outcomes: list[GateOutcome] = []
        root = Path(repo_path)
        has_python = any(root.rglob("*.py"))
        if not has_python:
            return QualityGateResult(language=Language.PYTHON, outcomes=[], overall_status=GateStatus.NOT_APPLICABLE)

        sh = ShellExecutor(cwd=str(root))

        for tool, command in [
            ("ruff", "ruff check ."),
            ("pytest", "pytest"),
        ]:
            if not shutil.which(tool):
                outcomes.append(GateOutcome(
                    name=tool, status=GateStatus.SKIPPED, command=command,
                    notes=[f"{tool} not installed; skipped (mark NotReleaseReady when required)"]
                ))
                continue
            if dry_run:
                outcomes.append(GateOutcome(
                    name=tool, status=GateStatus.SKIPPED, command=command,
                    notes=["dry-run: would execute"]
                ))
                continue
            res = sh.run(command)
            outcomes.append(GateOutcome(
                name=tool,
                status=GateStatus.PASSED if res.exit_code == 0 else GateStatus.FAILED,
                command=command,
                exit_code=res.exit_code,
                stdout=res.stdout[-4000:],
                stderr=res.stderr[-4000:],
            ))

        statuses = {o.status for o in outcomes}
        if GateStatus.FAILED in statuses:
            overall = GateStatus.FAILED
        elif statuses == {GateStatus.SKIPPED} or statuses == {GateStatus.NOT_APPLICABLE}:
            overall = GateStatus.SKIPPED
        else:
            overall = GateStatus.PASSED
        return QualityGateResult(language=Language.PYTHON, outcomes=outcomes, overall_status=overall)
