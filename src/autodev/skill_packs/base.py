"""Abstract base class for autodev skill packs."""
from __future__ import annotations

from abc import ABC, abstractmethod


class SkillPack(ABC):
    """Abstract base for a curated project template pack.

    Each pack provides pre-filled templates for the project-delivery
    pipeline: a brief template, a PRD scaffold, default milestone list,
    and hints for which executor/extras pair works best.
    """

    # -----------------------------------------------------------------
    # Required attributes (must be set in each concrete subclass)
    # -----------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical slug used as the --skill-pack argument value."""

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line human-readable description shown in --help output."""

    @property
    @abstractmethod
    def brief_template(self) -> str:
        """Markdown template for the project brief.

        Contains ``{{project_name}}`` and other ``{{...}}`` placeholders
        that the agent or user fills in before passing the brief to the
        PRD-writer pipeline.
        """

    @property
    @abstractmethod
    def prd_template(self) -> str:
        """Markdown schema / skeleton of PRD sections expected by this pack.

        Defines the section headings that the PRD-writer should populate
        for this project shape.
        """

    @property
    @abstractmethod
    def milestones_template(self) -> list[str]:
        """Ordered list of default milestone names for this project shape.

        Agents may override individual entries; this list is the starting
        point when no ``--prd`` overrides milestones.
        """

    @property
    @abstractmethod
    def recommended_executor(self) -> str:
        """Suggested ``--executor`` value for this pack (e.g. ``"auto"``).

        This is a hint, not a hard constraint.  Users can override with
        the ``--executor`` flag.
        """

    @property
    def recommended_extras(self) -> list[str]:
        """Optional pip extras that work well with this project shape.

        Defaults to an empty list; override in subclasses when the pack
        is commonly paired with specific tooling.
        """
        return []

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def render_brief(self, project_name: str = "MyProject", **kwargs: str) -> str:
        """Return ``brief_template`` with ``{{project_name}}`` and other
        ``{{key}}`` placeholders substituted by *kwargs*.

        Unknown placeholders are left as-is so users can fill them
        manually.
        """
        text = self.brief_template.replace("{{project_name}}", project_name)
        for key, value in kwargs.items():
            text = text.replace(f"{{{{{key}}}}}", value)
        return text

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
