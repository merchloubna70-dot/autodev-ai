"""
Unit tests for scripts/release_readiness_gate.py

Uses unittest.mock to avoid running pytest/ruff/mypy/subprocess during testing.
"""

from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from unittest.mock import patch

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
    """Minimal fake repo with the required structure (base + R2 prerequisites)."""
    # pyproject.toml — version starts with 0.1.0, has license field
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0"\nrequires-python = ">=3.10"\n'
        'license = {text = "MIT"}\n'
        '[project.scripts]\nautodev = "autodev.cli:app"\n',
        encoding="utf-8",
    )
    # README
    (tmp_path / "README.md").write_text("# autodev-ai\n", encoding="utf-8")

    # LICENSE file with MIT content
    (tmp_path / "LICENSE").write_text(
        "MIT License\n\nCopyright (c) 2026 autodev-ai contributors\n"
        "\nPermission is hereby granted, free of charge...\n",
        encoding="utf-8",
    )

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
    (val / "autodev_release_hardening_round.json").write_text(
        '{"release_blockers": []}', encoding="utf-8"
    )

    # tests/integration/test_mcp_server_smoke.py
    integration = tmp_path / "tests" / "integration"
    integration.mkdir(parents=True)
    (integration / "test_mcp_server_smoke.py").write_text("", encoding="utf-8")

    # a2a test files (≥5)
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    for i in range(6):
        (unit / f"test_a2a_check_{i}.py").write_text("", encoding="utf-8")

    # R2: SSRF test file (≥10 test functions)
    ssrf_funcs = "\n".join(f"def test_ssrf_{i}(): pass" for i in range(12))
    (unit / "test_a2a_http_ssrf_hardening.py").write_text(ssrf_funcs + "\n", encoding="utf-8")

    # R2: milestone_flow test (≥4)
    milestone_funcs = "\n".join(f"def test_milestone_{i}(): pass" for i in range(5))
    (unit / "test_milestone_flow.py").write_text(milestone_funcs + "\n", encoding="utf-8")

    # R2: release_flow test (≥4)
    release_funcs = "\n".join(f"def test_release_{i}(): pass" for i in range(5))
    (unit / "test_release_flow.py").write_text(release_funcs + "\n", encoding="utf-8")

    # packaging files
    docker = tmp_path / "packaging" / "docker"
    docker.mkdir(parents=True)
    # R3-D: must be digest-pinned (@sha256:<64-hex>)
    (docker / "Dockerfile").write_text(
        "FROM python:3.12-slim@sha256:" + ("a" * 64) + "\n", encoding="utf-8"
    )

    pyinst = tmp_path / "packaging" / "pyinstaller"
    pyinst.mkdir(parents=True)
    (pyinst / "autodev.spec").write_text("# spec\n", encoding="utf-8")

    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    # R3-F: honestly blocked formula
    (formula_dir / "autodev-ai.rb").write_text(
        '# STATUS: BLOCKED for publish until PyPI 0.1.0a1 sha256 is real\n'
        'url "https://github.com/merchloubna70-dot/autodev-ai/releases/..."\n'
        'sha256 "TODO_PUBLISH_SHA256"\n',
        encoding="utf-8",
    )
    # R3-F: PUBLISH_CHECKLIST.md required
    (tmp_path / "packaging" / "homebrew" / "PUBLISH_CHECKLIST.md").write_text(
        "# Homebrew publish checklist\n\n1. Confirm PyPI live\n", encoding="utf-8"
    )

    # R2: A2A SSRF transport + R3-E DNS rebinding pin symbols
    transport_dir = tmp_path / "src" / "autodev" / "adapters" / "a2a" / "transports"
    transport_dir.mkdir(parents=True)
    (transport_dir / "http.py").write_text(
        "class A2AHttpSSRFError(ValueError): pass\n"
        "def _resolve_and_pin_host(host: str) -> str: ...\n"
        "class _PinnedHTTPHandler: pass\n"
        "class _PinnedHTTPSHandler: pass\n",
        encoding="utf-8",
    )

    # R3-B: MCP apply guardrail symbols
    mcp_dir = tmp_path / "src" / "autodev" / "mcp_server"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "tools.py").write_text(
        "AUTODEV_MCP_ALLOW_APPLY = 'AUTODEV_MCP_ALLOW_APPLY'\n"
        "def tool(allow_apply: bool = False): ...\n",
        encoding="utf-8",
    )

    # R3-H: WorkerIsolator path-escape exception
    isolator_dir = tmp_path / "src" / "autodev" / "executors"
    isolator_dir.mkdir(parents=True)
    (isolator_dir / "worker_isolator.py").write_text(
        "class WorkerIsolatorPathEscapeError(Exception): pass\n", encoding="utf-8"
    )

    # R3-G: CHANGELOG + configuration + troubleshooting docs
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.0a1] — 2026-05-14 (Pre-Release)\n\n- First public alpha\n",
        encoding="utf-8",
    )
    (docs / "configuration.md").write_text(
        "# Configuration\n\n" + ("This document covers FACTORY_FORCE_MOCK and FACTORY_LOG. " * 20),
        encoding="utf-8",
    )
    (docs / "troubleshooting.md").write_text(
        "# Troubleshooting\n\n" + ("Common issues and fixes for autodev-ai users. " * 20),
        encoding="utf-8",
    )

    # R2: macOS Info.plist
    plist_dir = tmp_path / "packaging" / "desktop" / "autodev-ai.app" / "Contents"
    plist_dir.mkdir(parents=True)
    (plist_dir / "Info.plist").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        "<plist version=\"1.0\"><dict>"
        "<key>CFBundleShortVersionString</key><string>0.1.0a1</string>"
        "</dict></plist>\n",
        encoding="utf-8",
    )

    # R2: GitHub Actions release.yml with pytest + needs:
    gh_dir = tmp_path / ".github" / "workflows"
    gh_dir.mkdir(parents=True)
    (gh_dir / "release.yml").write_text(
        "jobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n"
        "  publish:\n    needs: test\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    # R3-C: lint.yml must scan scripts/
    (gh_dir / "lint.yml").write_text(
        "jobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - run: ruff check src tests scripts\n      - run: mypy src/autodev\n",
        encoding="utf-8",
    )

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
# Test 4: exactly 24 checks are run by default
# ---------------------------------------------------------------------------


def test_exactly_36_checks(repo: Path) -> None:
    """R3 grew the gate from 24 → 36 checks (BASE 12 + R2 12 + R3 12)."""
    with patch.object(gate, "_run", return_value=(0, "", "")):
        result = gate.main(["--repo-path", str(repo), "--output", str(repo / "rrgate_test.json")])
    assert len(result["checks"]) == 36


def test_exactly_12_checks_include_r2_only(repo: Path) -> None:
    with patch.object(gate, "_run", return_value=(0, "", "")):
        result = gate.main(["--repo-path", str(repo), "--output", str(repo / "rrgate_test.json"), "--include-r2"])
    assert len(result["checks"]) == 12
    # All check names should start with r2_
    assert all(c["name"].startswith("r2_") for c in result["checks"])


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
    # _run is used by cli_help, ruff, mypy, and r2_version_consistency (which calls python -c to get __version__)
    # r2_version_consistency reads pyproject version "0.1.0" and expects _run to return same via module import
    with patch.object(gate, "_run", return_value=(0, "0.1.0\n", "")):
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


# ---------------------------------------------------------------------------
# R2 Tests (13–24)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Test 13: r2_version_consistency — fails when pyproject version ≠ "0.1.0..."
# ---------------------------------------------------------------------------


def test_r2_version_consistency_fails_on_wrong_version(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "1.2.3"\nrequires-python = ">=3.10"\n',
        encoding="utf-8",
    )
    with patch.object(gate, "_run", return_value=(0, "1.2.3", "")):
        result = gate.check_r2_version_consistency(tmp_path)
    assert result["status"] == "fail"
    assert "0.1.0" in result["detail"]


def test_r2_version_consistency_passes_when_consistent(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0a1"\nrequires-python = ">=3.10"\n',
        encoding="utf-8",
    )
    with patch.object(gate, "_run", return_value=(0, "0.1.0a1\n", "")):
        result = gate.check_r2_version_consistency(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 14: r2_license_file_present
# ---------------------------------------------------------------------------


def test_r2_license_file_present_fails_when_missing(tmp_path: Path) -> None:
    result = gate.check_r2_license_file_present(tmp_path)
    assert result["status"] == "fail"
    assert "LICENSE" in result["detail"]


def test_r2_license_file_present_passes_with_mit(tmp_path: Path) -> None:
    (tmp_path / "LICENSE").write_text(
        "MIT License\n\nPermission is hereby granted...\n", encoding="utf-8"
    )
    result = gate.check_r2_license_file_present(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 15: r2_license_metadata_match
# ---------------------------------------------------------------------------


def test_r2_license_metadata_match_fails_when_missing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0"\nrequires-python = ">=3.10"\n',
        encoding="utf-8",
    )
    result = gate.check_r2_license_metadata_match(tmp_path)
    assert result["status"] == "fail"
    assert "license" in result["detail"].lower()


def test_r2_license_metadata_match_passes_with_field(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0"\n'
        'requires-python = ">=3.10"\nlicense = {text = "MIT"}\n',
        encoding="utf-8",
    )
    result = gate.check_r2_license_metadata_match(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 16: r2_wheel_version_works
# ---------------------------------------------------------------------------


def test_r2_wheel_version_works_skips_when_no_dist(tmp_path: Path) -> None:
    result = gate.check_r2_wheel_version_works(tmp_path)
    assert result["status"] == "skip"
    assert "no built wheel" in result["detail"]


def test_r2_wheel_version_works_passes_when_matching(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "autodev_ai-0.1.0a1-py3-none-any.whl").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0a1"\nrequires-python = ">=3.10"\n',
        encoding="utf-8",
    )
    result = gate.check_r2_wheel_version_works(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 17: r2_a2a_http_ssrf_hardened
# ---------------------------------------------------------------------------


def test_r2_a2a_http_ssrf_hardened_fails_when_no_error_class(tmp_path: Path) -> None:
    transport_dir = tmp_path / "src" / "autodev" / "adapters" / "a2a" / "transports"
    transport_dir.mkdir(parents=True)
    (transport_dir / "http.py").write_text("# no ssrf\n", encoding="utf-8")
    test_dir = tmp_path / "tests" / "unit"
    test_dir.mkdir(parents=True)
    ssrf_funcs = "\n".join(f"def test_ssrf_{i}(): pass" for i in range(12))
    (test_dir / "test_a2a_http_ssrf_hardening.py").write_text(ssrf_funcs, encoding="utf-8")
    result = gate.check_r2_a2a_http_ssrf_hardened(tmp_path)
    assert result["status"] == "fail"
    assert "A2AHttpSSRFError" in result["detail"]


def test_r2_a2a_http_ssrf_hardened_fails_when_too_few_tests(tmp_path: Path) -> None:
    transport_dir = tmp_path / "src" / "autodev" / "adapters" / "a2a" / "transports"
    transport_dir.mkdir(parents=True)
    (transport_dir / "http.py").write_text(
        "class A2AHttpSSRFError(ValueError): pass\n", encoding="utf-8"
    )
    test_dir = tmp_path / "tests" / "unit"
    test_dir.mkdir(parents=True)
    # Only 3 test functions — below threshold of 10
    (test_dir / "test_a2a_http_ssrf_hardening.py").write_text(
        "def test_a(): pass\ndef test_b(): pass\ndef test_c(): pass\n", encoding="utf-8"
    )
    result = gate.check_r2_a2a_http_ssrf_hardened(tmp_path)
    assert result["status"] == "fail"
    assert "3" in result["detail"]


# ---------------------------------------------------------------------------
# Test 18: r2_milestone_flow_tested
# ---------------------------------------------------------------------------


def test_r2_milestone_flow_tested_fails_when_missing(tmp_path: Path) -> None:
    result = gate.check_r2_milestone_flow_tested(tmp_path)
    assert result["status"] == "fail"


def test_r2_milestone_flow_tested_passes_with_4_tests(tmp_path: Path) -> None:
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    funcs = "\n".join(f"def test_m_{i}(): pass" for i in range(4))
    (unit / "test_milestone_flow.py").write_text(funcs + "\n", encoding="utf-8")
    result = gate.check_r2_milestone_flow_tested(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 19: r2_release_flow_tested
# ---------------------------------------------------------------------------


def test_r2_release_flow_tested_fails_when_missing(tmp_path: Path) -> None:
    result = gate.check_r2_release_flow_tested(tmp_path)
    assert result["status"] == "fail"


def test_r2_release_flow_tested_passes_with_4_tests(tmp_path: Path) -> None:
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    funcs = "\n".join(f"def test_r_{i}(): pass" for i in range(4))
    (unit / "test_release_flow.py").write_text(funcs + "\n", encoding="utf-8")
    result = gate.check_r2_release_flow_tested(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 20: r2_release_workflow_pytest_gate
# ---------------------------------------------------------------------------


def test_r2_release_workflow_pytest_gate_fails_when_no_pytest(tmp_path: Path) -> None:
    gh_dir = tmp_path / ".github" / "workflows"
    gh_dir.mkdir(parents=True)
    (gh_dir / "release.yml").write_text(
        "jobs:\n  publish:\n    needs: test\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    result = gate.check_r2_release_workflow_pytest_gate(tmp_path)
    assert result["status"] == "fail"
    assert "pytest" in result["detail"]


def test_r2_release_workflow_pytest_gate_passes(tmp_path: Path) -> None:
    gh_dir = tmp_path / ".github" / "workflows"
    gh_dir.mkdir(parents=True)
    (gh_dir / "release.yml").write_text(
        "jobs:\n  test:\n    steps:\n      - run: pytest\n"
        "  publish:\n    needs: test\n",
        encoding="utf-8",
    )
    result = gate.check_r2_release_workflow_pytest_gate(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 21: r2_homebrew_metadata_owner_fixed
# ---------------------------------------------------------------------------


def test_r2_homebrew_metadata_owner_fixed_fails_on_old_owner(tmp_path: Path) -> None:
    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    (formula_dir / "autodev-ai.rb").write_text(
        'url "https://github.com/macworkers/autodev-ai/releases/..."\n', encoding="utf-8"
    )
    result = gate.check_r2_homebrew_metadata_owner_fixed(tmp_path)
    assert result["status"] == "fail"
    assert "macworkers" in result["detail"]


def test_r2_homebrew_metadata_owner_fixed_passes_with_correct_owner(tmp_path: Path) -> None:
    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    (formula_dir / "autodev-ai.rb").write_text(
        'url "https://github.com/merchloubna70-dot/autodev-ai/releases/..."\n', encoding="utf-8"
    )
    result = gate.check_r2_homebrew_metadata_owner_fixed(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 22: r2_homebrew_sha256_not_stale
# ---------------------------------------------------------------------------


def test_r2_homebrew_sha256_not_stale_fails_on_stale_hash(tmp_path: Path) -> None:
    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    (formula_dir / "autodev-ai.rb").write_text(
        'sha256 "744375fb0bad1234567890abcdef"\n', encoding="utf-8"
    )
    result = gate.check_r2_homebrew_sha256_not_stale(tmp_path)
    assert result["status"] == "fail"
    assert "744375fb" in result["detail"]


def test_r2_homebrew_sha256_not_stale_passes_with_fresh_hash(tmp_path: Path) -> None:
    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    (formula_dir / "autodev-ai.rb").write_text(
        'sha256 "abcdef1234567890goodhash"\n', encoding="utf-8"
    )
    result = gate.check_r2_homebrew_sha256_not_stale(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 23: r2_macos_info_plist_version_match
# ---------------------------------------------------------------------------


def test_r2_macos_info_plist_version_match_skips_when_missing(tmp_path: Path) -> None:
    result = gate.check_r2_macos_info_plist_version_match(tmp_path)
    assert result["status"] == "skip"


def test_r2_macos_info_plist_version_match_passes_with_correct_version(tmp_path: Path) -> None:
    plist_dir = tmp_path / "packaging" / "desktop" / "autodev-ai.app" / "Contents"
    plist_dir.mkdir(parents=True)
    import plistlib
    plist_data = {"CFBundleShortVersionString": "0.1.0a1"}
    with open(plist_dir / "Info.plist", "wb") as fh:
        plistlib.dump(plist_data, fh)
    result = gate.check_r2_macos_info_plist_version_match(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 24: r2_remaining_blockers_recorded
# ---------------------------------------------------------------------------


def test_r2_remaining_blockers_recorded_fails_when_missing(tmp_path: Path) -> None:
    result = gate.check_r2_remaining_blockers_recorded(tmp_path)
    assert result["status"] == "fail"


def test_r2_remaining_blockers_recorded_passes_with_hardening_json(tmp_path: Path) -> None:
    val_dir = tmp_path / "docs" / "validation"
    val_dir.mkdir(parents=True)
    (val_dir / "autodev_release_hardening_round.json").write_text(
        '{"release_blockers": [{"id": "B-01"}]}', encoding="utf-8"
    )
    result = gate.check_r2_remaining_blockers_recorded(tmp_path)
    assert result["status"] == "pass"
    assert "1 items" in result["detail"]
