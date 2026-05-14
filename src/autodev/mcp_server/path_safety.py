"""Preflight path-safety validator for MCP tools.

Checks any path-like parameter *before* the handler touches file contents.
Raises ``MCPPathSafetyError`` on violation; callers convert to MCP isError.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class MCPPathSafetyError(ValueError):
    """Raised when a path fails the preflight safety check."""


# ---------------------------------------------------------------------------
# Rejection patterns
# ---------------------------------------------------------------------------

# Exact basenames to block (case-sensitive; lower comparison applied below)
_EXACT_REJECT: frozenset[str] = frozenset(
    {
        ".env",
        "credentials.json",
        "secrets.toml",
    }
)

# Glob patterns matched against the basename (lower-cased)
_GLOB_REJECT: tuple[str, ...] = (
    ".env.*",   # .env.production, .env.local, .env.staging, …
    "*.pem",
    "*.key",
)

# Substrings that must NOT appear in the final path component (basename)
_BASENAME_SUBSTRINGS: tuple[str, ...] = (
    "secret",
    "token",
    "credential",
)

# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def _validate_safe_path(path: str | Path, *, role: str = "path") -> None:
    """Raise ``MCPPathSafetyError`` if *path* matches a secret-file pattern.

    Checks (in order):
    1. Path traversal — any ``..`` segment.
    2. Exact basename match against ``_EXACT_REJECT``.
    3. Glob match against ``_GLOB_REJECT`` patterns.
    4. Sensitive-substring match in the **basename only** (not parent dirs).

    Args:
        path: The path string or ``Path`` object supplied by the caller.
        role: Human-readable label for the parameter name (used in error msg).

    Raises:
        MCPPathSafetyError: Always with the message
            ``"Path rejected: matches secret-file pattern"`` — the original
            path is intentionally omitted to avoid leaking it in error output.
    """
    _REJECT_MSG = "Path rejected: matches secret-file pattern"

    path_str = str(path)

    # 1. Path traversal
    try:
        parts = PurePosixPath(path_str).parts
    except Exception:
        parts = ()
    if ".." in parts or ".." in path_str.split("/") or ".." in path_str.split("\\"):
        raise MCPPathSafetyError(_REJECT_MSG)

    # 2 & 3 & 4: operate on the last component only to avoid false positives
    #    like /Users/secret/dev/repo  (parent dir named "secret")
    basename = Path(path_str).name.lower()  # empty string for bare "/"

    # 2. Exact
    if basename in _EXACT_REJECT:
        raise MCPPathSafetyError(_REJECT_MSG)

    # 3. Glob
    for pattern in _GLOB_REJECT:
        if fnmatch.fnmatch(basename, pattern):
            raise MCPPathSafetyError(_REJECT_MSG)

    # 4. Substring in basename
    for substr in _BASENAME_SUBSTRINGS:
        if substr in basename:
            raise MCPPathSafetyError(_REJECT_MSG)
