"""Unit tests for AdversarialReviewer.

FACTORY_FORCE_MOCK=1 path — no LLM calls needed.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from autodev.agents.adversarial_reviewer import AdversarialReviewer
from autodev.schemas import AgentCard, AdversarialFinding, Severity, SeverityFinding


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Minimal repo fixture."""
    return tmp_path


# ---------------------------------------------------------------------------
# Test 1: as_agent_card returns correct schema
# ---------------------------------------------------------------------------

def test_as_agent_card_returns_agent_card() -> None:
    card = AdversarialReviewer.as_agent_card()
    assert isinstance(card, AgentCard)
    assert card.name == "adversarial"
    assert card.model_hint == "opus"
    assert "injection" in card.skills
    assert "auth-bypass" in card.skills


# ---------------------------------------------------------------------------
# Test 2: abuse path — subprocess shell=True detected as BLOCKER injection
# ---------------------------------------------------------------------------

def test_shell_injection_detected(tmp_repo: Path) -> None:
    (tmp_repo / "run.py").write_text(
        'import subprocess\nsubprocess.run(cmd, shell=True)\n',
        encoding="utf-8",
    )
    reviewer = AdversarialReviewer()
    findings = reviewer.review(str(tmp_repo))
    assert isinstance(findings, list)
    blockers = [f for f in findings if f.severity == Severity.BLOCKER]
    assert blockers, "Expected BLOCKER for shell=True injection"
    assert any("injection" in f.category or "shell" in f.title.lower() for f in blockers)


# ---------------------------------------------------------------------------
# Test 3: --force / no auth check — verify=False (SSL auth bypass) is BLOCKER
# ---------------------------------------------------------------------------

def test_ssl_verify_false_detected(tmp_repo: Path) -> None:
    (tmp_repo / "client.py").write_text(
        "import requests\nresponse = requests.get(url, verify=False)\n",
        encoding="utf-8",
    )
    reviewer = AdversarialReviewer()
    findings = reviewer.review(str(tmp_repo))
    assert any(
        f.severity == Severity.BLOCKER and (
            "verify" in f.title.lower() or "ssl" in f.title.lower()
            or "verification" in f.title.lower()
        )
        for f in findings
    ), "Expected BLOCKER for verify=False"


# ---------------------------------------------------------------------------
# Test 4: wide CORS wildcard detected as MAJOR
# ---------------------------------------------------------------------------

def test_wildcard_cors_detected(tmp_repo: Path) -> None:
    (tmp_repo / "server.py").write_text(
        "headers = {'Access-Control-Allow-Origin': '*'}\n",
        encoding="utf-8",
    )
    reviewer = AdversarialReviewer()
    findings = reviewer.review(str(tmp_repo))
    cors_findings = [f for f in findings if "cors" in f.title.lower() or "cors" in f.category]
    assert cors_findings, "Expected CORS wildcard finding"


# ---------------------------------------------------------------------------
# Test 5: review_adversarial returns AdversarialFinding objects
# ---------------------------------------------------------------------------

def test_review_adversarial_returns_rich_findings(tmp_repo: Path) -> None:
    (tmp_repo / "app.py").write_text(
        "eval(user_input)\n",
        encoding="utf-8",
    )
    reviewer = AdversarialReviewer()
    rich = reviewer.review_adversarial(str(tmp_repo))
    assert isinstance(rich, list)
    assert all(isinstance(f, AdversarialFinding) for f in rich)
    # eval() should trigger injection BLOCKER
    injection = [f for f in rich if f.attack_vector == "injection"]
    assert injection, "Expected injection finding for eval()"
    assert injection[0].severity_finding is not None


# ---------------------------------------------------------------------------
# Test 6: clean repo emits no blockers
# ---------------------------------------------------------------------------

def test_clean_repo_no_blockers(tmp_repo: Path) -> None:
    (tmp_repo / "clean.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    reviewer = AdversarialReviewer()
    findings = reviewer.review(str(tmp_repo))
    blockers = [f for f in findings if f.severity == Severity.BLOCKER]
    assert not blockers, f"Unexpected BLOCKERs in clean repo: {blockers}"
