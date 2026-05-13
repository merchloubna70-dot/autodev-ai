"""Filesystem helpers."""
from __future__ import annotations

import os
from pathlib import Path


def ensure_dir(path: str | os.PathLike) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_text(path: str | os.PathLike, content: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def read_text(path: str | os.PathLike) -> str:
    return Path(path).read_text(encoding="utf-8")


def list_files(root: str | os.PathLike, pattern: str = "*") -> list[Path]:
    return sorted(Path(root).rglob(pattern))


def is_empty_dir(path: str | os.PathLike) -> bool:
    p = Path(path)
    if not p.exists():
        return True
    if not p.is_dir():
        return False
    for child in p.iterdir():
        if child.name in (".git", ".dev-factory"):
            continue
        if child.name.startswith("."):
            # Treat dotfiles (e.g. .gitkeep) as non-substantive for emptiness checks
            continue
        return False
    return True
