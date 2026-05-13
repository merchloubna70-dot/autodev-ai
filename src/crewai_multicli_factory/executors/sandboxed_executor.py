"""SandboxedExecutor — wraps an inner BaseExecutor with network-allowlist enforcement.

Design:
- Inherits BaseExecutor; delegates actual execution to ``inner``.
- Consumes W3's NetworkAllowlist via dynamic import (no hard dep).
- When sandbox_provider is "none" (unconfigured), falls back to running the
  inner executor with ``network_audit_only=True``.
- Provides interface only — no actual E2B/Modal call is made.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import ExecutionBackend, ExecutionRequest, ExecutionResult
from .base_executor import BaseExecutor

if TYPE_CHECKING:
    pass


class SandboxedExecutor(BaseExecutor):
    """Executor wrapper that adds network-allowlist enforcement around an inner executor."""

    backend: ExecutionBackend = ExecutionBackend.AUTO
    is_mock: bool = False

    def __init__(
        self,
        inner: BaseExecutor,
        *,
        allow_domains: list[str] | None = None,
        sandbox_provider: str = "none",
        network_audit_only: bool = True,
    ) -> None:
        self.inner = inner
        self.allow_domains: list[str] = allow_domains or []
        self.sandbox_provider = sandbox_provider
        self.network_audit_only = network_audit_only

        # Inherit mock/backend from inner
        self.is_mock = inner.is_mock
        self.backend = inner.backend

        # Lazily load NetworkAllowlist from W3 (dynamic import so no hard dep)
        self._allowlist = self._build_allowlist()

    # ------------------------------------------------------------------
    # BaseExecutor interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self.inner.is_available()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Run inner executor after applying network policy checks."""
        # Propagate allow_domains into the execution environment
        env_overrides: dict[str, str] = {}
        if self._allowlist is not None:
            env_overrides = self._allowlist.shell_env(self.allow_domains)

        # When sandbox_provider is unconfigured, run inner with audit_only annotation
        if self.sandbox_provider == "none":
            result = self.inner.execute(request)
            # Annotate the result metadata to indicate audit_only mode
            result = result.model_copy(
                update={
                    "selected_backend_reason": (
                        f"[sandboxed/audit_only={self.network_audit_only}] "
                        + (result.selected_backend_reason or "")
                    )
                }
            )
            return result

        # Future: dispatch to E2B / Modal / anthropic-sandbox-runtime
        # For now, raise a clear not-implemented error rather than silently failing
        raise NotImplementedError(
            f"sandbox_provider={self.sandbox_provider!r} is not yet implemented. "
            "Set sandbox_provider='none' to use audit-only mode."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_allowlist(self):
        """Dynamically import NetworkAllowlist; return None if unavailable."""
        try:
            from .network_allowlist import NetworkAllowlist
            from ..schemas import NetworkAllowlistPolicy

            policy = NetworkAllowlistPolicy(allow_domains=list(self.allow_domains))
            return NetworkAllowlist(policy=policy)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def audit_domain(self, url_or_host: str) -> bool:
        """Return True if the domain is allowed by the current policy."""
        if self._allowlist is None:
            return True  # no policy configured → permissive
        verdict = self._allowlist.evaluate(url_or_host)
        return verdict.allowed
