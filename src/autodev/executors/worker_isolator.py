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

Security hardening (R3-H / R4-C)
----------------------------------
* Symlink targets are resolved with ``strict=True`` before creation; any target
  that resolves outside ``parent_home`` raises ``WorkerIsolatorPathEscapeError``.
* Branch names are validated — ``..`` traversal sequences and NUL bytes are
  rejected.  Shell-injection metacharacters (``$(``, backtick, ``;``, ``&&``,
  ``||``, ``|``, ``>``, ``<``, newlines / control chars) are also rejected to
  prevent command injection if a branch name is ever interpolated into a shell
  string.  Leading ``-`` and leading/trailing whitespace are rejected to prevent
  git flag injection and accidental misuse.
* Cleanup (``rmtree``) asserts the resolved path is inside the configured
  worktree root; out-of-root paths raise ``WorkerIsolatorPathEscapeError``.
* CODEX_HOME env-var overrides pointing outside the allowed root are rejected.

Residual TOCTOU note
---------------------
The symlink ``os.symlink(src, dst)`` syscall is atomic on POSIX, so there is no
race between our resolve check and the link creation (F-03 attack surface
closed).  However, ``shutil.rmtree`` on the cleanup path is *not* atomic: an
adversary with write access to the parent directory could race a rename between
our ``is_relative_to`` check and the actual ``rmtree`` call (TOCTOU on cleanup).
This risk is accepted and documented; mitigations (e.g. ``AT_REMOVEDIR`` via
low-level fd tricks) are out of scope for this iteration.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WorkerIsolatorPathEscapeError(Exception):
    """Raised when a resolved path would escape the allowed root directory.

    This covers:
    * Symlink targets that resolve outside ``parent_home``.
    * Branch names / path components containing traversal sequences.
    * Cleanup targets that resolve outside the configured worktree root.
    * CODEX_HOME env-var overrides pointing outside the allowed root.
    """


class BranchNameInjectionError(WorkerIsolatorPathEscapeError):
    """Raised when a branch name contains shell-injection metacharacters or
    other dangerous patterns that could lead to command injection or path
    traversal if the name is interpolated into a shell command.

    This is a subclass of ``WorkerIsolatorPathEscapeError`` so existing callers
    that catch the parent class continue to work without modification.
    """


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

    Parameters
    ----------
    worktree_root:
        The filesystem root that all worktrees and worker homes must be
        contained within.  Used by cleanup helpers to prevent rm-rf escapes.
        Defaults to ``/tmp`` if not supplied.
    """

    def __init__(self, worktree_root: Path | None = None) -> None:
        # Default to /tmp so that accidental cleanup calls don't escape to /
        self._worktree_root: Path = Path(worktree_root) if worktree_root else Path("/tmp")
        # Track whether caller explicitly provided a root; only then do we
        # enforce the CODEX_HOME env check (to preserve backwards compatibility
        # with existing callers that construct WorkerIsolator() with no args).
        self._root_explicitly_set: bool = worktree_root is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_branch_name(branch: str) -> None:
        """Reject branch names that could cause path traversal or shell injection.

        Raises ``BranchNameInjectionError`` if the branch name contains any
        dangerous characters or patterns.

        Allowed examples: ``feature/foo``, ``fix/issue-123``, ``main``,
        ``release/v0.1.0a1``, ``chore/docs-update``.

        Rejected patterns
        -----------------
        * NUL byte
        * ``..`` path traversal (any ``/``-delimited component that is ``..``)
        * ``$(`` or ``)`` — command substitution
        * Backtick — alternative command substitution
        * ``;`` — shell statement separator
        * ``&&`` or ``||`` — shell logical operators
        * ``|`` — pipe
        * ``>`` or ``<`` — redirection (including ``>>`` / ``<<``)
        * Newline (``\\n``) or carriage-return (``\\r``) or ASCII control chars (< 0x20)
        * Leading ``-`` — would be interpreted as a git flag
        * Leading or trailing whitespace
        """
        # NUL byte
        if "\x00" in branch:
            raise BranchNameInjectionError(
                f"Branch name contains NUL byte: {branch!r}"
            )

        # Leading/trailing whitespace
        if branch != branch.strip():
            raise BranchNameInjectionError(
                f"Branch name has leading or trailing whitespace: {branch!r}"
            )

        # Leading dash (git flag injection)
        if branch.startswith("-"):
            raise BranchNameInjectionError(
                f"Branch name starts with '-' (would be interpreted as a git flag): {branch!r}"
            )

        # Newline / carriage-return / ASCII control characters (< 0x20, excluding tab
        # which is already caught by the whitespace check above, but we catch all < 0x20)
        for ch in branch:
            if ord(ch) < 0x20:
                raise BranchNameInjectionError(
                    f"Branch name contains control character (ord={ord(ch):#04x}): {branch!r}"
                )

        # Shell injection metacharacters
        _SHELL_PATTERNS = (
            ("$(", "command substitution '$('"),
            ("`", "command substitution backtick '`'"),
            (";", "shell statement separator ';'"),
            ("&&", "shell logical operator '&&'"),
            ("||", "shell logical operator '||'"),
            ("|", "pipe '|'"),
            (">", "redirection '>'"),
            ("<", "redirection '<'"),
        )
        for pattern, description in _SHELL_PATTERNS:
            if pattern in branch:
                raise BranchNameInjectionError(
                    f"Branch name contains {description}: {branch!r}"
                )

        # Path traversal: check each slash-delimited component for ".."
        parts = branch.split("/")
        for part in parts:
            if part == "..":
                raise BranchNameInjectionError(
                    f"Branch name contains '..' path traversal component: {branch!r}"
                )

    @staticmethod
    def _assert_inside(resolved: Path, root: Path, label: str) -> None:
        """Assert ``resolved`` is inside ``root``; raise otherwise."""
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise WorkerIsolatorPathEscapeError(
                f"{label}: resolved path {resolved} is outside root {root}"
            ) from exc

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
          Before creating each symlink, the source is resolved strictly and
          verified to be inside ``parent_home``; a traversal attempt raises
          ``WorkerIsolatorPathEscapeError``.
        - Creates each entry in ``CODEX_HOME_PRIVATE_DIRS`` as an empty
          directory inside ``worker_home``.
        - Does NOT create or symlink ``CODEX_HOME_PRIVATE_FILES`` — Codex
          will initialise them fresh.
        - If the ``CODEX_HOME`` environment variable is set, its resolved
          value must be inside ``parent_home`` or ``WorkerIsolatorPathEscapeError``
          is raised.

        Returns a ``CodexHomeResult`` manifest.

        Raises
        ------
        WorkerIsolatorPathEscapeError
            If any symlink target resolves outside ``parent_home``, or if
            the ``CODEX_HOME`` env override points outside ``worktree_root``.
        """
        worker_home = Path(worker_home)
        parent_home = Path(parent_home)

        # Validate CODEX_HOME env override if present.
        # Only enforced when worktree_root was explicitly set by the caller
        # (i.e. a security boundary was declared).  Legacy callers that
        # construct WorkerIsolator() without a worktree_root skip this check.
        env_codex_home = os.environ.get("CODEX_HOME") if self._root_explicitly_set else None
        if env_codex_home:
            env_path = Path(env_codex_home)
            if env_path.exists():
                resolved_env = env_path.resolve(strict=True)
            else:
                resolved_env = env_path.resolve()
            resolved_root = self._worktree_root.resolve()
            try:
                resolved_env.relative_to(resolved_root)
            except ValueError as exc:
                raise WorkerIsolatorPathEscapeError(
                    f"CODEX_HOME env override {env_codex_home!r} resolves to "
                    f"{resolved_env} which is outside worktree_root {self._worktree_root}"
                ) from exc

        worker_home.mkdir(parents=True, exist_ok=True)

        result = CodexHomeResult(worker_home=worker_home)

        resolved_parent = parent_home.resolve()

        # Immutable symlinks — validate each source before linking
        for name in CODEX_HOME_SHARED:
            src = parent_home / name
            dst = worker_home / name
            if not src.exists():
                continue
            if dst.exists() or dst.is_symlink():
                continue

            # Security: resolve strictly and assert inside parent_home
            resolved_src = src.resolve(strict=True)
            self._assert_inside(resolved_src, resolved_parent, f"symlink src '{name}'")

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

        Branch name validation is strict: traversal sequences, NUL bytes, and
        all shell-injection metacharacters are rejected with
        ``BranchNameInjectionError`` before any git subprocess is spawned.

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

        Raises
        ------
        BranchNameInjectionError
            If ``branch`` contains shell-injection metacharacters, path
            traversal sequences, NUL bytes, leading ``-``, or leading/trailing
            whitespace.  ``BranchNameInjectionError`` is a subclass of
            ``WorkerIsolatorPathEscapeError`` so existing callers continue to
            work.
        """
        repo = Path(repo)
        worker_root = Path(worker_root)

        # Security: validate branch name before any git invocation
        self._validate_branch_name(branch)

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

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_worktree(self, path: Path) -> None:
        """Safely remove a worktree directory.

        Asserts that the resolved path is inside ``self._worktree_root``
        before calling ``shutil.rmtree``.  If ``path`` does not exist, this
        method is a no-op (idempotent).

        Raises
        ------
        WorkerIsolatorPathEscapeError
            If the resolved path is outside ``self._worktree_root``.
        """
        path = Path(path)
        if not path.exists():
            return

        resolved = path.resolve()
        resolved_root = self._worktree_root.resolve()
        self._assert_inside(resolved, resolved_root, f"cleanup target '{path}'")

        shutil.rmtree(path)
