"""GitDiffContextProvider — returns `git diff` output as a Markdown block."""
from __future__ import annotations

from ..adapters.git_adapter import GitAdapter
from .base import BaseContextProvider

_MAX_DIFF_CHARS = 8000


class GitDiffContextProvider(BaseContextProvider):
    """Provide the current working-tree diff as context.

    Parameters
    ----------
    repo_path:
        Path to the git repository root.
    max_chars:
        Truncate diff output at this many characters to stay within token budget.
    """

    def __init__(self, repo_path: str, max_chars: int = _MAX_DIFF_CHARS) -> None:
        self.repo_path = repo_path
        self.max_chars = max_chars
        self._adapter = GitAdapter(repo_path)

    def provide(self, task: str) -> str:  # noqa: ARG002  (task unused — diff is global)
        """Return git diff output trimmed to *max_chars*."""
        try:
            if not self._adapter.has_git():
                return "<!-- GitDiffContextProvider: no .git directory found -->"
            diff = self._adapter.diff()
            if not diff.strip():
                return "<!-- GitDiffContextProvider: working tree is clean -->"
            if len(diff) > self.max_chars:
                diff = diff[: self.max_chars] + "\n... (truncated)"
            return f"```diff\n{diff}\n```"
        except Exception as exc:  # noqa: BLE001
            return f"<!-- GitDiffContextProvider error: {exc} -->"
