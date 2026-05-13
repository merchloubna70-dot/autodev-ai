"""QualityGate agent — fan out to per-language gates."""
from __future__ import annotations

from ..gates import PythonGate, RustGate, TypeScriptGate
from ..schemas import Language, QualityGateResult
from ._crewai_bridge import make_agent


class QualityGateAgent:
    def __init__(self) -> None:
        self.python = PythonGate()
        self.rust = RustGate()
        self.typescript = TypeScriptGate()
        self.agent = make_agent(
            role="Quality Gatekeeper",
            goal="Run language gates and refuse to bless skipped/failed as passed.",
            backstory="A release engineer with veto power.",
        )

    def run(self, *, repo_path: str, languages: list[Language], dry_run: bool) -> list[QualityGateResult]:
        results: list[QualityGateResult] = []
        if Language.PYTHON in languages:
            results.append(self.python.run(repo_path, dry_run=dry_run))
        if Language.RUST in languages:
            results.append(self.rust.run(repo_path, dry_run=dry_run))
        if Language.TYPESCRIPT in languages:
            results.append(self.typescript.run(repo_path, dry_run=dry_run))
        return results
