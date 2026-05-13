"""Apply structured patches to the working tree (used by mock executors and
when an upstream agent returns a structured diff rather than a raw shell call).

Patch format here is intentionally minimal and deterministic so that mock
executors can produce identical patches across CI runs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..schemas import PipelineMode


@dataclass
class FilePatch:
    path: str
    new_content: str
    create_only: bool = False  # only write if file does not exist


class PatchExecutor:
    def __init__(self, repo_path: str, mode: PipelineMode = PipelineMode.DRY_RUN):
        self.repo_root = Path(repo_path).resolve()
        self.mode = mode

    def apply(self, patches: list[FilePatch]) -> list[str]:
        changed: list[str] = []
        for patch in patches:
            target = (self.repo_root / patch.path).resolve()
            try:
                target.relative_to(self.repo_root)
            except ValueError:
                # path escape — refuse
                continue
            if patch.create_only and target.exists():
                continue
            if self.mode == PipelineMode.DRY_RUN:
                changed.append(patch.path)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patch.new_content, encoding="utf-8")
            changed.append(patch.path)
        return changed

    @staticmethod
    def synthesize_unified_diff(patches: list[FilePatch]) -> str:
        """Tiny deterministic 'diff' rendering for mock results.

        Not a true unified diff — but good enough for audit logs in dry-run
        and for fixture-based tests to assert determinism.
        """
        lines: list[str] = []
        for p in patches:
            lines.append(f"--- a/{p.path}")
            lines.append(f"+++ b/{p.path}")
            for ln in p.new_content.splitlines():
                lines.append(f"+ {ln}")
        return "\n".join(lines)
