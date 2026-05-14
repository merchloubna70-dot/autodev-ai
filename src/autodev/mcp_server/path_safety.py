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
        # SSH key files (no extension — not caught by *.key / *.pem globs)
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_xmss",
        "authorized_keys",
        "known_hosts",
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

# SSH key basename prefixes — blocks id_rsa.pub, id_ed25519.old, etc.
_SSH_KEY_PREFIXES: tuple[str, ...] = (
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_xmss",
)

# Absolute path prefixes that are always off-limits for MCP operations.
# These cover system-file locations that are never a legitimate project repo.
# Paths under /tmp, /Users, /home, /var/folders etc. are still allowed
# because they can legitimately host project directories.
#
# Note: on macOS /etc, /tmp, /var etc. are symlinks under /private/ —
# include both the canonical symlink form and the /private/ resolved form so
# that Path.resolve() and raw-string matching both work.
_ABSOLUTE_REJECT_PREFIXES: tuple[str, ...] = (
    "/etc/",
    "/etc",           # bare /etc itself
    "/private/etc/",  # macOS: /etc -> /private/etc
    "/private/etc",
    "/root/",
    "/root",
    "/private/root/",
    "/private/root",
    "/proc/",
    "/proc",
    "/sys/",
    "/sys",
    "/dev/",
    "/dev",
    "/boot/",
    "/boot",
    "/.ssh/",         # /home/.../.ssh handled by basename checks; block bare /.ssh
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

    # 0. Absolute path: reject if the resolved path starts with a protected
    #    system-directory prefix.  Legitimate absolute project paths under
    #    /tmp, /Users, /home, /var, etc. are still allowed; this only blocks
    #    known system trees (/etc, /root, /proc, /sys, /dev, /boot).
    if Path(path_str).is_absolute():
        # Normalise with a trailing separator so prefix matching is exact.
        resolved_str = str(Path(path_str).resolve())
        for prefix in _ABSOLUTE_REJECT_PREFIXES:
            if resolved_str == prefix.rstrip("/") or resolved_str.startswith(
                prefix if prefix.endswith("/") else prefix + "/"
            ):
                raise MCPPathSafetyError(_REJECT_MSG)

    # 1. Path traversal
    try:
        parts = PurePosixPath(path_str).parts
    except Exception:
        parts = ()
    if ".." in parts or ".." in path_str.split("/") or ".." in path_str.split("\\"):
        raise MCPPathSafetyError(_REJECT_MSG)

    # 2 & 3 & 4 & 5: operate on the last component only to avoid false positives
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

    # 5. SSH key basename prefix — catches id_rsa.pub, id_ed25519.old, etc.
    for prefix in _SSH_KEY_PREFIXES:
        if basename.startswith(prefix):
            raise MCPPathSafetyError(_REJECT_MSG)
