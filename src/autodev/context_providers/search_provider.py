"""SearchContextProvider — ripgrep-style search, falls back to Python re."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .base import BaseContextProvider

_MAX_RESULTS = 30
_MAX_CHARS = 4000


def _python_grep(pattern: str, root: Path, max_results: int) -> list[str]:
    """Pure-Python fallback: search *.py files for *pattern*."""
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        rx = re.compile(re.escape(pattern), re.IGNORECASE)

    hits: list[str] = []
    for p in root.rglob("*.py"):
        if ".git" in p.parts or "__pycache__" in p.parts:
            continue
        try:
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    rel = str(p.relative_to(root))
                    hits.append(f"{rel}:{i}: {line.rstrip()}")
                    if len(hits) >= max_results:
                        return hits
        except OSError:
            continue
    return hits


def _rg_search(pattern: str, root: str, max_results: int) -> list[str] | None:
    """Try ripgrep; return None if not installed."""
    try:
        result = subprocess.run(
            ["rg", "--no-heading", "--line-number", "-i", "-m", "1",
             "--max-count", str(max_results), pattern, root],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode in (0, 1):  # 1 = no matches
            return result.stdout.splitlines()[:max_results]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


class SearchContextProvider(BaseContextProvider):
    """Search the repository for identifiers mentioned in the task.

    Uses ripgrep when available; falls back to a pure-Python re search.

    Parameters
    ----------
    repo_path:
        Repository root to search within.
    max_results:
        Maximum number of match lines to include.
    """

    def __init__(self, repo_path: str, max_results: int = _MAX_RESULTS) -> None:
        self.repo_path = repo_path
        self.max_results = max_results

    def provide(self, task: str) -> str:
        """Return search hits for key identifiers extracted from *task*."""
        # Extract the most distinctive token (CamelCase preferred)
        camel = re.findall(r"\b[A-Z][A-Za-z0-9]{2,}\b", task)
        words = re.findall(r"\b\w{4,}\b", task)
        pattern = camel[0] if camel else (words[0] if words else task[:30])

        root = Path(self.repo_path)
        hits = _rg_search(pattern, self.repo_path, self.max_results)
        if hits is None:
            hits = _python_grep(pattern, root, self.max_results)

        if not hits:
            return f"<!-- SearchContextProvider: no results for '{pattern}' -->"

        body = "\n".join(hits)
        if len(body) > _MAX_CHARS:
            body = body[:_MAX_CHARS] + "\n... (truncated)"
        return f"### Search results for `{pattern}`\n```\n{body}\n```"
