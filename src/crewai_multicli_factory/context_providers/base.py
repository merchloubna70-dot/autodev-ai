"""Abstract base for all context providers."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseContextProvider(ABC):
    """Provide a Markdown-formatted context block for a given task string."""

    @abstractmethod
    def provide(self, task: str) -> str:
        """Return a Markdown string with context relevant to *task*.

        Must never raise; return an empty string or an error note on failure.
        """
