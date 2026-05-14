"""R9-B3 coverage backfill for src/autodev/mcp_server/tools.py.

Targets uncovered lines (79% → ≥85%):
  - Lines 60-62:  _write_audit_log OSError branch
  - Lines 186-196: _handle_create_prd full body
  - Lines 253-254: _handle_deliver_project invalid-language → Language.UNKNOWN
  - Lines 381-382: _handle_run_issue invalid-language → Language.UNKNOWN
  - Lines 476-482: _handle_report success path (after path safety)
  - Lines 560-565: _handle_release_check success path (after path safety)
  - Lines 596-610: _handle_list_runs non-empty directory cases
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from autodev.mcp_server.tools import (
    _ENV_ALLOW_APPLY,
    _ENV_AUDIT_LOG,
    _DEFAULT_AUDIT_LOG,
    _write_audit_log,
    _handle_create_prd,
    _handle_deliver_project,
    _handle_list_runs,
    _handle_release_check,
    _handle_report,
    _handle_run_issue,
)


# ---------------------------------------------------------------------------
# Helper: strip guardrail env vars so path-safety is the only denial path
# ---------------------------------------------------------------------------

def _clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items()
            if k not in (_ENV_ALLOW_APPLY, _ENV_AUDIT_LOG)}
    if extra:
        base.update(extra)
    return base


# ===========================================================================
# 1. _write_audit_log OSError branch (lines 60-62)
# ===========================================================================

class TestWriteAuditLogOSError:
    """When the audit log file cannot be opened, it logs to stderr but does NOT raise."""

    def test_oserror_on_open_does_not_raise(self, tmp_path: Path, capsys):
        """builtins.open raises OSError → warning on stderr, no exception propagated."""
        audit_file = str(tmp_path / "audit.log")

        # Force open() to raise OSError
        with mock.patch("builtins.open", side_effect=OSError("disk full")), \
             mock.patch.dict(os.environ, {_ENV_AUDIT_LOG: audit_file}):
            # Must not raise
            _write_audit_log("test_tool", {"param": "value"}, "/tmp/repo", "allowed")

        captured = capsys.readouterr()
        assert "WARNING: could not write audit log" in captured.err

    def test_oserror_on_write_does_not_raise(self, tmp_path: Path, capsys):
        """If the file handle's write() raises OSError the function still does not raise.

        We patch open's context manager to return a mock file handle that raises
        on .write().
        """
        audit_file = str(tmp_path / "audit.log")
        mock_fh = mock.MagicMock()
        mock_fh.__enter__ = mock.Mock(return_value=mock_fh)
        mock_fh.__exit__ = mock.Mock(return_value=False)
        mock_fh.write.side_effect = OSError("no space left")

        with mock.patch("builtins.open", return_value=mock_fh), \
             mock.patch.dict(os.environ, {_ENV_AUDIT_LOG: audit_file}):
            _write_audit_log("test_tool", {}, "/tmp/repo", "denied", "reason text")

        captured = capsys.readouterr()
        assert "WARNING: could not write audit log" in captured.err


# ===========================================================================
# 2. _handle_create_prd (lines 186-196)
# ===========================================================================

class TestHandleCreatePrd:
    """_handle_create_prd calls ProductManagerAgent → RequirementAnalystAgent → PRDWriterAgent."""

    def test_create_prd_returns_markdown_string(self):
        """Happy path: all three agents mocked, returns a non-empty string."""
        mock_brief = mock.MagicMock()
        mock_fr = [mock.MagicMock()]
        mock_nf = [mock.MagicMock()]
        mock_ac = [mock.MagicMock()]
        mock_prd = mock.MagicMock()
        mock_markdown = "# PRD\n\nSome content"

        with mock.patch("autodev.agents.product_manager.ProductManagerAgent.build_brief",
                        return_value=mock_brief) as _pm, \
             mock.patch("autodev.agents.requirement_analyst.RequirementAnalystAgent.derive",
                        return_value=(mock_fr, mock_nf, mock_ac)) as _ra, \
             mock.patch("autodev.agents.prd_writer.PRDWriterAgent.write",
                        return_value=mock_prd) as _pw, \
             mock.patch("autodev.agents.prd_writer.PRDWriterAgent.render_markdown",
                        return_value=mock_markdown) as _rm:
            result = _handle_create_prd({"brief_text": "Build an API for invoice management"})

        assert isinstance(result, str)
        assert "PRD" in result

    def test_create_prd_passes_brief_text_to_pm(self):
        """brief_text is forwarded to ProductManagerAgent.build_brief."""
        brief_text = "Automated invoice processing"
        mock_brief = mock.MagicMock()

        with mock.patch("autodev.agents.product_manager.ProductManagerAgent.build_brief",
                        return_value=mock_brief) as pm_mock, \
             mock.patch("autodev.agents.requirement_analyst.RequirementAnalystAgent.derive",
                        return_value=([], [], [])), \
             mock.patch("autodev.agents.prd_writer.PRDWriterAgent.write",
                        return_value=mock.MagicMock()), \
             mock.patch("autodev.agents.prd_writer.PRDWriterAgent.render_markdown",
                        return_value="# PRD"):
            _handle_create_prd({"brief_text": brief_text})

        pm_mock.assert_called_once_with(brief_text)

    def test_create_prd_empty_brief_text(self):
        """brief_text defaults to '' when absent; should still work."""
        mock_brief = mock.MagicMock()

        with mock.patch("autodev.agents.product_manager.ProductManagerAgent.build_brief",
                        return_value=mock_brief), \
             mock.patch("autodev.agents.requirement_analyst.RequirementAnalystAgent.derive",
                        return_value=([], [], [])), \
             mock.patch("autodev.agents.prd_writer.PRDWriterAgent.write",
                        return_value=mock.MagicMock()), \
             mock.patch("autodev.agents.prd_writer.PRDWriterAgent.render_markdown",
                        return_value=""):
            result = _handle_create_prd({})  # no brief_text key

        # Should still return a string (even if empty)
        assert isinstance(result, str)


# ===========================================================================
# 3. _handle_deliver_project invalid language → Language.UNKNOWN (lines 253-254)
# ===========================================================================

class TestHandleDeliverProjectInvalidLanguage:
    """Unsupported language strings must be coerced to Language.UNKNOWN."""

    def test_invalid_language_falls_back_to_unknown(self, tmp_path: Path):
        """Languages=['cobol', 'fortran-77'] are invalid → Language.UNKNOWN used."""
        args = {
            "repo_path": str(tmp_path),
            "brief_text": "Build something",
            "languages": ["cobol", "fortran-77"],
        }
        mock_run = mock.MagicMock()
        mock_run.run_id = "test-invalid-lang-001"
        mock_run.state.release_check = None

        with mock.patch(
            "autodev.flows.project_delivery_flow.ProjectDeliveryFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(os.environ, _clean_env(), clear=True):
            result = _handle_deliver_project(args)

        # Should succeed (no isError) — unknowns are coerced
        assert result.get("isError") is not True, f"Unexpected error: {result}"
        assert result["run_id"] == "test-invalid-lang-001"

    def test_single_invalid_language_as_string_falls_back(self, tmp_path: Path):
        """A single non-list language string that isn't valid → Language.UNKNOWN."""
        args = {
            "repo_path": str(tmp_path),
            "brief_text": "Build something",
            "languages": "brainfuck",   # not a list, not a valid Language
        }
        mock_run = mock.MagicMock()
        mock_run.run_id = "test-invalid-lang-str"
        mock_run.state.release_check = None

        with mock.patch(
            "autodev.flows.project_delivery_flow.ProjectDeliveryFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(os.environ, _clean_env(), clear=True):
            result = _handle_deliver_project(args)

        assert result.get("isError") is not True


# ===========================================================================
# 4. _handle_run_issue invalid language → Language.UNKNOWN (lines 381-382)
# ===========================================================================

class TestHandleRunIssueInvalidLanguage:
    """Unsupported language strings must be coerced to Language.UNKNOWN."""

    def test_invalid_language_falls_back_to_unknown(self, tmp_path: Path):
        args = {
            "repo_path": str(tmp_path),
            "issue_text": "Bug: NPE on startup",
            "languages": ["cobol", "prolog"],
        }
        mock_run = mock.MagicMock()
        mock_run.run_id = "issue-invalid-lang-001"
        mock_run.state.mock_execution_used = True

        with mock.patch(
            "autodev.flows.issue_pipeline_flow.IssuePipelineFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(os.environ, _clean_env(), clear=True):
            result = _handle_run_issue(args)

        assert result.get("isError") is not True
        assert result["run_id"] == "issue-invalid-lang-001"

    def test_non_list_invalid_language_coerced(self, tmp_path: Path):
        """Non-list invalid language string goes through UNKNOWN coercion."""
        args = {
            "repo_path": str(tmp_path),
            "issue_text": "Crash on startup",
            "languages": "intercal",
        }
        mock_run = mock.MagicMock()
        mock_run.run_id = "issue-invalid-lang-str"
        mock_run.state.mock_execution_used = False

        with mock.patch(
            "autodev.flows.issue_pipeline_flow.IssuePipelineFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(os.environ, _clean_env(), clear=True):
            result = _handle_run_issue(args)

        assert result.get("isError") is not True


# ===========================================================================
# 5. _handle_report success path (lines 476-482)
# ===========================================================================

class TestHandleReport:
    """_handle_report: success path loads RunState and writes a report."""

    def test_report_returns_text_when_file_exists(self, tmp_path: Path):
        """When final_report.md exists, returns its contents as a string."""
        # Build a minimal fake RunState so Reporter().write_final_report can run
        mock_run = mock.MagicMock()
        report_file = tmp_path / "delivery" / "final_report.md"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text("# Final Report\n\nAll good.", encoding="utf-8")
        mock_run.path.return_value = report_file

        args = {"repo_path": str(tmp_path), "run_id": "run-report-001"}

        with mock.patch("autodev.state.RunState.load", return_value=mock_run), \
             mock.patch("autodev.reports.reporter.Reporter.write_final_report"):
            result = _handle_report(args)

        assert isinstance(result, str)
        assert "Final Report" in result

    def test_report_returns_fallback_when_file_missing(self, tmp_path: Path):
        """When final_report.md does not exist, returns a fallback string."""
        nonexistent = tmp_path / "delivery" / "final_report.md"
        mock_run = mock.MagicMock()
        mock_run.path.return_value = nonexistent  # does not exist

        args = {"repo_path": str(tmp_path), "run_id": "run-report-missing"}

        with mock.patch("autodev.state.RunState.load", return_value=mock_run), \
             mock.patch("autodev.reports.reporter.Reporter.write_final_report"):
            result = _handle_report(args)

        # Fallback branch: "report written to <path>"
        assert isinstance(result, str)
        assert "report written to" in result or "final_report" in result

    def test_report_rejects_dangerous_repo_path(self):
        """_handle_report rejects /../ traversal paths."""
        args = {"repo_path": "../etc/passwd", "run_id": "some-run"}
        result = _handle_report(args)
        assert isinstance(result, dict)
        assert result.get("isError") is True


# ===========================================================================
# 6. _handle_release_check success path (lines 560-565)
# ===========================================================================

class TestHandleReleaseCheck:
    """_handle_release_check: success path runs ReleaseFlow.check and returns JSON."""

    def test_release_check_returns_dict(self, tmp_path: Path):
        """Happy path: returns a dict with release check fields."""
        mock_run = mock.MagicMock()
        mock_rc = mock.MagicMock()
        mock_rc.model_dump_json.return_value = json.dumps({
            "decision": "release-ready",
            "reasons": [],
            "score": 100,
        })

        args = {"repo_path": str(tmp_path), "run_id": "run-rc-001"}

        with mock.patch("autodev.state.RunState.load", return_value=mock_run), \
             mock.patch("autodev.flows.release_flow.ReleaseFlow.check", return_value=mock_rc):
            result = _handle_release_check(args)

        assert isinstance(result, dict)
        assert result.get("decision") == "release-ready"

    def test_release_check_rejects_dangerous_repo_path(self):
        """_handle_release_check rejects path traversal."""
        args = {"repo_path": "../etc/shadow", "run_id": "run-001"}
        result = _handle_release_check(args)
        assert result.get("isError") is True


# ===========================================================================
# 7. _handle_list_runs non-empty directory (lines 596-610)
# ===========================================================================

class TestHandleListRunsNonEmpty:
    """_handle_list_runs: tests for the non-empty-directory branches."""

    def test_list_runs_returns_runs_with_state(self, tmp_path: Path):
        """Returns a list of dicts with run_id, mode, flow when run_state.json exists."""
        runs_root = tmp_path / ".dev-factory" / "runs"
        run_dir = runs_root / "20240101T000000Z-abc123"
        run_dir.mkdir(parents=True)
        state_data = {"mode": "dry-run", "flow": "project_delivery"}
        (run_dir / "run_state.json").write_text(json.dumps(state_data), encoding="utf-8")

        args = {"repo_path": str(tmp_path)}
        result = _handle_list_runs(args)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["run_id"] == "20240101T000000Z-abc123"
        assert result[0]["mode"] == "dry-run"
        assert result[0]["flow"] == "project_delivery"

    def test_list_runs_handles_missing_state_json(self, tmp_path: Path):
        """When run_state.json is absent, run_id is still returned with no mode/flow."""
        runs_root = tmp_path / ".dev-factory" / "runs"
        run_dir = runs_root / "20240102T000000Z-xyz789"
        run_dir.mkdir(parents=True)
        # No run_state.json created

        args = {"repo_path": str(tmp_path)}
        result = _handle_list_runs(args)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["run_id"] == "20240102T000000Z-xyz789"
        # mode and flow should not be present (no state file)
        assert "mode" not in result[0]
        assert "flow" not in result[0]

    def test_list_runs_handles_corrupt_state_json(self, tmp_path: Path):
        """Corrupt run_state.json is silently skipped; run_id is still returned."""
        runs_root = tmp_path / ".dev-factory" / "runs"
        run_dir = runs_root / "20240103T000000Z-corrupt"
        run_dir.mkdir(parents=True)
        (run_dir / "run_state.json").write_text("NOT VALID JSON {{{{", encoding="utf-8")

        args = {"repo_path": str(tmp_path)}
        result = _handle_list_runs(args)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["run_id"] == "20240103T000000Z-corrupt"
        # No mode/flow keys when JSON parse fails
        assert "mode" not in result[0]

    def test_list_runs_skips_non_directory_entries(self, tmp_path: Path):
        """Files in the runs directory (not dirs) are skipped."""
        runs_root = tmp_path / ".dev-factory" / "runs"
        runs_root.mkdir(parents=True)
        # Create a file (not a dir) with a run-like name
        (runs_root / "not_a_dir.json").write_text("{}", encoding="utf-8")
        # Create a valid run dir
        run_dir = runs_root / "20240104T000000Z-validrun"
        run_dir.mkdir()
        (run_dir / "run_state.json").write_text(
            json.dumps({"mode": "apply", "flow": "issue_pipeline"}), encoding="utf-8"
        )

        args = {"repo_path": str(tmp_path)}
        result = _handle_list_runs(args)

        assert isinstance(result, list)
        # Only the directory entry should be included
        assert len(result) == 1
        assert result[0]["run_id"] == "20240104T000000Z-validrun"

    def test_list_runs_returns_at_most_20(self, tmp_path: Path):
        """_handle_list_runs caps results at 20 entries."""
        runs_root = tmp_path / ".dev-factory" / "runs"
        # Create 25 run directories
        for i in range(25):
            run_dir = runs_root / f"20240101T{i:06d}Z-run{i:03d}"
            run_dir.mkdir(parents=True)

        args = {"repo_path": str(tmp_path)}
        result = _handle_list_runs(args)

        assert isinstance(result, list)
        assert len(result) <= 20

    def test_list_runs_rejects_dangerous_path(self):
        """_handle_list_runs rejects path traversal."""
        args = {"repo_path": "../etc/passwd"}
        result = _handle_list_runs(args)
        assert isinstance(result, dict)
        assert result.get("isError") is True


# ===========================================================================
# 8. Additional apply-mode guardrail + audit-log OS error combinations
# ===========================================================================

class TestAuditLogOSErrorInApplyMode:
    """Audit log write failure must not abort the apply-mode check result."""

    def test_check_apply_allowed_survives_audit_oserror(self, tmp_path: Path):
        """Even if audit log write fails, _check_apply_mode_allowed returns the right result."""
        from autodev.mcp_server.tools import _check_apply_mode_allowed

        args = {"allow_apply": True}

        with mock.patch("builtins.open", side_effect=OSError("no space")), \
             mock.patch.dict(os.environ, _clean_env({_ENV_ALLOW_APPLY: "1"}), clear=True):
            denial = _check_apply_mode_allowed("some_tool", args, "/tmp/repo")

        # Should return None (allowed) even though audit log write failed
        assert denial is None

    def test_check_apply_denied_survives_audit_oserror(self, tmp_path: Path):
        """Denied apply with audit log failure still returns the denial dict."""
        from autodev.mcp_server.tools import _check_apply_mode_allowed

        args = {}  # allow_apply missing

        with mock.patch("builtins.open", side_effect=OSError("disk full")), \
             mock.patch.dict(os.environ, _clean_env({_ENV_ALLOW_APPLY: "1"}), clear=True):
            denial = _check_apply_mode_allowed("some_tool", args, "/tmp/repo")

        assert denial is not None
        assert denial.get("isError") is True
