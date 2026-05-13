"""RepoMapContextProvider — wraps RepoMap into a ContextProvider."""
from __future__ import annotations

from ..scanners.repo_map import RepoMap
from .base import BaseContextProvider


class RepoMapContextProvider(BaseContextProvider):
    """Provide a ranked repo-map excerpt as context.

    Parameters
    ----------
    repo_path:
        Repository root.
    token_budget:
        Approximate token budget for the excerpt.
    open_files:
        Currently open/relevant files (receive a 50× score boost).
    """

    def __init__(
        self,
        repo_path: str,
        token_budget: int = 512,
        open_files: list[str] | None = None,
    ) -> None:
        self.repo_path = repo_path
        self.token_budget = token_budget
        self.open_files = open_files or []

    def provide(self, task: str) -> str:
        """Return a Markdown table of the top-ranked files for *task*."""
        repo_map = RepoMap(
            repo_path=self.repo_path,
            seeds=_extract_seeds(task),
            open_files=self.open_files,
            token_budget=self.token_budget,
        )
        entries = repo_map.rank()
        if not entries:
            return "<!-- RepoMapContextProvider: no Python files found -->"

        lines = ["### Repo map (top files by relevance)", "| File | Symbols | Score |", "|------|---------|-------|"]
        for e in entries[:15]:
            summary = e.signature_summary[:60] + ("..." if len(e.signature_summary) > 60 else "")
            lines.append(f"| `{e.file_path}` | {summary} | {e.score:.1f} |")

        return "\n".join(lines)


def _extract_seeds(task: str) -> list[str]:
    import re
    camel = re.findall(r"\b[A-Z][A-Za-z0-9]{2,}\b", task)
    snake = re.findall(r"\b[a-z][a-z0-9_]{3,}\b", task)
    return list(dict.fromkeys(camel + snake))
