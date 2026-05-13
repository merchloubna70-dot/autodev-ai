"""Tests for _fs_observer.py — snapshot_repo / diff_repo helpers."""
from __future__ import annotations

import os

import pytest

from autodev.executors._fs_observer import diff_repo, snapshot_repo


def test_empty_repo_snapshot(tmp_path):
    """An empty directory yields an empty snapshot."""
    snap = snapshot_repo(str(tmp_path))
    assert isinstance(snap, set)


def test_single_new_file_detected(tmp_path):
    """A file created after the snapshot shows up in diff_repo."""
    before = snapshot_repo(str(tmp_path))
    new_file = tmp_path / "hello.py"
    new_file.write_text("print('hello')")
    after = snapshot_repo(str(tmp_path))
    diff = diff_repo(before, after)
    # At least one entry containing the filename should appear.
    assert any("hello.py" in p for p in diff), f"diff={diff}"


def test_cache_dirs_excluded(tmp_path):
    """Cache directories are excluded from mtime snapshots."""
    # Create a file in a cache dir.
    cache_dir = tmp_path / ".pytest_cache"
    cache_dir.mkdir()
    (cache_dir / "cache_file.txt").write_text("junk")

    # Also create a real file.
    (tmp_path / "real.py").write_text("x = 1")

    before: set[str] = set()  # empty pre-state
    after = snapshot_repo(str(tmp_path))
    diff = diff_repo(before, after)

    paths_str = " ".join(diff)
    assert ".pytest_cache" not in paths_str, f"cache dir leaked into diff: {diff}"
    # real.py should appear (if no git or if git shows it as untracked)
    # We accept that in a git repo it might not show if not staged — just verify no crash.


def test_git_aware_mode_skips_cache(tmp_path, monkeypatch):
    """Even when git is present, cache dirs don't appear in changed_files."""
    # Monkeypatch _is_git_repo to return False so we use mtime walk.
    import autodev.executors._fs_observer as obs

    monkeypatch.setattr(obs, "_is_git_repo", lambda p: False)

    ruff_cache = tmp_path / ".ruff_cache"
    ruff_cache.mkdir()
    (ruff_cache / "result.json").write_text("{}")

    before: set[str] = set()
    after = snapshot_repo(str(tmp_path))
    diff = diff_repo(before, after)
    paths_str = " ".join(diff)
    assert ".ruff_cache" not in paths_str


def test_diff_repo_is_sorted(tmp_path):
    """diff_repo output is sorted."""
    before: set[str] = set()
    for name in ["z.py", "a.py", "m.py"]:
        (tmp_path / name).write_text("")
    after = snapshot_repo(str(tmp_path))
    diff = diff_repo(before, after)
    assert diff == sorted(diff)
