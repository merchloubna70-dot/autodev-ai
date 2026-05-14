"""Integration tests for the `generate-context` CLI command (BMAD-11)."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from autodev.cli import app

runner = CliRunner()


def _make_fixture_repo(tmp_path: Path) -> Path:
    """Create a minimal Python fixture repo."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 88\n[tool.pytest.ini_options]\n",
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text("# lockfile\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Agent rules\nDo not skip tests.\n", encoding="utf-8")
    (tmp_path / ".commitlintrc").write_text("{}\n", encoding="utf-8")
    return tmp_path


def test_generate_context_creates_files(tmp_path: Path) -> None:
    """CLI end-to-end: generate-context writes project-context.md and .json."""
    repo = _make_fixture_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "generate-context",
            "--repo-path", str(repo),
            "--product-name", "FixtureApp",
        ],
    )
    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"
    assert "FixtureApp" in result.output
    assert "rules=" in result.output

    md_path = repo / "_autodev" / "project-context.md"
    json_path = repo / "_autodev" / "project-context.json"
    assert md_path.exists(), "project-context.md not written"
    assert json_path.exists(), "project-context.json not written"

    content = md_path.read_text(encoding="utf-8")
    assert "FixtureApp" in content
    assert "CTX-" in content  # at least one rule


def test_generate_context_with_brief(tmp_path: Path) -> None:
    """generate-context accepts --project-brief and incorporates its rules."""
    repo = _make_fixture_repo(tmp_path)
    brief_file = tmp_path / "brief.md"
    brief_file.write_text(
        "All functions must have type annotations. No mocking in production.\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "generate-context",
            "--repo-path", str(repo),
            "--project-brief", str(brief_file),
            "--product-name", "BriefApp",
        ],
    )
    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"

    json_path = repo / "_autodev" / "project-context.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["product_name"] == "BriefApp"
    # Brief mentions type annotations → expect a lang-idiom rule
    lang_rules = [r for r in data["rules"] if r["category"] == "lang-idiom"]
    assert any("type" in r["statement"].lower() for r in lang_rules), (
        f"Expected type-annotation rule in lang-idiom; got rules: {[r['statement'] for r in lang_rules]}"
    )


def test_generate_context_idempotent(tmp_path: Path) -> None:
    """Running generate-context twice does not duplicate rules in the JSON."""
    repo = _make_fixture_repo(tmp_path)

    runner.invoke(app, ["generate-context", "--repo-path", str(repo)])
    result2 = runner.invoke(app, ["generate-context", "--repo-path", str(repo)])

    assert result2.exit_code == 0
    json_path = repo / "_autodev" / "project-context.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    rule_ids = [r["rule_id"] for r in data["rules"]]
    assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule_ids after second run"
