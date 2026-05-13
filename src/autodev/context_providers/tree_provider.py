"""FileTreeContextProvider — depth-limited directory tree as context."""
from __future__ import annotations

from pathlib import Path

from .base import BaseContextProvider

_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".mypy_cache", ".pytest_cache"}
_MAX_NODES = 200


def _build_tree(root: Path, depth: int, max_depth: int, nodes: list[str], indent: str = "") -> None:
    if depth > max_depth or len(nodes) >= _MAX_NODES:
        return
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return
    for entry in entries:
        if len(nodes) >= _MAX_NODES:
            nodes.append(f"{indent}... (truncated)")
            return
        if entry.name in _SKIP_DIRS:
            continue
        if entry.is_dir():
            nodes.append(f"{indent}{entry.name}/")
            _build_tree(entry, depth + 1, max_depth, nodes, indent + "  ")
        else:
            nodes.append(f"{indent}{entry.name}")


class FileTreeContextProvider(BaseContextProvider):
    """Provide a depth-limited file tree of the repository.

    Parameters
    ----------
    repo_path:
        Repository root.
    max_depth:
        Maximum directory depth to traverse (default 4).
    """

    def __init__(self, repo_path: str, max_depth: int = 4) -> None:
        self.repo_path = repo_path
        self.max_depth = max_depth

    def provide(self, task: str) -> str:  # noqa: ARG002
        """Return a depth-limited ASCII file tree."""
        root = Path(self.repo_path)
        if not root.is_dir():
            return f"<!-- FileTreeContextProvider: {self.repo_path} is not a directory -->"

        nodes: list[str] = [f"{root.name}/"]
        _build_tree(root, depth=1, max_depth=self.max_depth, nodes=nodes, indent="  ")

        body = "\n".join(nodes)
        return f"### File tree: `{root.name}`\n```\n{body}\n```"
