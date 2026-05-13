"""ScaffoldVerification — result model for ScaffolderAgent.verify()."""
from __future__ import annotations

from pydantic import BaseModel


class ScaffoldVerification(BaseModel):
    """Records which scaffold files are present vs missing, and which M1 tasks were dropped."""

    present_files: list[str]
    missing_files: list[str]
    dropped_task_ids: list[str]
    survived_task_ids: list[str]
