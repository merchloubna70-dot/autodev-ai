"""Filesystem observer helpers for changed_files capture.

Two strategies:
- git-aware: uses ``git status --porcelain`` (fast, exact, ignores .gitignore).
- mtime-walk: os.walk with mtime snapshots, excludes common cache dirs.
"""
from __future__ import annotations

import os
import subprocess

_SKIP_DIRS: frozenset[str] = frozenset({
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
    ".dev-factory",
    ".git",
})


def _is_git_repo(path: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return r.returncode == 0
    except Exception:
        return False


def _git_status_set(path: str) -> set[str]:
    """Return a set of relative paths that git considers changed/untracked."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode != 0:
            return set()
        files: set[str] = set()
        for line in r.stdout.splitlines():
            if len(line) >= 4:
                rel = line[3:].strip()
                # Handle renames: "old -> new"
                if " -> " in rel:
                    rel = rel.split(" -> ", 1)[1]
                files.add(rel)
        return files
    except Exception:
        return set()


def _mtime_snapshot(path: str) -> set[str]:
    """Return set of 'relpath:mtime_ns' strings, skipping cache dirs."""
    result: set[str] = set()
    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in files:
            full = os.path.join(root, fname)
            try:
                mtime = os.stat(full).st_mtime_ns
                rel = os.path.relpath(full, path)
                result.add(f"{rel}:{mtime}")
            except OSError:
                pass
    return result


def snapshot_repo(repo_path: str) -> set[str]:
    """Snapshot the repo state.

    Returns a set of opaque tokens representing current file state.
    If git is available, tokens are ``<relpath>`` strings from ``git status``.
    Otherwise, tokens are ``<relpath>:<mtime_ns>`` strings.
    """
    if _is_git_repo(repo_path):
        return _git_status_set(repo_path)
    return _mtime_snapshot(repo_path)


def diff_repo(before: set[str], after: set[str]) -> list[str]:
    """Return sorted list of relative file paths that appeared or changed.

    For git-mode: the tokens are just relpaths; any token in *after* that
    wasn't in *before* is new.
    For mtime-mode: tokens include mtime; a new token means added or modified.
    We extract just the relpath part (before the last ``:``) for the result.
    """
    new_tokens = after - before
    paths: set[str] = set()
    for token in new_tokens:
        # mtime tokens look like "path/to/file:1234567890"
        # git tokens look like "path/to/file"
        if ":" in token:
            # Could be a Windows-style absolute path or mtime token.
            # Split on last colon to separate mtime; but guard against
            # paths like "C:\foo" where we'd get a short numeric suffix.
            parts = token.rsplit(":", 1)
            try:
                int(parts[1])  # mtime_ns is numeric
                paths.add(parts[0])
            except ValueError:
                paths.add(token)
        else:
            paths.add(token)
    return sorted(paths)
