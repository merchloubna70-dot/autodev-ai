"""Unit tests for InvestigatorAgent (BMAD-10).

All tests run without network or real gh CLI — failure modes are expected
to be silently skipped per hard rule 1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from autodev.agents.investigator import InvestigatorAgent
from autodev.schemas import CaseFile, EvidenceEntry, InvestigationInputKind

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Minimal repo fixture with a Python file."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "def hello():\n    raise ValueError('kaboom')\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def agent() -> InvestigatorAgent:
    return InvestigatorAgent()


# ---------------------------------------------------------------------------
# Test 1: ticket-id classification
# ---------------------------------------------------------------------------

def test_classify_ticket_id(agent):
    kind = agent._classify("PROJ-42", ".")
    assert kind == InvestigationInputKind.TICKET_ID


def test_classify_ticket_id_longer(agent):
    kind = agent._classify("ABC-1234", ".")
    assert kind == InvestigationInputKind.TICKET_ID


# ---------------------------------------------------------------------------
# Test 2: log-path classification
# ---------------------------------------------------------------------------

def test_classify_log_path(agent, tmp_repo):
    log = tmp_repo / "app.log"
    log.write_text("2026-01-01 ERROR something went wrong\n", encoding="utf-8")
    kind = agent._classify(str(log), str(tmp_repo))
    assert kind == InvestigationInputKind.LOG_PATH


# ---------------------------------------------------------------------------
# Test 3: error-msg classification
# ---------------------------------------------------------------------------

def test_classify_error_msg(agent):
    kind = agent._classify("TypeError: unsupported operand type(s) for +: 'int' and 'str'", ".")
    assert kind == InvestigationInputKind.ERROR_MSG


def test_classify_error_msg_traceback(agent):
    kind = agent._classify("Traceback (most recent call last): File 'x.py'", ".")
    assert kind == InvestigationInputKind.ERROR_MSG


# ---------------------------------------------------------------------------
# Test 4: code-area classification
# ---------------------------------------------------------------------------

def test_classify_code_area_glob(agent):
    kind = agent._classify("src/autodev/agents/*.py", ".")
    assert kind == InvestigationInputKind.CODE_AREA


def test_classify_code_area_dir(agent):
    kind = agent._classify("src/autodev/flows/", ".")
    assert kind == InvestigationInputKind.CODE_AREA


# ---------------------------------------------------------------------------
# Test 5: problem-description classification (prose fallback)
# ---------------------------------------------------------------------------

def test_classify_problem_desc(agent):
    kind = agent._classify(
        "The authentication module seems to be rejecting valid tokens intermittently.", "."
    )
    assert kind == InvestigationInputKind.PROBLEM_DESC


# ---------------------------------------------------------------------------
# Test 6: open_case returns a valid CaseFile
# ---------------------------------------------------------------------------

def test_open_case_ticket(agent):
    case = agent.open_case("PROJ-99", ".")
    assert isinstance(case, CaseFile)
    assert case.input_kind == InvestigationInputKind.TICKET_ID
    assert case.mode == "calibrating"
    assert case.case_id
    assert case.slug


# ---------------------------------------------------------------------------
# Test 7: collect_evidence — no crash on missing log file
# ---------------------------------------------------------------------------

def test_collect_evidence_missing_log_no_crash(agent):
    case = agent.open_case("/nonexistent/path/foo.log", ".")
    # force log-path kind
    case.input_kind = InvestigationInputKind.LOG_PATH
    result = agent.collect_evidence(case)
    # Should have at least one evidence entry (even the error placeholder)
    assert len(result.evidence) >= 1
    # Must not raise


# ---------------------------------------------------------------------------
# Test 8: collect_evidence for error_msg adds hypothesis
# ---------------------------------------------------------------------------

def test_collect_evidence_error_msg_adds_hypothesis(agent):
    case = agent.open_case("ValueError: division by zero in module foo", ".")
    result = agent.collect_evidence(case)
    assert any("Hypothesis" in h for h in result.hypotheses)


# ---------------------------------------------------------------------------
# Test 9: calibrate returns correct modes
# ---------------------------------------------------------------------------

def test_calibrate_defect_chasing_ticket(agent):
    case = agent.open_case("BUG-99", ".")
    mode = agent.calibrate(case)
    assert mode == "defect-chasing"


def test_calibrate_area_exploration_code_area(agent):
    case = agent.open_case("src/mymodule/*.py", ".")
    mode = agent.calibrate(case)
    assert mode == "area-exploration"


# ---------------------------------------------------------------------------
# Test 10: run() writes a case file and returns correct CaseFile
# ---------------------------------------------------------------------------

def test_run_writes_case_file(agent, tmp_repo):
    case = agent.run("DEMO-1", str(tmp_repo))
    assert case.file_path is not None
    assert Path(case.file_path).exists()
    content = Path(case.file_path).read_text(encoding="utf-8")
    assert "Case File" in content
    assert case.mode in ("defect-chasing", "area-exploration")


def test_run_file_path_under_dev_factory(agent, tmp_repo):
    case = agent.run("ValueError: boom in test suite", str(tmp_repo))
    assert case.file_path is not None
    assert ".dev-factory/investigations" in case.file_path


# ---------------------------------------------------------------------------
# Test 11: collect_evidence for code_area doesn't crash on missing glob
# ---------------------------------------------------------------------------

def test_collect_evidence_code_area_no_crash(agent):
    case = agent.open_case("nonexistent_path/**/*.py", ".")
    result = agent.collect_evidence(case)
    assert len(result.evidence) >= 1


# ---------------------------------------------------------------------------
# Test 12: EvidenceEntry has collected_at populated automatically
# ---------------------------------------------------------------------------

def test_evidence_entry_collected_at():
    e = EvidenceEntry(kind="file", path="x.py", snippet="hello")
    assert e.collected_at  # should be a non-empty ISO string


# ---------------------------------------------------------------------------
# Test 13: resume classification from existing .md file
# ---------------------------------------------------------------------------

def test_classify_resume(agent, tmp_repo):
    md_file = tmp_repo / "case.md"
    md_file.write_text("# Case File: test\n", encoding="utf-8")
    kind = agent._classify(str(md_file), str(tmp_repo))
    assert kind == InvestigationInputKind.RESUME


# ---------------------------------------------------------------------------
# Test 14: summarize produces expected sections
# ---------------------------------------------------------------------------

def test_summarize_sections(agent):
    case = agent.open_case("PROJ-7", ".")
    case.evidence = [EvidenceEntry(kind="issue", reference="PROJ-7", snippet="test issue")]
    case.hypotheses = ["Hypothesis #1: X causes Y"]
    case.next_steps = ["Do A", "Do B"]
    md = agent.summarize(case)
    assert "## Evidence" in md
    assert "## Hypotheses" in md
    assert "## Recommended Next Steps" in md
    assert "PROJ-7" in md
