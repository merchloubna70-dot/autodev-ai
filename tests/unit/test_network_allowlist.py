"""Tests for NetworkAllowlist — offline, no network calls."""
from __future__ import annotations

import pytest

from crewai_multicli_factory.executors.network_allowlist import NetworkAllowlist
from crewai_multicli_factory.schemas import NetworkAllowlistPolicy


def test_default_deny():
    """All requests denied by default with empty policy."""
    al = NetworkAllowlist()
    verdict = al.evaluate("https://example.com/api")
    assert verdict.allowed is False
    assert verdict.matched_rule is None
    assert "deny" in verdict.reason.lower()


def test_wildcard_domain_match():
    """*.github.com wildcard matches subdomains."""
    policy = NetworkAllowlistPolicy(allow_domains=["*.github.com"])
    al = NetworkAllowlist(policy)

    assert al.evaluate("https://api.github.com/repos").allowed is True
    assert al.evaluate("https://raw.githubusercontent.com").allowed is False  # different apex
    assert al.evaluate("https://github.com").allowed is True  # exact apex still matches via rule


def test_exact_domain_match():
    """Exact domain rule allows exact match only."""
    policy = NetworkAllowlistPolicy(allow_domains=["pypi.org"])
    al = NetworkAllowlist(policy)

    verdict = al.evaluate("https://pypi.org/simple/requests/")
    assert verdict.allowed is True
    assert verdict.matched_rule == "pypi.org"

    assert al.evaluate("https://sub.pypi.org").allowed is False


def test_cidr_match():
    """CIDR rule allows IPs within the range."""
    policy = NetworkAllowlistPolicy(
        allow_domains=[],
        allow_cidrs=["192.168.1.0/24"],
    )
    al = NetworkAllowlist(policy)

    assert al.evaluate("192.168.1.100").allowed is True
    assert al.evaluate("192.168.2.1").allowed is False


def test_typical_agent_egress(tmp_path):
    """Common agent egress domains can be allowed."""
    policy = NetworkAllowlistPolicy(
        allow_domains=["pypi.org", "*.github.com", "huggingface.co", "files.pythonhosted.org"]
    )
    al = NetworkAllowlist(policy)

    assert al.evaluate("https://pypi.org/simple/").allowed is True
    assert al.evaluate("https://api.github.com/repos/owner/repo").allowed is True
    assert al.evaluate("https://huggingface.co/models").allowed is True
    assert al.evaluate("https://files.pythonhosted.org/packages/foo.whl").allowed is True
    assert al.evaluate("https://malicious.example.com").allowed is False


def test_shell_env_dict_shape():
    """shell_env returns correct dict with FACTORY_NET_ALLOW key."""
    policy = NetworkAllowlistPolicy(allow_domains=["pypi.org", "*.github.com"])
    al = NetworkAllowlist(policy)
    env = al.shell_env()

    assert "FACTORY_NET_ALLOW" in env
    domains = env["FACTORY_NET_ALLOW"].split(",")
    assert "pypi.org" in domains
    assert "*.github.com" in domains


def test_shell_env_override():
    """shell_env accepts explicit allow_domains, overriding policy."""
    al = NetworkAllowlist()
    env = al.shell_env(allow_domains=["custom.example.com"])
    assert env["FACTORY_NET_ALLOW"] == "custom.example.com"
