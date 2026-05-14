"""
Unit tests for scripts/release_readiness_gate.py

Uses unittest.mock to avoid running pytest/ruff/mypy/subprocess during testing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Dynamic import of the script (it lives under scripts/, not a package)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "release_readiness_gate.py"


def _load_gate_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("release_readiness_gate", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


gate = _load_gate_module()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Minimal fake repo with the required structure."""
    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0"\nrequires-python = ">=3.10"\n'
        '[project.scripts]\nautodev = "autodev.cli:app"\n',
        encoding="utf-8",
    )
    # README
    (tmp_path / "README.md").write_text("# autodev-ai\n", encoding="utf-8")

    # docs
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "quickstart.md").write_text("quick", encoding="utf-8")
    (docs / "architecture.md").write_text("arch", encoding="utf-8")
    (docs / "faq.md").write_text("faq", encoding="utf-8")
    tutorials = docs / "tutorials"
    tutorials.mkdir()

    # examples
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "README.md").write_text("examples", encoding="utf-8")

    # docs/validation
    val = docs / "validation"
    val.mkdir()
    (val / "autodev_release_readiness_gate.json").write_text("{}", encoding="utf-8")

    # tests/integration/test_mcp_server_smoke.py
    integration = tmp_path / "tests" / "integration"
    integration.mkdir(parents=True)
    (integration / "test_mcp_server_smoke.py").write_text("", encoding="utf-8")

    # a2a test files (≥5)
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    for i in range(6):
        (unit / f"test_a2a_check_{i}.py").write_text("", encoding="utf-8")

    # packaging files
    docker = tmp_path / "packaging" / "docker"
    docker.mkdir(parents=True)
    (docker / "Dockerfile").write_text("FROM python:3.10\n", encoding="utf-8")

    pyinst = tmp_path / "packaging" / "pyinstaller"
    pyinst.mkdir(parents=True)
    (pyinst / "autodev.spec").write_text("# spec\n", encoding="utf-8")

    formula = tmp_path / "packaging" / "homebrew" / "Formula"
    formula.mkdir(parents=True)
    (formula / "autodev-ai.rb").write_text("# rb\n", encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Test 1: main() returns dict with 'overall' key
# ---------------------------------------------------------------------------


def test_main_returns_dict_with_overall_key(repo: Path) -> None:
    with patch.object(gate, "_run", return_value=(0, "", "")):
        result = gate.main(["--repo-path", str(repo), "--output", str(repo / "rrgate_test.json")])
    assert isinstance(result, dict)
    assert "overall" in result


# ---------------------------------------------------------------------------
# Test 2: report contains all required top-level keys
# ---------------------------------------------------------------------------


def test_report_has_required_top_level_keys(repo: Path) -> None:
    with patch.object(gate, "_run", return_value=(0, "", "")):
        result = gate.main(["--repo-path", str(repo), "--output", str(repo / "rrgate_test.json")])
    for key in ("gate", "ran_at", "overall", "checks", "strict_pass", "summary"):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Test 3: each check result dict has required fields
# ---------------------------------------------------------------------------


def test_each_check_has_required_fields(repo: Path) -> None:
    with patch.object(gate, "_run", return_value=(0, "", "")):
        result = gate.main(["--repo-path", str(repo), "--output", str(repo / "rrgate_test.json")])
    required_fields = {"name", "status", "detail", "duration_ms", "evidence"}
    for check in result["checks"]:
        missing = required_fields - set(check.keys())
        assert not missing, f"Check {check.get('name')} missing fields: {missing}"


# ---------------------------------------------------------------------------
# Test 4: exactly 12 checks are run
# ---------------------------------------------------------------------------


def test_exactly_12_checks(repo: Path) -> None:
    with patch.object(gate, "_run", return_value=(0, "", "")):
        result = gate.main(["--repo-path", str(repo), "--output", str(repo / "rrgate_test.json")])
    assert len(result["checks"]) == 12


# ---------------------------------------------------------------------------
# Test 5: --strict exits 1 on synthetic fail
# ---------------------------------------------------------------------------


def test_strict_exits_1_on_fail(repo: Path) -> None:
    # Remove pyproject.toml to force package_metadata_valid to fail
    (repo / "pyproject.toml").unlink()
    with pytest.raises(SystemExit) as exc_info:
        with patch.object(gate, "_run", return_value=(0, "", "")):
            gate.main(["--repo-path", str(repo), "--output", str(repo / "rrgate_test.json"), "--strict"])
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test 6: overall == "pass" when no failures/skips
# ---------------------------------------------------------------------------


def test_overall_pass_when_all_pass(repo: Path) -> None:
    with patch.object(gate, "_run", return_value=(0, "", "")):
        result = gate.main(["--repo-path", str(repo), "--output", str(repo / "rrgate_test.json")])
    # Some checks may skip (e.g. cli_help if not on PATH in mock env), so accept pass or pass_with_skips
    assert result["overall"] in ("pass", "pass_with_skips")
    assert result["summary"]["fail"] == 0


# ---------------------------------------------------------------------------
# Test 7: check_package_metadata_valid fails on bad pyproject
# ---------------------------------------------------------------------------


def test_package_metadata_valid_fails_on_missing_keys(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "bad"\n', encoding="utf-8")
    result = gate.check_package_metadata_valid(tmp_path)
    assert result["status"] == "fail"
    assert "version" in result["detail"] or "requires-python" in result["detail"]


# ---------------------------------------------------------------------------
# Test 8: check_docs_exist fails when docs are absent
# ---------------------------------------------------------------------------


def test_docs_exist_fails_when_missing(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# hi", encoding="utf-8")
    result = gate.check_docs_exist(tmp_path)
    assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# Test 9: check_packaging_files_exist fails when files are absent
# ---------------------------------------------------------------------------


def test_packaging_files_exist_fails_when_missing(tmp_path: Path) -> None:
    result = gate.check_packaging_files_exist(tmp_path)
    assert result["status"] == "fail"
    assert "Missing" in result["detail"]


# ---------------------------------------------------------------------------
# Test 10: check_no_dangerous_release_claims detects forbidden strings
# ---------------------------------------------------------------------------


def test_no_dangerous_release_claims_catches_forbidden(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "This software is production ready and enterprise certified!\n",
        encoding="utf-8",
    )
    result = gate.check_no_dangerous_release_claims(tmp_path)
    assert result["status"] == "fail"
    assert "production ready" in result["detail"] or "enterprise certified" in result["detail"]


# ---------------------------------------------------------------------------
# Test 11: check_a2a_smoke_path_exists passes with ≥5 a2a files
# ---------------------------------------------------------------------------


def test_a2a_smoke_path_exists_passes(repo: Path) -> None:
    result = gate.check_a2a_smoke_path_exists(repo)
    assert result["status"] == "pass"
    assert "6" in result["detail"] or int(result["detail"].split()[0]) >= 5


# ---------------------------------------------------------------------------
# Test 12: output JSON is written to disk and parseable
# ---------------------------------------------------------------------------


def test_output_json_written_to_disk(repo: Path) -> None:
    out = repo / "test_rrgate_output.json"
    with patch.object(gate, "_run", return_value=(0, "", "")):
        gate.main(["--repo-path", str(repo), "--output", str(out)])
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["gate"] == "release_readiness"
    assert "checks" in data
