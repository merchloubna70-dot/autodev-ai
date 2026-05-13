"""Integration tests for 'autodev investigate' CLI command (BMAD-10)."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from autodev.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Test 1: ticket-id-like input — end-to-end
# ---------------------------------------------------------------------------

def test_investigate_ticket_id(tmp_path):
    """CLI 'investigate' with a ticket-id input should succeed and emit case_id."""
    result = runner.invoke(app, [
        "investigate",
        "--input", "PROJ-101",
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.stdout}"
    assert "case_id=" in result.stdout
    assert "slug=" in result.stdout
    assert "mode=" in result.stdout
    # Should write a case file
    inv_dir = tmp_path / ".dev-factory" / "investigations"
    md_files = list(inv_dir.glob("*.md"))
    assert len(md_files) >= 1, "Expected at least one .md case file"


# ---------------------------------------------------------------------------
# Test 2: error-message input — end-to-end
# ---------------------------------------------------------------------------

def test_investigate_error_msg(tmp_path):
    """CLI 'investigate' with an error message should classify as error-msg."""
    result = runner.invoke(app, [
        "investigate",
        "--input", "TypeError: unsupported operand type(s) for +",
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.stdout}"
    assert "mode=defect-chasing" in result.stdout


# ---------------------------------------------------------------------------
# Test 3: log-path input — end-to-end
# ---------------------------------------------------------------------------

def test_investigate_log_path(tmp_path):
    """CLI 'investigate' with a real log file path should work end-to-end."""
    log = tmp_path / "server.log"
    log.write_text(
        "2026-01-01 10:00:00 INFO starting\n"
        "2026-01-01 10:01:00 ERROR connection refused\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, [
        "investigate",
        "--input", str(log),
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.stdout}"
    assert "case_id=" in result.stdout
    assert "mode=defect-chasing" in result.stdout
    assert "file=" in result.stdout
    # Case file should reference the log path
    inv_dir = tmp_path / ".dev-factory" / "investigations"
    md_files = list(inv_dir.glob("*.md"))
    assert len(md_files) >= 1
    content = md_files[0].read_text(encoding="utf-8")
    assert "## Evidence" in content


# ---------------------------------------------------------------------------
# Test 4: code-area input — produces area-exploration mode
# ---------------------------------------------------------------------------

def test_investigate_code_area(tmp_path):
    """CLI 'investigate' with a code area glob should produce area-exploration mode."""
    result = runner.invoke(app, [
        "investigate",
        "--input", "src/autodev/agents/*.py",
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.stdout}"
    assert "mode=area-exploration" in result.stdout


# ---------------------------------------------------------------------------
# Test 5: problem description prose — area-exploration
# ---------------------------------------------------------------------------

def test_investigate_prose_description(tmp_path):
    """CLI 'investigate' with prose should produce area-exploration mode."""
    result = runner.invoke(app, [
        "investigate",
        "--input", "The payment gateway module appears to silently drop requests under high load.",
        "--repo-path", str(tmp_path),
    ])
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.stdout}"
    assert "mode=area-exploration" in result.stdout


# ---------------------------------------------------------------------------
# Test 6: case file content contains expected sections
# ---------------------------------------------------------------------------

def test_investigate_case_file_sections(tmp_path):
    """The written .md case file should contain all required markdown sections."""
    runner.invoke(app, [
        "investigate",
        "--input", "BUG-99",
        "--repo-path", str(tmp_path),
    ])
    inv_dir = tmp_path / ".dev-factory" / "investigations"
    md_files = list(inv_dir.glob("*.md"))
    assert md_files, "No case file written"
    content = md_files[0].read_text(encoding="utf-8")
    assert "## Evidence" in content
    assert "## Hypotheses" in content
    assert "## Recommended Next Steps" in content
