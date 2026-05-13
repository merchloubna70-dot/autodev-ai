"""TypeScript quality gate."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..executors.shell_executor import ShellExecutor
from ..schemas import GateOutcome, GateStatus, Language, QualityGateResult


class TypeScriptGate:
    def run(self, repo_path: str, *, dry_run: bool = True) -> QualityGateResult:
        outcomes: list[GateOutcome] = []
        root = Path(repo_path)
        if not (root / "package.json").exists() and not list(root.rglob("package.json")):
            return QualityGateResult(language=Language.TYPESCRIPT, outcomes=[], overall_status=GateStatus.NOT_APPLICABLE)
        runner = "pnpm" if shutil.which("pnpm") else ("yarn" if shutil.which("yarn") else "npm")
        sh = ShellExecutor(cwd=str(root))
        for label, command in [
            ("typecheck", f"{runner} run typecheck"),
            ("lint", f"{runner} run lint"),
            ("test", f"{runner} test"),
        ]:
            if not shutil.which(runner):
                outcomes.append(GateOutcome(name=label, status=GateStatus.SKIPPED, command=command, notes=[f"{runner} not installed"]))
                continue
            if dry_run:
                outcomes.append(GateOutcome(name=label, status=GateStatus.SKIPPED, command=command, notes=["dry-run"]))
                continue
            res = sh.run(command)
            outcomes.append(GateOutcome(
                name=label,
                status=GateStatus.PASSED if res.exit_code == 0 else GateStatus.FAILED,
                command=command,
                exit_code=res.exit_code,
                stdout=res.stdout[-4000:],
                stderr=res.stderr[-4000:],
            ))
        statuses = {o.status for o in outcomes}
        overall = GateStatus.FAILED if GateStatus.FAILED in statuses else (
            GateStatus.SKIPPED if statuses == {GateStatus.SKIPPED} else GateStatus.PASSED
        )
        return QualityGateResult(language=Language.TYPESCRIPT, outcomes=outcomes, overall_status=overall)
