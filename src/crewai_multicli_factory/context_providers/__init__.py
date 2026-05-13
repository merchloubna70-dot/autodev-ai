"""Context providers package.

Each provider implements BaseContextProvider and returns a Markdown block
that can be prepended to an LLM prompt to give it task-relevant context.
"""
from .base import BaseContextProvider  # noqa: F401
from .diff_provider import GitDiffContextProvider  # noqa: F401
from .repo_map_provider import RepoMapContextProvider  # noqa: F401
from .search_provider import SearchContextProvider  # noqa: F401
from .tree_provider import FileTreeContextProvider  # noqa: F401
