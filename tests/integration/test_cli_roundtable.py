"""CLI tests for the `autodev roundtable` subcommand.

Runs offline (FACTORY_FORCE_MOCK=1 set by conftest).
"""
from __future__ import annotations

import json

from typer.testing import CliRunner

from autodev.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Test 1: normal invocation — stdout non-empty, JSON file written
# ---------------------------------------------------------------------------

def test_roundtable_cli_writes_json_and_prints_synthesis(tmp_path):
    """roundtable --topic ... --skills ... prints synthesis and creates JSON file."""
    result = runner.invoke(app, [
        "roundtable",
        "--topic", "Should we use gRPC or REST for internal microservices?",
        "--skills", "architecture,security",
        "--repo-path", str(tmp_path),
    ])

    assert result.exit_code == 0, f"CLI exited with {result.exit_code}: {result.output}"

    # stdout must be non-empty (synthesis text + file path line)
    assert result.output.strip(), "Expected non-empty stdout"

    # JSON file must be created under .dev-factory/roundtables/
    roundtables_dir = tmp_path / ".dev-factory" / "roundtables"
    assert roundtables_dir.exists(), f"Expected {roundtables_dir} to exist"

    json_files = list(roundtables_dir.glob("*.json"))
    assert len(json_files) == 1, f"Expected exactly 1 JSON file, got {json_files}"

    # JSON must be valid and contain conversation + synthesis keys
    data = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert "conversation" in data
    assert "synthesis" in data

    conv = data["conversation"]
    assert "conversation_id" in conv
    assert "participating_cards" in conv

    synth = data["synthesis"]
    assert "parts" in synth


# ---------------------------------------------------------------------------
# Test 2: unknown / nonsensical skill — succeeds with best-effort (no crash)
# ---------------------------------------------------------------------------

def test_roundtable_cli_nonsensical_skill_falls_back(tmp_path):
    """--skills with no roster match still succeeds (best-effort participant selection)."""
    result = runner.invoke(app, [
        "roundtable",
        "--topic", "Review the quantum entanglement subsystem.",
        "--skills", "nonsensical-skill-xyz",
        "--repo-path", str(tmp_path),
    ])

    # Must NOT raise an unhandled exception
    assert result.exit_code == 0, (
        f"CLI raised with exit_code={result.exit_code}:\n{result.output}"
    )

    # Output must be non-empty (either synthesis or fallback message)
    assert result.output.strip(), "Expected non-empty output even with unknown skill"

    # JSON file is still written (even if conversation has 0 participants)
    roundtables_dir = tmp_path / ".dev-factory" / "roundtables"
    json_files = list(roundtables_dir.glob("*.json"))
    assert len(json_files) == 1, f"Expected 1 JSON file, found {json_files}"

    data = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert "conversation" in data
    assert "synthesis" in data


# ---------------------------------------------------------------------------
# Test 3: --help shows roundtable command
# ---------------------------------------------------------------------------

def test_roundtable_appears_in_help():
    """autodev --help lists the roundtable subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "roundtable" in result.stdout
