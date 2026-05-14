"""NetworkAllowlist — policy surface for controlling agent egress.

Design:
- Default deny-all; caller must explicitly add domains or CIDRs.
- Wildcard domain support: *.github.com matches api.github.com, raw.githubusercontent.com, etc.
- CIDR matching via stdlib ipaddress (no external deps).
- .shell_env() returns a dict with FACTORY_NET_ALLOW for downstream sandbox runtimes.
- NO actual network enforcement here; real enforcement is SandboxedExecutor's concern.
"""
from __future__ import annotations

import fnmatch
import ipaddress
from collections.abc import Sequence

from ..schemas import AllowVerdict, NetworkAllowlistPolicy


class NetworkAllowlist:
    """Evaluate URLs / hostnames against a configurable allow-list policy."""

    def __init__(self, policy: NetworkAllowlistPolicy | None = None) -> None:
        self.policy = policy or NetworkAllowlistPolicy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, url_or_host: str) -> AllowVerdict:
        """Return an AllowVerdict for the given URL or hostname."""
        host = self._extract_host(url_or_host)

        # 1. Domain wildcard / exact match
        for rule in self.policy.allow_domains:
            if self._domain_matches(host, rule):
                return AllowVerdict(
                    target=url_or_host,
                    allowed=True,
                    matched_rule=rule,
                    reason=f"matched allow_domains rule '{rule}'",
                )

        # 2. CIDR match (only if host looks like an IP address)
        if self._is_ip(host):
            for cidr in self.policy.allow_cidrs:
                try:
                    net = ipaddress.ip_network(cidr, strict=False)
                    addr = ipaddress.ip_address(host)
                    if addr in net:
                        return AllowVerdict(
                            target=url_or_host,
                            allowed=True,
                            matched_rule=cidr,
                            reason=f"matched allow_cidrs rule '{cidr}'",
                        )
                except ValueError:
                    continue

        # 3. Default deny
        deny_reason = "default deny-all" if self.policy.default_deny else "no rule matched"
        return AllowVerdict(
            target=url_or_host,
            allowed=not self.policy.default_deny,
            matched_rule=None,
            reason=deny_reason,
        )

    def shell_env(self, allow_domains: Sequence[str] | None = None) -> dict[str, str]:
        """Return env vars for downstream sandbox runtimes.

        Uses allow_domains if provided, otherwise falls back to policy domains.
        """
        domains = list(allow_domains) if allow_domains is not None else self.policy.allow_domains
        return {"FACTORY_NET_ALLOW": ",".join(domains)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_host(url_or_host: str) -> str:
        """Extract the hostname from a URL or return the input as-is."""
        s = url_or_host
        # Strip scheme
        for scheme in ("https://", "http://", "ftp://"):
            if s.startswith(scheme):
                s = s[len(scheme):]
                break
        # Strip path / query / fragment
        s = s.split("/")[0].split("?")[0].split("#")[0]
        # Strip port
        if ":" in s and not s.startswith("["):
            s = s.rsplit(":", 1)[0]
        return s.lower()

    @staticmethod
    def _domain_matches(host: str, rule: str) -> bool:
        """Match host against rule, supporting *.example.com wildcards."""
        rule = rule.lower()
        if rule.startswith("*."):
            suffix = rule[1:]  # e.g. ".github.com"
            return host == rule[2:] or host.endswith(suffix)
        return fnmatch.fnmatch(host, rule)

    @staticmethod
    def _is_ip(host: str) -> bool:
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            return False
