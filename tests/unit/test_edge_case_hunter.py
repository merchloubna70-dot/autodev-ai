"""Unit tests for EdgeCaseHunter — boundary/edge-case scanner.

Covers text patterns + AST-based heuristics; no LLM calls.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from autodev.agents.edge_case_hunter import EdgeCaseHunter, _ast_scan_python
from autodev.schemas import AgentCard, EdgeCasePattern, Severity, SeverityFinding


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# Test 1: as_agent_card returns correct schema
# ---------------------------------------------------------------------------

def test_as_agent_card_returns_agent_card() -> None:
    card = EdgeCaseHunter.as_agent_card()
    assert isinstance(card, AgentCard)
    assert card.name == "edge-case-hunter"
    assert card.model_hint == "sonnet"
    assert "nan" in card.skills
    assert "timezone" in card.skills


# ---------------------------------------------------------------------------
# Test 2: empty input pattern detected (length check comment)
# ---------------------------------------------------------------------------

def test_empty_input_unbuffered_read_detected(tmp_repo: Path) -> None:
    (tmp_repo / "reader.py").write_text(
        "data = f.read()\n",
        encoding="utf-8",
    )
    hunter = EdgeCaseHunter()
    findings = hunter.review(str(tmp_repo))
    assert any("read" in f.title.lower() or f.category == "huge" for f in findings), \
        "Expected huge/unbuffered-read finding"


# ---------------------------------------------------------------------------
# Test 3: unicode emoji file name — unicode category in results
# ---------------------------------------------------------------------------

def test_unicode_encode_detected(tmp_repo: Path) -> None:
    (tmp_repo / "encode.py").write_text(
        "text.encode()\n",
        encoding="utf-8",
    )
    hunter = EdgeCaseHunter()
    findings = hunter.review(str(tmp_repo))
    unicode_findings = [f for f in findings if "unicode" in f.category or "encode" in f.title.lower()]
    assert unicode_findings, "Expected unicode encode() finding"


# ---------------------------------------------------------------------------
# Test 4: AST division-without-zero-check Python pattern detection
# ---------------------------------------------------------------------------

def test_ast_division_without_zero_check(tmp_path: Path) -> None:
    p = tmp_path / "divider.py"
    p.write_text(
        "def ratio(a, b):\n    return a / b\n",
        encoding="utf-8",
    )
    patterns = _ast_scan_python(p, "divider.py")
    div_patterns = [ep for ep in patterns if ep.category == "numeric"]
    assert div_patterns, "Expected numeric/division-without-zero-guard pattern"
    assert div_patterns[0].severity_finding is not None
    assert div_patterns[0].severity_finding.severity == Severity.MAJOR


# ---------------------------------------------------------------------------
# Test 5: AST dict direct subscript access flagged
# ---------------------------------------------------------------------------

def test_ast_dict_subscript_flagged(tmp_path: Path) -> None:
    p = tmp_path / "access.py"
    p.write_text(
        'd = {"key": 1}\nval = d["key"]\n',
        encoding="utf-8",
    )
    patterns = _ast_scan_python(p, "access.py")
    dict_patterns = [ep for ep in patterns if "dict" in ep.hint.lower() or "subscript" in ep.hint.lower()]
    assert dict_patterns, "Expected dict subscript finding"


# ---------------------------------------------------------------------------
# Test 6: network timeout=None detected as MAJOR
# ---------------------------------------------------------------------------

def test_network_timeout_none_detected(tmp_repo: Path) -> None:
    (tmp_repo / "http_client.py").write_text(
        "import requests\nrequests.get(url, timeout=None)\n",
        encoding="utf-8",
    )
    hunter = EdgeCaseHunter()
    findings = hunter.review(str(tmp_repo))
    network = [f for f in findings if f.severity == Severity.MAJOR and "timeout" in f.title.lower()]
    assert network, "Expected MAJOR finding for timeout=None"


# ---------------------------------------------------------------------------
# Test 7: review_edge_cases returns EdgeCasePattern objects
# ---------------------------------------------------------------------------

def test_review_edge_cases_returns_rich(tmp_repo: Path) -> None:
    (tmp_repo / "tz.py").write_text(
        "from datetime import datetime\nnow = datetime.now()\n",
        encoding="utf-8",
    )
    hunter = EdgeCaseHunter()
    rich = hunter.review_edge_cases(str(tmp_repo))
    assert isinstance(rich, list)
    assert all(isinstance(ep, EdgeCasePattern) for ep in rich)
    tz = [ep for ep in rich if ep.category == "timezone"]
    assert tz, "Expected timezone finding for datetime.now()"
