"""Tests for WorkerIsolator symlink-escape / path-traversal hardening (R3-H F-03).

Attack vectors covered:
  1. Symlink target outside parent_home → WorkerIsolatorPathEscapeError
  2. Branch name with ".." rejected
  3. Branch name with "/" in middle rejected
  4. Branch name with NUL byte rejected
  5. Cleanup path outside worktree_root → WorkerIsolatorPathEscapeError
  6. Valid symlink target inside root → success
  7. CODEX_HOME env override pointing outside worktree_root rejected
  8. Happy-path full lifecycle (prepare_codex_home + cleanup_worktree)
  9. Cleanup of non-existent path is idempotent
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from autodev.executors.worker_isolator import (
    WorkerIsolator,
    WorkerIsolatorPathEscapeError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parent_home(tmp_path: Path) -> Path:
    """Create a minimal parent_home structure with one shared file."""
    parent = tmp_path / "parent_home"
    parent.mkdir()
    # Create a real file that worker can symlink
    (parent / "auth.json").write_text('{"token": "test"}')
    return parent


# ---------------------------------------------------------------------------
# 1. Symlink target outside parent_home raises WorkerIsolatorPathEscapeError
# ---------------------------------------------------------------------------


def test_symlink_target_outside_parent_home_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A symlink src that resolves outside parent_home must be rejected."""
    # Clear any ambient CODEX_HOME so it doesn't interfere
    monkeypatch.delenv("CODEX_HOME", raising=False)

    parent_home = tmp_path / "parent_home"
    parent_home.mkdir()
    worker_home = tmp_path / "worker_home"

    # Create a legitimate-looking entry inside parent_home that is actually a
    # symlink pointing outside of it (simulates a pre-placed malicious symlink).
    escape_target = tmp_path / "secret_file"
    escape_target.write_text("sensitive data")

    # Plant a symlink inside parent_home that points outside
    malicious_entry = parent_home / "auth.json"
    malicious_entry.symlink_to(escape_target)

    isolator = WorkerIsolator(worktree_root=tmp_path)

    with pytest.raises(WorkerIsolatorPathEscapeError, match="outside root"):
        isolator.prepare_codex_home(
            parent_home=parent_home,
            worker_home=worker_home,
        )


# ---------------------------------------------------------------------------
# 2. Branch name with ".." rejected
# ---------------------------------------------------------------------------


def test_branch_name_with_dotdot_raises(tmp_path: Path) -> None:
    """Branch names containing '..' must raise WorkerIsolatorPathEscapeError."""
    isolator = WorkerIsolator(worktree_root=tmp_path)

    with pytest.raises(WorkerIsolatorPathEscapeError):
        isolator.prepare_worktree(
            repo=tmp_path,
            worker_root=tmp_path / "wt",
            branch="../evil",
        )


def test_branch_name_bare_dotdot_raises(tmp_path: Path) -> None:
    """A bare '..' branch name must be rejected."""
    isolator = WorkerIsolator(worktree_root=tmp_path)

    with pytest.raises(WorkerIsolatorPathEscapeError):
        isolator.prepare_worktree(
            repo=tmp_path,
            worker_root=tmp_path / "wt",
            branch="..",
        )


# ---------------------------------------------------------------------------
# 3. Branch name with "/" in middle rejected
# ---------------------------------------------------------------------------


def test_branch_name_with_slash_raises(tmp_path: Path) -> None:
    """Branch names containing '/' must raise WorkerIsolatorPathEscapeError."""
    isolator = WorkerIsolator(worktree_root=tmp_path)

    with pytest.raises(WorkerIsolatorPathEscapeError, match="'/'"):
        isolator.prepare_worktree(
            repo=tmp_path,
            worker_root=tmp_path / "wt",
            branch="feat/evil-branch",
        )


# ---------------------------------------------------------------------------
# 4. Branch name with NUL byte rejected
# ---------------------------------------------------------------------------


def test_branch_name_with_nul_byte_raises(tmp_path: Path) -> None:
    """Branch names containing NUL bytes must raise WorkerIsolatorPathEscapeError."""
    isolator = WorkerIsolator(worktree_root=tmp_path)

    with pytest.raises(WorkerIsolatorPathEscapeError, match="NUL"):
        isolator.prepare_worktree(
            repo=tmp_path,
            worker_root=tmp_path / "wt",
            branch="evil\x00branch",
        )


# ---------------------------------------------------------------------------
# 5. Cleanup with path outside root refuses to rm-rf
# ---------------------------------------------------------------------------


def test_cleanup_outside_root_raises(tmp_path: Path) -> None:
    """cleanup_worktree must refuse to rmtree a path outside worktree_root."""
    # Use a narrow root so that tmp_path itself is outside it
    narrow_root = tmp_path / "allowed_root"
    narrow_root.mkdir()

    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    (outside_dir / "important.txt").write_text("do not delete")

    isolator = WorkerIsolator(worktree_root=narrow_root)

    with pytest.raises(WorkerIsolatorPathEscapeError, match="outside root"):
        isolator.cleanup_worktree(outside_dir)

    # The directory must NOT have been removed
    assert outside_dir.exists(), "cleanup_worktree must not remove path outside root"


# ---------------------------------------------------------------------------
# 6. Valid symlink target inside root succeeds
# ---------------------------------------------------------------------------


def test_valid_symlink_target_inside_root_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A symlink target that resolves inside parent_home must succeed."""
    # Clear any ambient CODEX_HOME that would be outside worktree_root
    monkeypatch.delenv("CODEX_HOME", raising=False)

    parent_home = _make_parent_home(tmp_path)
    worker_home = tmp_path / "worker_home"

    isolator = WorkerIsolator(worktree_root=tmp_path)
    result = isolator.prepare_codex_home(
        parent_home=parent_home,
        worker_home=worker_home,
    )

    assert "auth.json" in result.symlinks_created
    assert (worker_home / "auth.json").is_symlink()
    # The symlink target must resolve to the original file inside parent_home
    assert (worker_home / "auth.json").resolve() == (parent_home / "auth.json").resolve()


# ---------------------------------------------------------------------------
# 7. CODEX_HOME env override pointing outside worktree_root is rejected
# ---------------------------------------------------------------------------


def test_codex_home_env_outside_worktree_root_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CODEX_HOME env override pointing outside worktree_root must raise."""
    # Use a narrow worktree_root; CODEX_HOME will point somewhere outside it
    narrow_root = tmp_path / "narrow_root"
    narrow_root.mkdir()
    parent_home = narrow_root / "parent_home"
    parent_home.mkdir()
    (parent_home / "auth.json").write_text('{"token": "test"}')
    worker_home = narrow_root / "worker_home"

    # Point CODEX_HOME to tmp_path which is the *parent* of narrow_root — outside
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))

    isolator = WorkerIsolator(worktree_root=narrow_root)

    with pytest.raises(WorkerIsolatorPathEscapeError, match="CODEX_HOME"):
        isolator.prepare_codex_home(
            parent_home=parent_home,
            worker_home=worker_home,
        )


# ---------------------------------------------------------------------------
# 8. Happy-path full lifecycle (prepare_codex_home + cleanup_worktree)
# ---------------------------------------------------------------------------


def test_happy_path_full_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full lifecycle: prepare_codex_home creates dirs/links, cleanup removes."""
    # Clear any ambient CODEX_HOME that would be outside worktree_root
    monkeypatch.delenv("CODEX_HOME", raising=False)

    parent_home = _make_parent_home(tmp_path)
    workers_root = tmp_path / "workers"
    workers_root.mkdir()
    worker_home = workers_root / "worker-0" / ".codex"

    isolator = WorkerIsolator(worktree_root=tmp_path)
    result = isolator.prepare_codex_home(
        parent_home=parent_home,
        worker_home=worker_home,
    )

    assert worker_home.exists()
    assert "auth.json" in result.symlinks_created
    assert len(result.private_dirs_created) > 0

    # Cleanup — must succeed without raising
    isolator.cleanup_worktree(worker_home)
    assert not worker_home.exists()


# ---------------------------------------------------------------------------
# 9. Cleanup of non-existent path is idempotent
# ---------------------------------------------------------------------------


def test_cleanup_nonexistent_path_is_idempotent(tmp_path: Path) -> None:
    """cleanup_worktree on a non-existent path inside root must be a no-op."""
    root = tmp_path / "workers"
    root.mkdir()
    ghost_path = root / "worker-99"
    assert not ghost_path.exists()

    isolator = WorkerIsolator(worktree_root=root)
    # Must not raise
    isolator.cleanup_worktree(ghost_path)
    # Still doesn't exist — no side effects
    assert not ghost_path.exists()
