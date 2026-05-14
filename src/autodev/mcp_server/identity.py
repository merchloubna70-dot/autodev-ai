"""Per-caller identity and scope-based authorization for the autodev MCP server.

Supports two operating modes:
- Legacy mode (AUTODEV_MCP_IDENTITIES unset): single shared token via
  AUTODEV_A2A_TOKEN, all callers get full scopes, caller_id = "legacy_shared_token".
- Per-caller mode (AUTODEV_MCP_IDENTITIES = path/to/identities.json): each
  caller has its own hashed token, display name, and scope set.

Identity registry JSON format:
    {
      "caller-id-1": {
        "display_name": "CI Bot",
        "scopes": ["mcp:read", "mcp:write"],
        "hashed_token": "sha256:<hex>",
        "expires_at": "2027-01-01T00:00:00Z"   // optional ISO-8601
      },
      ...
    }

Scope vocabulary:
    mcp:read   — read-only tools (scan, classify, list_runs, report, release_check)
    mcp:write  — write tools (create_prd, run_issue dry-run, deliver_project dry-run,
                  roundtable)
    mcp:apply  — destructive apply-mode tools (deliver_project apply, run_issue apply)
"""
from __future__ import annotations

import contextvars
import functools
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from pydantic import BaseModel
    _PYDANTIC_AVAILABLE = True
except ImportError:
    _PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# All known scopes
# ---------------------------------------------------------------------------

SCOPE_READ = "mcp:read"
SCOPE_WRITE = "mcp:write"
SCOPE_APPLY = "mcp:apply"

ALL_SCOPES = [SCOPE_READ, SCOPE_WRITE, SCOPE_APPLY]

# Caller ID used in legacy single-token mode
LEGACY_CALLER_ID = "legacy_shared_token"


# ---------------------------------------------------------------------------
# CallerIdentity model
# ---------------------------------------------------------------------------

if _PYDANTIC_AVAILABLE:
    class CallerIdentity(BaseModel):
        """Represents an authenticated caller with its identity and scope set."""

        caller_id: str
        display_name: str
        scopes: list[str]
        expires_at: datetime | None = None

        def has_scope(self, scope: str) -> bool:
            """Return True if this identity has the given scope."""
            return scope in self.scopes

        def is_expired(self) -> bool:
            """Return True if the identity has an expiry and it is in the past."""
            if self.expires_at is None:
                return False
            return datetime.now(tz=timezone.utc) >= self.expires_at

else:
    # Fallback for environments without pydantic (tests mock this anyway)
    class CallerIdentity:  # type: ignore[no-redef]
        """Represents an authenticated caller with its identity and scope set."""

        def __init__(
            self,
            caller_id: str,
            display_name: str,
            scopes: list[str],
            expires_at: datetime | None = None,
        ) -> None:
            self.caller_id = caller_id
            self.display_name = display_name
            self.scopes = list(scopes)
            self.expires_at = expires_at

        def has_scope(self, scope: str) -> bool:
            return scope in self.scopes

        def is_expired(self) -> bool:
            if self.expires_at is None:
                return False
            return datetime.now(tz=timezone.utc) >= self.expires_at

        def model_dump(self) -> dict[str, Any]:
            return {
                "caller_id": self.caller_id,
                "display_name": self.display_name,
                "scopes": self.scopes,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            }


# ---------------------------------------------------------------------------
# Request-scoped current caller context var
# ---------------------------------------------------------------------------

_current_caller: contextvars.ContextVar[CallerIdentity | None] = (
    contextvars.ContextVar("_current_caller", default=None)
)


def get_current_caller() -> CallerIdentity | None:
    """Return the CallerIdentity for the currently-executing request, or None."""
    return _current_caller.get()


def set_current_caller(identity: CallerIdentity | None) -> contextvars.Token:
    """Set the current caller identity; returns a reset token."""
    return _current_caller.set(identity)


# ---------------------------------------------------------------------------
# Token hashing
# ---------------------------------------------------------------------------

def _hash_token(token: str) -> str:
    """Return the canonical sha256 hex digest prefixed with 'sha256:'."""
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# IdentityRegistry
# ---------------------------------------------------------------------------

class IdentityRegistry:
    """Loads and queries per-caller identities from a JSON file.

    File format (JSON object keyed by caller_id):
        {
          "<caller_id>": {
            "display_name": "<human label>",
            "scopes": ["mcp:read", "mcp:write"],
            "hashed_token": "sha256:<64-hex-chars>",
            "expires_at": "<ISO-8601 datetime or null>"  // optional
          }
        }

    The registry builds an O(1) lookup table from hashed_token → CallerIdentity
    on load so authenticate() is constant-time regardless of registry size.
    """

    def __init__(self, identities_path: str | Path) -> None:
        self._path = Path(identities_path)
        # hashed_token (str) -> CallerIdentity
        self._by_hash: dict[str, CallerIdentity] = {}
        self._load()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load(self) -> None:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(
                f"Identity registry at {self._path} must be a JSON object"
            )
        for caller_id, entry in raw.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Entry for caller_id={caller_id!r} must be a JSON object"
                )
            hashed_token: str = entry["hashed_token"]
            scopes: list[str] = entry.get("scopes", [])
            display_name: str = str(entry.get("display_name") or caller_id)
            expires_at_raw: str | None = entry.get("expires_at")

            expires_at: datetime | None = None
            if expires_at_raw:
                expires_at = datetime.fromisoformat(expires_at_raw)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

            identity = CallerIdentity(
                caller_id=caller_id,
                display_name=display_name,
                scopes=scopes,
                expires_at=expires_at,
            )
            self._by_hash[hashed_token] = identity

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def authenticate(self, token: str) -> CallerIdentity | None:
        """Return the CallerIdentity for *token*, or None if not found / expired.

        Performs an O(1) lookup by sha256(token) against the loaded registry.
        Returns None for unknown tokens and for identities whose expires_at is in
        the past.
        """
        hashed = _hash_token(token)
        identity = self._by_hash.get(hashed)
        if identity is None:
            return None
        if identity.is_expired():
            return None
        return identity

    def __len__(self) -> int:
        return len(self._by_hash)


# ---------------------------------------------------------------------------
# Scope-check decorator
# ---------------------------------------------------------------------------

def requires_scope(scope: str):
    """Decorator that raises PermissionError if the current caller lacks *scope*.

    Usage:
        @requires_scope("mcp:apply")
        def my_handler(args):
            ...

    Raises:
        PermissionError: if no caller is set in context or the caller lacks the scope.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            caller = get_current_caller()
            if caller is None:
                raise PermissionError(
                    f"No authenticated caller in context; scope {scope!r} required"
                )
            if not caller.has_scope(scope):
                raise PermissionError(
                    f"Caller {caller.caller_id!r} lacks required scope {scope!r}"
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Convenience: build a legacy identity
# ---------------------------------------------------------------------------

def _make_legacy_identity() -> CallerIdentity:
    """Return a full-scope identity for legacy single-token mode."""
    return CallerIdentity(
        caller_id=LEGACY_CALLER_ID,
        display_name="Legacy Shared Token",
        scopes=ALL_SCOPES,
        expires_at=None,
    )


# ---------------------------------------------------------------------------
# Registry factory from environment
# ---------------------------------------------------------------------------

_ENV_IDENTITIES = "AUTODEV_MCP_IDENTITIES"


def load_registry_from_env() -> IdentityRegistry | None:
    """Load the IdentityRegistry from AUTODEV_MCP_IDENTITIES env var path.

    Returns None if the env var is not set (legacy mode active).
    Raises FileNotFoundError or ValueError if the path is set but invalid.
    """
    path = os.environ.get(_ENV_IDENTITIES)
    if not path:
        return None
    return IdentityRegistry(path)
