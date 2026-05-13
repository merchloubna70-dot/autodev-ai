"""Structured audit model for wave planning explanations."""
from __future__ import annotations

from pydantic import BaseModel, Field


class WaveExplanation(BaseModel):
    """Audit report explaining why each task is placed in its wave."""

    waves: list[list[str]] = Field(default_factory=list)
    reasons: dict[str, list[str]] = Field(default_factory=dict)
    # task_id -> list of "blocked-by-X (reason)" strings
    stats: dict = Field(default_factory=dict)
    # {num_waves, max_width, avg_width, single_task_waves}
