"""WorkerIsolator — per-worker CODEX_HOME isolation via symlinks + private dirs.

Mirrors the isolation strategy from codex-fanout's ``make_worker_codex_home``
and ``make_worktree``:
  - Immutable / shared files are symlinked from parent → worker home (auth.json,
    config.toml, models_cache.json, …).  All workers share the same tokens and
    config without duplicating large files.
  - Mutable directories (sessions/, log/, cache/, …) are created as empty dirs
    inside worker_home so each worker gets its own private state.
  - Mutable top-level files (state_5.sqlite, history.jsonl, …) are intentionally
    *not* created — Codex will initialise them fresh on startup, preventing
    concurrent SQLite / jsonl write races.

The class is standalone: ``prepare_codex_home`` works purely with
``pathlib.Path`` and ``os.symlink``; no git operations are needed.
``prepare_worktree`` is optional and wraps ``git worktree add`` via subprocess.
Failures in ``prepare_worktree`` are returned as structured errors rather than
raised exceptions, so callers can decide how to surface them.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants (mirrors codex-fanout CODEX_HOME_SHARED / CODEX_HOME_PRIVATE_DIRS)
# ---------------------------------------------------------------------------

#: Files / dirs in parent CODEX_HOME that are immutable (read-only for workers).
#: Each is symlinked from parent_home into worker_home.
CODEX_HOME_SHARED: tuple[str, ...] = (
    "auth.json",
    "config.toml",
    "AGENTS.md",
    "installation_id",
    "version.json",
    "models_cache.json",
    "plugins",
    "skills",
    "vendor_imports",
    "computer-use",
    ".personality_migration",
)

#: Directories that each worker owns privately (created as empty dirs).
CODEX_HOME_PRIVATE_DIRS: tuple[str, ...] = (
    "sessions",
    "log",
    "cache",
    "shell_snapshots",
    "tmp",
    ".tmp",
    "sqlite",
    "memories",
)

#: Top-level mutable files — intentionally NOT created or symlinked.
#: Codex initialises them fresh; sharing would cause SQLite / jsonl races.
#: Listed here as schema documentation only.
CODEX_HOME_PRIVATE_FILES: tuple[str, ...] = (
    "state_5.sqlite",
    "state_5.sqlite-shm",
    "state_5.sqlite-wal",
    "logs_2.sqlite",
    "logs_2.sqlite-shm",
    "logs_2.sqlite-wal",
    "history.jsonl",
    "session_index.jsonl",
    ".codex-global-state.json",
    ".codex-global-state.json.bak",
)


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------


@dataclass
class WorktreeResult:
    """Result of ``prepare_worktree`` — success or structured error."""

    path: Path | None = None
    success: bool = False
    error: str | None = None
    reused: bool = False


@dataclass
class CodexHomeResult:
    """Manifest of what ``prepare_codex_home`` created."""

    worker_home: Path
    symlinks_created: list[str] = field(default_factory=list)
    private_dirs_created: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# WorkerIsolator
# ---------------------------------------------------------------------------


class WorkerIsolator:
    """Utility class for worker-level filesystem isolation.

    Usage (Codex home only — no git required)::

        isolator = WorkerIsolator()
        result = isolator.prepare_codex_home(
            parent_home=Path.home() / ".codex",
            worker_home=Path("/tmp/workers/worker-0/.codex"),
        )
        # result.symlinks_created, result.private_dirs_created

    Usage (with git worktree)::

        wt = isolator.prepare_worktree(
            repo=Path("/path/to/repo"),
            worker_root=Path("/tmp/workers/worker-0"),
            branch="fix/my-bug-0",
        )
        if not wt.success:
            print(f"worktree failed: {wt.error}")
    """

    # ------------------------------------------------------------------
    # Codex home isolation
    # ------------------------------------------------------------------

    def prepare_codex_home(
        self,
        parent_home: Path,
        worker_home: Path,
    ) -> CodexHomeResult:
        """Set up an isolated CODEX_HOME for one worker.

        - Creates ``worker_home`` (and parents) if absent.
        - Symlinks each entry in ``CODEX_HOME_SHARED`` that exists in
          ``parent_home`` into ``worker_home`` (skips if already present).
        - Creates each entry in ``CODEX_HOME_PRIVATE_DIRS`` as an empty
          directory inside ``worker_home``.
        - Does NOT create or symlink ``CODEX_HOME_PRIVATE_FILES`` — Codex
          will initialise them fresh.

        Returns a ``CodexHomeResult`` manifest.
        """
        worker_home = Path(worker_home)
        parent_home = Path(parent_home)
        worker_home.mkdir(parents=True, exist_ok=True)

        result = CodexHomeResult(worker_home=worker_home)

        # Immutable symlinks
        for name in CODEX_HOME_SHARED:
            src = parent_home / name
            dst = worker_home / name
            if not src.exists():
                continue
            if dst.exists() or dst.is_symlink():
                continue
            os.symlink(src, dst)
            result.symlinks_created.append(name)

        # Private mutable directories
        for name in CODEX_HOME_PRIVATE_DIRS:
            d = worker_home / name
            d.mkdir(parents=True, exist_ok=True)
            result.private_dirs_created.append(name)

        # CODEX_HOME_PRIVATE_FILES deliberately NOT created here —
        # see module docstring.
        _ = CODEX_HOME_PRIVATE_FILES  # noqa: F841  schema reference

        return result

    # ------------------------------------------------------------------
    # Git worktree
    # ------------------------------------------------------------------

    def prepare_worktree(
        self,
        repo: Path,
        worker_root: Path,
        branch: str,
        base: str = "HEAD",
        reuse: bool = False,
    ) -> WorktreeResult:
        """Create (or reuse) a git worktree for this worker.

        Returns a ``WorktreeResult`` — never raises on git failure so callers
        can log / fall back without try/except.

        Parameters
        ----------
        repo:
            Path to the main git repository.
        worker_root:
            Directory where the worktree will be checked out.
        branch:
            New branch name to create (or existing branch when reuse=True).
        base:
            Commit / ref to branch from (default ``HEAD``).
        reuse:
            If True and the worktree directory already exists, return it as-is.
        """
        repo = Path(repo)
        worker_root = Path(worker_root)

        if worker_root.exists():
            if reuse:
                return WorktreeResult(path=worker_root, success=True, reused=True)
            return WorktreeResult(
                success=False,
                error=f"worktree already exists and reuse=False: {worker_root}",
            )

        # Check whether the branch already exists in the repo
        try:
            list_result = subprocess.run(
                ["git", "branch", "--list", branch],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return WorktreeResult(success=False, error=f"git not available: {exc}")

        branch_exists = bool(list_result.stdout.strip())

        if branch_exists:
            if not reuse:
                return WorktreeResult(
                    success=False,
                    error=f"branch already exists and reuse=False: {branch}",
                )
            cmd = ["git", "worktree", "add", str(worker_root), branch]
        else:
            cmd = ["git", "worktree", "add", "-b", branch, str(worker_root), base]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return WorktreeResult(success=False, error=f"git worktree add failed: {exc}")

        if proc.returncode != 0:
            return WorktreeResult(
                success=False,
                error=f"git worktree add exited {proc.returncode}: {proc.stderr.strip()}",
            )

        return WorktreeResult(path=worker_root, success=True, reused=False)
