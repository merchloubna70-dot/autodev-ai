"""Integration tests for the `design-ux` CLI command."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from autodev.cli import app


runner = CliRunner()


def test_design_ux_basic(tmp_path):
    """design-ux with --project-name and --repo-path produces ux_design.md."""
    result = runner.invoke(
        app,
        [
            "design-ux",
            "--project-name", "CLITestProduct",
            "--repo-path", str(tmp_path),
        ],
    )
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
    assert "CLITestProduct" in result.output
    assert "Sally completed" in result.output
    out_file = tmp_path / "product" / "ux_design.md"
    assert out_file.exists(), "product/ux_design.md not written"


def test_design_ux_with_languages(tmp_path):
    """design-ux accepts comma-separated --languages without crashing."""
    result = runner.invoke(
        app,
        [
            "design-ux",
            "--project-name", "MultiLangApp",
            "--languages", "python,typescript",
            "--repo-path", str(tmp_path),
        ],
    )
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
    assert "MultiLangApp" in result.output
    out_file = tmp_path / "product" / "ux_design.md"
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "MultiLangApp" in content


def test_design_ux_default_repo_path(tmp_path, monkeypatch):
    """design-ux without --repo-path defaults to '.' (current dir)."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "design-ux",
            "--project-name", "DefaultPath",
        ],
    )
    assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
    out_file = tmp_path / "product" / "ux_design.md"
    assert out_file.exists()
