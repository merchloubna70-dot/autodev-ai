"""NavigatorAgent — drives RepoMap to produce a NavigatorResult."""
from __future__ import annotations

import re
from pathlib import Path

from ..scanners.repo_map import RepoMap as _RepoMap
from ..schemas import NavigatorResult, RepoMapEntry as _SchemaEntry
from ._crewai_bridge import make_agent


def _entries_to_schema(entries: list) -> list[_SchemaEntry]:
    """Convert RepoMap internal entries to Pydantic schema entries."""
    return [
        _SchemaEntry(
            file_path=e.file_path,
            signature_summary=e.signature_summary,
            score=e.score,
            symbol_count=e.symbol_count,
        )
        for e in entries
    ]


def _extract_seeds(task_description: str) -> list[str]:
    """Heuristic: pull CamelCase and snake_case identifiers from the task."""
    camel = re.findall(r"\b[A-Z][A-Za-z0-9]{2,}\b", task_description)
    snake = re.findall(r"\b[a-z][a-z0-9_]{3,}\b", task_description)
    return list(dict.fromkeys(camel + snake))  # deduplicate, preserve order


class NavigatorAgent:
    """Locate the most relevant files and symbols for a given task.

    Parameters
    ----------
    repo_path:
        Absolute path to the repository root.
    token_budget:
        Approximate token cap for repo-map summaries passed downstream.
    """

    def __init__(self, repo_path: str, token_budget: int = 1024) -> None:
        self.repo_path = repo_path
        self.token_budget = token_budget
        self.agent = make_agent(
            role="Navigator",
            goal="Identify the most relevant files and symbols for the current task.",
            backstory=(
                "An expert code archaeologist who reads import graphs and symbol "
                "names to surface the exact files a developer needs."
            ),
        )

    # ------------------------------------------------------------------

    def navigate(
        self,
        task_description: str,
        task_id: str = "task-0",
        open_files: list[str] | None = None,
    ) -> NavigatorResult:
        """Return a NavigatorResult ranking files by relevance to *task_description*."""
        seeds = _extract_seeds(task_description)

        repo_map = _RepoMap(
            repo_path=self.repo_path,
            seeds=seeds,
            open_files=open_files or [],
            token_budget=self.token_budget,
        )
        ranked = repo_map.rank()

        schema_entries = _entries_to_schema(ranked)

        # Top files (up to 10)
        top_files = [e.file_path for e in schema_entries[:10]]

        # Collect symbols from top entries
        symbols: list[str] = []
        for entry in schema_entries[:5]:
            for sym in entry.signature_summary.split(", "):
                clean = sym.strip().split(" ")[0]  # remove "(+N more)" suffix
                if clean and "+" not in clean:
                    symbols.append(clean)

        # Build simple call-chain hints: file→file based on import graph
        # (limited breadcrumb: just top 3 files listed as a chain)
        call_chains: list[str] = []
        if len(top_files) >= 2:
            call_chains.append(" → ".join(top_files[:3]))

        return NavigatorResult(
            task_id=task_id,
            files=top_files,
            symbols=list(dict.fromkeys(symbols)),  # deduplicate
            call_chains=call_chains,
            repo_map_excerpt=schema_entries[:20],
        )
