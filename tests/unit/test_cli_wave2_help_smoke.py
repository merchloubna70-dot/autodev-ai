"""Smoke tests for wave-2 CLI commands' --help.

Brings cli.py coverage back above 85% by exercising the typer registration
paths for deliver-multi, reverse-doc, and the new flags added to existing
commands.  These do NOT execute the underlying flows — they only verify
the command surface is registered and --help renders.
"""
from __future__ import annotations

from typer.testing import CliRunner

from autodev.cli import app


def test_deliver_multi_help_renders() -> None:
    result = CliRunner().invoke(app, ["deliver-multi", "--help"])
    assert result.exit_code == 0
    assert "--config" in result.stdout
    assert "multi" in result.stdout.lower()


def test_reverse_doc_help_renders() -> None:
    result = CliRunner().invoke(app, ["reverse-doc", "--help"])
    assert result.exit_code == 0
    assert "--watch" in result.stdout
    assert "--debounce" in result.stdout


def test_doctor_help_renders() -> None:
    result = CliRunner().invoke(app, ["doctor", "--help"])
    assert result.exit_code == 0


def test_ci_run_help_renders() -> None:
    result = CliRunner().invoke(app, ["ci-run", "--help"])
    assert result.exit_code == 0


def test_deliver_project_help_shows_new_flags() -> None:
    result = CliRunner().invoke(app, ["deliver-project", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "--skill-pack" in out
    assert "--dry-cost" in out
    assert "--judges" in out
    assert "--resume-from" in out


def test_dashboard_help_shows_export_html() -> None:
    result = CliRunner().invoke(app, ["dashboard", "--help"])
    assert result.exit_code == 0
    assert "--export-html" in result.stdout


def test_deliver_multi_missing_config_exits_nonzero() -> None:
    """--config is required; missing it must exit non-zero."""
    result = CliRunner().invoke(app, ["deliver-multi"])
    assert result.exit_code != 0


def test_deliver_multi_invalid_scale_rejected(tmp_path) -> None:
    """Invalid --scale should trigger the validation branch and exit 1."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("group_name: t\nrepos: []\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["deliver-multi", "--config", str(cfg), "--scale", "nonsense"])
    assert result.exit_code == 1


def test_deliver_project_invalid_skill_pack_rejected() -> None:
    """--skill-pack with unknown name must exit 1 before doing anything."""
    result = CliRunner().invoke(app, ["deliver-project", "--skill-pack", "no-such-pack"])
    assert result.exit_code == 1


def test_deliver_project_dry_cost_exits_zero_no_run(tmp_path) -> None:
    """--dry-cost must exit 0 with JSON output and NOT execute the pipeline."""
    brief = tmp_path / "brief.md"
    brief.write_text("Build a small CLI tool.", encoding="utf-8")
    result = CliRunner().invoke(
        app,
        ["deliver-project", "--dry-cost", "--project-brief", str(brief)],
    )
    assert result.exit_code == 0
    assert "{" in result.stdout  # JSON output
    assert "tokens" in result.stdout.lower() or "cost" in result.stdout.lower()


def test_deliver_project_resume_from_unknown_stage_rejected() -> None:
    """--resume-from with invalid stage must exit 1."""
    result = CliRunner().invoke(
        app, ["deliver-project", "--resume-from", "not-a-stage", "--run-id", "fake"]
    )
    assert result.exit_code == 1


def test_deliver_multi_runs_minimal_mock_pipeline(tmp_path, monkeypatch) -> None:
    """Exercise deliver-multi body with a real YAML + mocked MultiRepoFlow.run."""
    from unittest.mock import MagicMock, patch

    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        "group_name: test-group\nrepos:\n  - path: ./r1\n    brief_file: ./b.md\n",
        encoding="utf-8",
    )
    (tmp_path / "r1").mkdir()
    (tmp_path / "b.md").write_text("test brief", encoding="utf-8")

    mock_summary = MagicMock(
        group_id="g1",
        total=1,
        succeeded=1,
        failed=0,
        artifact_root=str(tmp_path / "out"),
    )
    with patch("autodev.flows.multi_repo_flow.MultiRepoFlow.run", return_value=mock_summary):
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            app, ["deliver-multi", "--config", str(cfg), "--scale", "small"]
        )
    assert result.exit_code == 0
    assert "group_id=g1" in result.stdout


def test_deliver_multi_missing_config_file_exits_2(tmp_path) -> None:
    """Missing config file → exit 2 cleanly."""
    result = CliRunner().invoke(
        app, ["deliver-multi", "--config", str(tmp_path / "does-not-exist.yaml")]
    )
    assert result.exit_code == 2
