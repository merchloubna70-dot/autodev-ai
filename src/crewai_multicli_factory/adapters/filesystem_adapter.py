"""Filesystem adapter — read-only helpers for repo inspection."""
from __future__ import annotations

from pathlib import Path


class FilesystemAdapter:
    def __init__(self, repo_path: str):
        self.root = Path(repo_path).resolve()

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def listdir(self, rel: str = "") -> list[str]:
        target = self.root / rel
        if not target.exists():
            return []
        return [p.name for p in target.iterdir()]
