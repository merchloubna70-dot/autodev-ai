"""Walk src/autodev/ and return a list of dotted import strings for every submodule.

This script does NOT import the autodev package at runtime; it only does
filesystem walking and string manipulation.  Safe to call from within a
PyInstaller spec file.

Usage (from spec file):
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from _collect_hidden_imports import collect
    hiddenimports = collect()
"""
from __future__ import annotations

import os
from pathlib import Path


def collect(src_root: str | None = None) -> list[str]:
    """Return sorted list of dotted module paths for every autodev submodule.

    Parameters
    ----------
    src_root:
        Absolute (or relative) path to the ``src/`` directory that contains
        the ``autodev`` package.  Defaults to ``../../src`` relative to this
        file, which is correct when the spec file lives in
        ``packaging/pyinstaller/``.
    """
    if src_root is None:
        here = Path(__file__).resolve().parent
        src_root = here / ".." / ".." / "src"

    pkg_root = Path(src_root) / "autodev"
    if not pkg_root.is_dir():
        raise FileNotFoundError(f"autodev package not found under {src_root!r}")

    modules: list[str] = []

    for dirpath, dirnames, filenames in os.walk(pkg_root):
        # Skip __pycache__ and hidden dirs
        dirnames[:] = sorted(
            d for d in dirnames if not d.startswith("_") or d == "__init__"
        )
        # But we do want __pycache__ skipped explicitly
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]

        for fname in filenames:
            if not fname.endswith(".py"):
                continue

            fpath = Path(dirpath) / fname
            # Build dotted path relative to src_root
            rel = fpath.relative_to(Path(src_root))
            parts = list(rel.parts)
            # Strip .py extension from last part
            parts[-1] = parts[-1][:-3]
            # Drop __init__ — the package itself is referenced by its parent name
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if not parts:
                continue
            dotted = ".".join(parts)
            modules.append(dotted)

    return sorted(set(modules))


if __name__ == "__main__":
    for m in collect():
        print(m)
