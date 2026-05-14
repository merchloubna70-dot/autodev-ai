"""Unit tests for InvestigationFlow.

Real signatures:
  InvestigationFlow() -- no args
  InvestigationFlow.run(inp: InvestigationInput) -> CaseFile

InvestigationInput:
  input_token: str
  repo_path: str = "."

CaseFile:
  case_id, slug, input_token, input_kind, mode, hypotheses, evidence,
  next_steps, outcomes, summary, file_path, created_at, updated_at
"""
from __future__ import annotations

from pathlib import Path

from autodev.flows.investigation_flow import InvestigationFlow
from autodev.schemas import CaseFile, InvestigationInput


class TestInvestigationFlowInitialization:
    def test_investigation_flow_initialization(self):
        flow = InvestigationFlow()
        assert flow is not None
        assert hasattr(flow, "agent"), "InvestigationFlow must expose .agent"


class TestInvestigationFlowHappyPath:
    def test_investigation_flow_happy_path_with_minimal_input(self, tmp_path):
        """Happy path: problem-description input produces a valid CaseFile artifact on disk."""
        flow = InvestigationFlow()
        inp = InvestigationInput(
            input_token="service crashes at startup with unexpected keyword argument",
            repo_path=str(tmp_path),
        )
        result = flow.run(inp)

        assert isinstance(result, CaseFile), "run() must return a CaseFile"
        assert result.case_id, "CaseFile must have a case_id"
        assert result.slug, "CaseFile must have a slug"
        assert result.file_path is not None, "CaseFile.file_path must be set after run()"
        assert Path(result.file_path).exists(), "Markdown case file must be written to disk"

        content = Path(result.file_path).read_text(encoding="utf-8")
        assert "# Case File" in content, "Markdown must begin with '# Case File'"


class TestInvestigationFlowStateDirCreated:
    def test_investigation_flow_state_dir_created_under_run(self, tmp_path):
        """Verify that .dev-factory/investigations/ is created under repo_path."""
        flow = InvestigationFlow()
        inp = InvestigationInput(
            input_token="PROJ-999",
            repo_path=str(tmp_path),
        )
        flow.run(inp)

        state_dir = tmp_path / ".dev-factory" / "investigations"
        assert state_dir.is_dir(), ".dev-factory/investigations/ must be created by InvestigationFlow.run()"


class TestInvestigationFlowMissingEvidence:
    def test_investigation_flow_missing_evidence_handled(self, tmp_path):
        """Empty repo with no greppable input should not crash; evidence list may be empty or contain placeholders."""
        flow = InvestigationFlow()
        # Use a plain prose token — no files in tmp_path to grep
        inp = InvestigationInput(
            input_token="something mysterious happens sometimes",
            repo_path=str(tmp_path),
        )
        result = flow.run(inp)  # must not raise

        assert isinstance(result, CaseFile)
        # Evidence may contain placeholder entries (not crash)
        assert isinstance(result.evidence, list)
        # Summary should be generated regardless
        assert result.summary, "summary must be populated even with no grep hits"
