"""ConventionLoader — reads repo convention files (AGENTS.md, CLAUDE.md, .cursor/rules/*.mdc,
.cursorrules) and composes a system-prompt prefix for orchestrators.

Rules:
- Pure read-only; never executes shell or reads .env / secrets.
- Token-budget cap: default 3000 chars (truncates with notice).
- Returns RepoConventions schema.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

from ..schemas import RepoConventions

_DEFAULT_CHAR_BUDGET = 3000

# Convention files searched in order; .mdc glob is expanded separately.
_STATIC_CANDIDATES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
]
_CURSOR_RULES_GLOB = ".cursor/rules/*.mdc"


class ConventionLoader:
    """Scan a repo root for convention files and concatenate their contents."""

    def __init__(self, char_budget: int = _DEFAULT_CHAR_BUDGET) -> None:
        self.char_budget = char_budget

    def load(self, repo_path: str | Path) -> RepoConventions:
        root = Path(repo_path)

        candidates: list[Path] = []
        for name in _STATIC_CANDIDATES:
            p = root / name
            if p.is_file():
                candidates.append(p)

        # Expand .cursor/rules/*.mdc
        glob_pattern = str(root / _CURSOR_RULES_GLOB)
        for match in sorted(glob.glob(glob_pattern)):
            mp = Path(match)
            if mp.is_file():
                candidates.append(mp)

        sources: list[str] = []
        body_parts: list[str] = []
        total = 0
        truncated = False

        for path in candidates:
            # Only allow markdown/mdc extensions — never read .env or binaries.
            if path.suffix not in {".md", ".mdc", ""}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue

            header = f"## from {path.relative_to(root)}\n"
            chunk = header + text

            remaining = self.char_budget - total
            if remaining <= len(header):
                truncated = True
                break

            if len(chunk) > remaining:
                chunk = chunk[:remaining] + "\n[...truncated]"
                truncated = True

            sources.append(str(path.relative_to(root)))
            body_parts.append(chunk)
            total += len(chunk)

            if truncated:
                break

        body = "\n\n".join(body_parts)
        return RepoConventions(
            sources=sources,
            body=body,
            char_count=len(body),
            truncated=truncated,
        )
