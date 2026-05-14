"""Unit tests for WorkerIsolator — no git operations required."""
from __future__ import annotations

from pathlib import Path

import pytest

from autodev.executors.worker_isolator import (
    CODEX_HOME_PRIVATE_DIRS,
    CODEX_HOME_PRIVATE_FILES,
    WorkerIsolator,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def parent_home(tmp_path: Path) -> Path:
    """A fake parent CODEX_HOME with some shared files/dirs."""
    home = tmp_path / "parent_codex_home"
    home.mkdir()
    # Create a subset of CODEX_HOME_SHARED entries
    (home / "auth.json").write_text('{"token": "fake"}', encoding="utf-8")
    (home / "config.toml").write_text("[settings]\nfoo = true\n", encoding="utf-8")
    (home / "plugins").mkdir()
    (home / "skills").mkdir()
    return home


@pytest.fixture()
def worker_home(tmp_path: Path) -> Path:
    return tmp_path / "worker_codex_home"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_prepare_codex_home_creates_worker_dir(parent_home, worker_home):
    isolator = WorkerIsolator()
    result = isolator.prepare_codex_home(parent_home, worker_home)
    assert worker_home.exists()
    assert result.worker_home == worker_home


def test_shared_files_are_symlinks(parent_home, worker_home):
    isolator = WorkerIsolator()
    isolator.prepare_codex_home(parent_home, worker_home)

    # auth.json and config.toml exist in parent → should be symlinks in worker
    for name in ("auth.json", "config.toml"):
        dst = worker_home / name
        assert dst.is_symlink(), f"{name} should be a symlink"
        assert dst.resolve() == (parent_home / name).resolve(), \
            f"{name} symlink should point to parent_home"


def test_shared_dirs_are_symlinks(parent_home, worker_home):
    isolator = WorkerIsolator()
    isolator.prepare_codex_home(parent_home, worker_home)

    for name in ("plugins", "skills"):
        dst = worker_home / name
        assert dst.is_symlink(), f"{name} dir should be a symlink"


def test_private_dirs_are_real_mkdirs(parent_home, worker_home):
    isolator = WorkerIsolator()
    isolator.prepare_codex_home(parent_home, worker_home)

    for name in CODEX_HOME_PRIVATE_DIRS:
        d = worker_home / name
        assert d.exists() and d.is_dir(), f"{name} should be a real directory"
        assert not d.is_symlink(), f"{name} should NOT be a symlink"


def test_private_files_are_not_created(parent_home, worker_home):
    """Mutable SQLite / jsonl files must NOT exist in the worker home."""
    isolator = WorkerIsolator()
    isolator.prepare_codex_home(parent_home, worker_home)

    for name in CODEX_HOME_PRIVATE_FILES:
        f = worker_home / name
        assert not f.exists() and not f.is_symlink(), \
            f"{name} must not be created in worker_home"


def test_missing_shared_file_is_skipped(tmp_path):
    """If a shared file doesn't exist in parent_home it's silently skipped."""
    parent = tmp_path / "empty_parent"
    parent.mkdir()
    worker = tmp_path / "worker"

    isolator = WorkerIsolator()
    result = isolator.prepare_codex_home(parent, worker)

    # No symlinks should be created (nothing exists in parent)
    assert result.symlinks_created == []
    # Private dirs still created
    assert len(result.private_dirs_created) == len(CODEX_HOME_PRIVATE_DIRS)


def test_idempotent_if_worker_home_already_exists(parent_home, worker_home):
    """Calling prepare_codex_home twice should not fail."""
    isolator = WorkerIsolator()
    isolator.prepare_codex_home(parent_home, worker_home)
    # Second call — should not raise
    result = isolator.prepare_codex_home(parent_home, worker_home)
    assert result.worker_home == worker_home


def test_manifest_lists_symlinks_and_dirs(parent_home, worker_home):
    isolator = WorkerIsolator()
    result = isolator.prepare_codex_home(parent_home, worker_home)

    # auth.json, config.toml, plugins, skills were created in parent_home
    assert "auth.json" in result.symlinks_created
    assert "config.toml" in result.symlinks_created
    assert "plugins" in result.symlinks_created
    assert "skills" in result.symlinks_created
    assert set(result.private_dirs_created) == set(CODEX_HOME_PRIVATE_DIRS)


def test_prepare_worktree_missing_git_returns_error(tmp_path):
    """prepare_worktree should return a structured error if git is missing/fails."""
    isolator = WorkerIsolator()
    result = isolator.prepare_worktree(
        repo=tmp_path / "not_a_repo",
        worker_root=tmp_path / "worktree",
        branch="test-branch",
    )
    # Should not raise; should return success=False with error message
    assert result.success is False
    assert result.error is not None


def test_prepare_worktree_reuse_existing(tmp_path):
    """If worktree dir already exists and reuse=True, return it without git."""
    existing = tmp_path / "existing_worktree"
    existing.mkdir()

    isolator = WorkerIsolator()
    result = isolator.prepare_worktree(
        repo=tmp_path / "repo",
        worker_root=existing,
        branch="some-branch",
        reuse=True,
    )
    assert result.success is True
    assert result.reused is True
    assert result.path == existing


def test_prepare_worktree_no_reuse_existing_fails(tmp_path):
    """If worktree dir already exists and reuse=False, return error."""
    existing = tmp_path / "existing_worktree"
    existing.mkdir()

    isolator = WorkerIsolator()
    result = isolator.prepare_worktree(
        repo=tmp_path / "repo",
        worker_root=existing,
        branch="some-branch",
        reuse=False,
    )
    assert result.success is False
    assert result.error is not None
