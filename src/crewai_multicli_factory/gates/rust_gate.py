"""Rust quality gate — cargo test, cargo clippy."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..executors.shell_executor import ShellExecutor
from ..schemas import GateOutcome, GateStatus, Language, QualityGateResult


class RustGate:
    def run(self, repo_path: str, *, dry_run: bool = True) -> QualityGateResult:
        outcomes: list[GateOutcome] = []
        root = Path(repo_path)
        if not (root / "Cargo.toml").exists() and not list(root.rglob("Cargo.toml")):
            return QualityGateResult(language=Language.RUST, outcomes=[], overall_status=GateStatus.NOT_APPLICABLE)

        sh = ShellExecutor(cwd=str(root))
        for tool, command in [
            ("cargo", "cargo test"),
            ("cargo", "cargo clippy --workspace --all-targets -- -D warnings"),
        ]:
            if not shutil.which(tool):
                outcomes.append(GateOutcome(name=tool, status=GateStatus.SKIPPED, command=command, notes=["cargo not installed"]))
                continue
            if dry_run:
                outcomes.append(GateOutcome(name=tool, status=GateStatus.SKIPPED, command=command, notes=["dry-run"]))
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
        overall = GateStatus.FAILED if GateStatus.FAILED in statuses else (
            GateStatus.SKIPPED if statuses == {GateStatus.SKIPPED} else GateStatus.PASSED
        )
        return QualityGateResult(language=Language.RUST, outcomes=outcomes, overall_status=overall)
