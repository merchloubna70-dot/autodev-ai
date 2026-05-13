"""Repo Explorer — wraps RepoScanner with a CrewAI face."""
from __future__ import annotations

from ..scanners import RepoScanner
from ..schemas import RepoScanResult
from ._crewai_bridge import make_agent


class RepoExplorerAgent:
    def __init__(self) -> None:
        self.scanner = RepoScanner()
        self.agent = make_agent(
            role="Repo Explorer",
            goal="Understand the existing repo layout, languages, and test framework.",
            backstory="A senior engineer who 'reads' a repo in seconds.",
        )

    def explore(self, repo_path: str) -> RepoScanResult:
        return self.scanner.scan(repo_path)
