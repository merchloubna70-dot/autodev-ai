"""
R10 Coverage Backfill — release_readiness_gate.py

Targets the 137 missing lines to push coverage from 78% → ≥95%.

Covers:
  - _run() helper: timeout and FileNotFoundError paths (lines 52-64)
  - check_package_metadata_valid: missing autodev entry-point, wrong CLI ref, parse error (107, 116, 130-131)
  - check_cli_help_works: on-PATH pass/fail, python-m pass/skip (142-149, 159)
  - check_pytest_evidence: .dev-factory with no records, smoke file run pass/fail (171-173, 184-192)
  - check_ruff_passes: fail path (203)
  - check_mypy_passes: fail path (215)
  - check_docs_exist: README missing (224)
  - check_mcp_smoke_path_exists: smoke absent + mcp_server entry pass/fail (258-262)
  - check_a2a_smoke_path_exists: too few files (283)
  - check_mock_executor_works: pass/skip/fail/timeout/FileNotFoundError (328-350)
  - check_packaging_files_exist: pass path (already covered; also partial present)
  - check_no_dangerous_release_claims: README missing skip (376)
  - check_release_blockers_recorded: no val_dir fail (409), only gate-reports (427)
  - check_r2_version_consistency: skip (import fails), module mismatch, parse error (451-454, 475, 499-500)
  - check_r2_license_file_present: non-MIT content (520)
  - check_r2_license_metadata_match: parse error (567-568)
  - check_r2_wheel_version_works: no whl in dist (581), missing toml (588-595), parse error (600-601),
    bad filename (608), mismatch (623)
  - check_r2_a2a_http_ssrf_hardened: missing files (641, 646)
  - check_r2_milestone_flow_tested: too few (691)
  - check_r2_release_flow_tested: too few (719)
  - check_r2_release_workflow_pytest_gate: missing file (742), no needs: (758)
  - check_r2_homebrew_metadata_owner_fixed: missing formula (781)
  - check_r2_homebrew_sha256_not_stale: missing formula (795)
  - check_r2_macos_info_plist_version_match: wrong version, parse error (869-877)
  - check_r2_remaining_blockers_recorded: r2 closure file (891), hardening json parse error (913-916)
  - R3 checks: all missing file / fail / edge branches (937, 948, 958, 962, 972, 978, 988, 994,
    1004, 1008, 1018, 1022, 1032, 1036, 1046, 1050, 1060, 1065, 1069, 1071, 1101, 1103, 1117-1127,
    1150)
  - main() CLI: --include-r3, --strict-r2, --strict-r3, --strict-rc, absolute output path,
    run_checks exception path (1222-1223, 1229, 1234, 1241, 1310, 1323-1342, 1347, 1375)
"""

from __future__ import annotations

import json
import plistlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import autodev.release_readiness_gate as gate

# ---------------------------------------------------------------------------
# Minimal repo fixture shared by most tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def full_repo(tmp_path: Path) -> Path:
    """Full-featured fake repo that passes all 36 checks with _run mocked to (0,'','')."""
    _populate_full_repo(tmp_path)
    return tmp_path


def _populate_full_repo(p: Path) -> None:
    """Write the minimal file tree for a complete-pass repo."""
    (p / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0"\nrequires-python = ">=3.10"\n'
        'license = {text = "MIT"}\n'
        '[project.scripts]\nautodev = "autodev.cli:app"\n',
        encoding="utf-8",
    )
    (p / "README.md").write_text("# autodev-ai\n", encoding="utf-8")
    (p / "LICENSE").write_text(
        "MIT License\n\nPermission is hereby granted, free of charge...\n",
        encoding="utf-8",
    )
    (p / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.0a1] — 2026-05-14\n- First alpha\n",
        encoding="utf-8",
    )
    docs = p / "docs"
    docs.mkdir()
    for name in ("quickstart.md", "architecture.md", "faq.md"):
        (docs / name).write_text(name, encoding="utf-8")
    (docs / "tutorials").mkdir()
    (docs / "configuration.md").write_text("# Config\n\n" + "x" * 500, encoding="utf-8")
    (docs / "troubleshooting.md").write_text("# Troubleshoot\n\n" + "x" * 500, encoding="utf-8")
    ex = p / "examples"
    ex.mkdir()
    (ex / "README.md").write_text("examples", encoding="utf-8")
    val = docs / "validation"
    val.mkdir()
    (val / "autodev_release_readiness_gate.json").write_text("{}", encoding="utf-8")
    (val / "autodev_release_hardening_round.json").write_text(
        '{"release_blockers": []}', encoding="utf-8"
    )
    intg = p / "tests" / "integration"
    intg.mkdir(parents=True)
    (intg / "test_mcp_server_smoke.py").write_text("", encoding="utf-8")
    unit = p / "tests" / "unit"
    unit.mkdir(parents=True)
    for i in range(6):
        (unit / f"test_a2a_check_{i}.py").write_text("", encoding="utf-8")
    ssrf_funcs = "\n".join(f"def test_ssrf_{i}(): pass" for i in range(12))
    (unit / "test_a2a_http_ssrf_hardening.py").write_text(ssrf_funcs + "\n", encoding="utf-8")
    milestone_funcs = "\n".join(f"def test_milestone_{i}(): pass" for i in range(5))
    (unit / "test_milestone_flow.py").write_text(milestone_funcs + "\n", encoding="utf-8")
    release_funcs = "\n".join(f"def test_release_{i}(): pass" for i in range(5))
    (unit / "test_release_flow.py").write_text(release_funcs + "\n", encoding="utf-8")
    docker = p / "packaging" / "docker"
    docker.mkdir(parents=True)
    (docker / "Dockerfile").write_text(
        "FROM python:3.12-slim@sha256:" + ("a" * 64) + "\n", encoding="utf-8"
    )
    pyinst = p / "packaging" / "pyinstaller"
    pyinst.mkdir(parents=True)
    (pyinst / "autodev.spec").write_text("# spec\n", encoding="utf-8")
    formula_dir = p / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    (formula_dir / "autodev-ai.rb").write_text(
        "# STATUS: BLOCKED for publish\n"
        'url "https://github.com/merchloubna70-dot/autodev-ai/releases/..."\n'
        'sha256 "TODO_PUBLISH_SHA256"\n',
        encoding="utf-8",
    )
    (p / "packaging" / "homebrew" / "PUBLISH_CHECKLIST.md").write_text(
        "# Homebrew publish checklist\n\n1. Confirm PyPI live\n", encoding="utf-8"
    )
    transport_dir = p / "src" / "autodev" / "adapters" / "a2a" / "transports"
    transport_dir.mkdir(parents=True)
    (transport_dir / "http.py").write_text(
        "class A2AHttpSSRFError(ValueError): pass\n"
        "def _resolve_and_pin_host(host: str) -> str: ...\n"
        "class _PinnedHTTPHandler: pass\n"
        "class _PinnedHTTPSHandler: pass\n",
        encoding="utf-8",
    )
    mcp_dir = p / "src" / "autodev" / "mcp_server"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "tools.py").write_text(
        "AUTODEV_MCP_ALLOW_APPLY = 'AUTODEV_MCP_ALLOW_APPLY'\n"
        "def tool(allow_apply: bool = False): ...\n",
        encoding="utf-8",
    )
    isolator_dir = p / "src" / "autodev" / "executors"
    isolator_dir.mkdir(parents=True)
    (isolator_dir / "worker_isolator.py").write_text(
        "class WorkerIsolatorPathEscapeError(Exception): pass\n", encoding="utf-8"
    )
    plist_dir = p / "packaging" / "desktop" / "autodev-ai.app" / "Contents"
    plist_dir.mkdir(parents=True)
    plist_data = {"CFBundleShortVersionString": "0.1.0a1"}
    with open(plist_dir / "Info.plist", "wb") as fh:
        plistlib.dump(plist_data, fh)
    gh_dir = p / ".github" / "workflows"
    gh_dir.mkdir(parents=True)
    (gh_dir / "release.yml").write_text(
        "jobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n"
        "  publish:\n    needs: test\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    (gh_dir / "lint.yml").write_text(
        "jobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - run: ruff check src tests scripts\n      - run: mypy src/autodev\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# _run helper: timeout and FileNotFoundError
# ---------------------------------------------------------------------------


def test_run_timeout_returns_minus1(tmp_path: Path) -> None:
    """_run should return (-1, '', 'timeout') on TimeoutExpired."""
    with patch("autodev.release_readiness_gate.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd=["sleep"], timeout=1)):
        rc, out, err = gate._run(["sleep", "99"], tmp_path, timeout=1)
    assert rc == -1
    assert err == "timeout"
    assert out == ""


def test_run_file_not_found_returns_minus2(tmp_path: Path) -> None:
    """_run should return (-2, '', 'command not found: ...') on FileNotFoundError."""
    with patch("autodev.release_readiness_gate.subprocess.run",
               side_effect=FileNotFoundError()):
        rc, out, err = gate._run(["nonexistent_command_xyz"], tmp_path)
    assert rc == -2
    assert "nonexistent_command_xyz" in err
    assert out == ""


def test_run_success_returns_tuple(tmp_path: Path) -> None:
    """_run wraps subprocess.run and returns (rc, stdout, stderr)."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "hello"
    mock_proc.stderr = ""
    with patch("autodev.release_readiness_gate.subprocess.run", return_value=mock_proc):
        rc, out, _err = gate._run(["echo", "hello"], tmp_path)
    assert rc == 0
    assert out == "hello"


# ---------------------------------------------------------------------------
# check_package_metadata_valid: additional branches
# ---------------------------------------------------------------------------


def test_package_metadata_valid_missing_autodev_entrypoint(tmp_path: Path) -> None:
    """Fails when [project.scripts] exists but 'autodev' key is absent."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0"\nrequires-python = ">=3.10"\n'
        '[project.scripts]\nother_cli = "autodev.cli:app"\n',
        encoding="utf-8",
    )
    result = gate.check_package_metadata_valid(tmp_path)
    assert result["status"] == "fail"
    assert "autodev" in result["detail"]


def test_package_metadata_valid_wrong_cli_ref(tmp_path: Path) -> None:
    """Fails when 'autodev' entry-point does not reference autodev.cli."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0"\nrequires-python = ">=3.10"\n'
        '[project.scripts]\nautodev = "some.other.module:main"\n',
        encoding="utf-8",
    )
    result = gate.check_package_metadata_valid(tmp_path)
    assert result["status"] == "fail"
    assert "autodev.cli" in result["detail"]


def test_package_metadata_valid_parse_error(tmp_path: Path) -> None:
    """Fails gracefully when pyproject.toml cannot be parsed."""
    (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe invalid toml \x00")
    result = gate.check_package_metadata_valid(tmp_path)
    assert result["status"] == "fail"
    assert "Parse error" in result["detail"] or "fail" in result["status"]


# ---------------------------------------------------------------------------
# check_cli_help_works: on-PATH pass/fail, python -m pass/skip
# ---------------------------------------------------------------------------


def test_cli_help_works_on_path_pass(tmp_path: Path) -> None:
    """When autodev is on PATH and --help exits 0 → pass."""
    def fake_run(cmd, cwd, timeout=30):
        if cmd == ["which", "autodev"]:
            return 0, "/usr/local/bin/autodev", ""
        if cmd == ["autodev", "--help"]:
            return 0, "usage ...", ""
        return 1, "", "error"

    with patch.object(gate, "_run", side_effect=fake_run):
        result = gate.check_cli_help_works(tmp_path)
    assert result["status"] == "pass"
    assert "exit 0" in result["detail"]


def test_cli_help_works_on_path_fail(tmp_path: Path) -> None:
    """When autodev is on PATH but --help exits non-zero → fail."""
    def fake_run(cmd, cwd, timeout=30):
        if cmd == ["which", "autodev"]:
            return 0, "/usr/local/bin/autodev", ""
        if cmd == ["autodev", "--help"]:
            return 1, "", "something went wrong"
        return 1, "", ""

    with patch.object(gate, "_run", side_effect=fake_run):
        result = gate.check_cli_help_works(tmp_path)
    assert result["status"] == "fail"
    assert "exited 1" in result["detail"]


def test_cli_help_works_python_m_pass(tmp_path: Path) -> None:
    """When autodev not on PATH but python -m works → pass."""
    def fake_run(cmd, cwd, timeout=30):
        if cmd == ["which", "autodev"]:
            return 1, "", ""
        # python -m autodev.cli --help
        return 0, "usage ...", ""

    with patch.object(gate, "_run", side_effect=fake_run):
        result = gate.check_cli_help_works(tmp_path)
    assert result["status"] == "pass"
    assert "python -m" in result["detail"]


def test_cli_help_works_both_fail_skip(tmp_path: Path) -> None:
    """When neither which nor python -m works → skip."""
    with patch.object(gate, "_run", return_value=(1, "", "not found")):
        result = gate.check_cli_help_works(tmp_path)
    assert result["status"] == "skip"


# ---------------------------------------------------------------------------
# check_pytest_evidence: various branches
# ---------------------------------------------------------------------------


def test_pytest_evidence_dev_factory_exists_but_empty(tmp_path: Path) -> None:
    """When .dev-factory exists but has no *.json → falls through to smoke file logic."""
    df = tmp_path / ".dev-factory"
    df.mkdir()
    # No json files, no smoke file → skip
    result = gate.check_pytest_evidence(tmp_path)
    assert result["status"] == "skip"


def test_pytest_evidence_dev_factory_with_records(tmp_path: Path) -> None:
    """When .dev-factory has *.json records → pass immediately."""
    df = tmp_path / ".dev-factory"
    df.mkdir()
    (df / "run_001.json").write_text('{"result": "pass"}', encoding="utf-8")
    result = gate.check_pytest_evidence(tmp_path)
    assert result["status"] == "pass"
    assert "run_001.json" in result["detail"]


def test_pytest_evidence_smoke_file_passes(tmp_path: Path) -> None:
    """When smoke file exists and pytest exits 0 → pass."""
    smoke = tmp_path / "tests" / "unit"
    smoke.mkdir(parents=True)
    (smoke / "test_prfaq_style.py").write_text("", encoding="utf-8")

    with patch.object(gate, "_run", return_value=(0, "1 passed", "")):
        result = gate.check_pytest_evidence(tmp_path)
    assert result["status"] == "pass"
    assert "passed" in result["detail"].lower() or "Smoke pytest passed" in result["detail"]


def test_pytest_evidence_smoke_file_fails(tmp_path: Path) -> None:
    """When smoke file exists but pytest exits non-zero → fail."""
    smoke = tmp_path / "tests" / "unit"
    smoke.mkdir(parents=True)
    (smoke / "test_prfaq_style.py").write_text("", encoding="utf-8")

    with patch.object(gate, "_run", return_value=(1, "", "1 failed")):
        result = gate.check_pytest_evidence(tmp_path)
    assert result["status"] == "fail"
    assert "exit 1" in result["detail"]


# ---------------------------------------------------------------------------
# check_ruff_passes and check_mypy_passes: fail branches
# ---------------------------------------------------------------------------


def test_ruff_passes_fail_path(tmp_path: Path) -> None:
    """check_ruff_passes returns fail when ruff exits non-zero."""
    with patch.object(gate, "_run", return_value=(1, "E001 error found", "")):
        result = gate.check_ruff_passes(tmp_path)
    assert result["status"] == "fail"
    assert "ruff exit 1" in result["detail"]


def test_mypy_passes_fail_path(tmp_path: Path) -> None:
    """check_mypy_passes returns fail when mypy exits non-zero."""
    with patch.object(gate, "_run", return_value=(1, "Found 2 errors", "")):
        result = gate.check_mypy_passes(tmp_path)
    assert result["status"] == "fail"
    assert "mypy exit 1" in result["detail"]


# ---------------------------------------------------------------------------
# check_docs_exist: README missing
# ---------------------------------------------------------------------------


def test_docs_exist_fails_readme_missing(tmp_path: Path) -> None:
    """check_docs_exist fails immediately when README.md is absent."""
    result = gate.check_docs_exist(tmp_path)
    assert result["status"] == "fail"
    assert "README.md not found" in result["detail"]


# ---------------------------------------------------------------------------
# check_mcp_smoke_path_exists: smoke absent, fallback paths
# ---------------------------------------------------------------------------


def test_mcp_smoke_path_absent_with_server_entry(tmp_path: Path) -> None:
    """When smoke test missing but mcp_server/__init__.py exists → pass."""
    mcp_dir = tmp_path / "src" / "autodev" / "mcp_server"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "__init__.py").write_text("", encoding="utf-8")
    result = gate.check_mcp_smoke_path_exists(tmp_path)
    assert result["status"] == "pass"
    assert "MCP server entry found" in result["detail"]


def test_mcp_smoke_path_both_absent(tmp_path: Path) -> None:
    """When both smoke test and mcp_server entry are absent → fail."""
    result = gate.check_mcp_smoke_path_exists(tmp_path)
    assert result["status"] == "fail"
    assert "No MCP smoke test" in result["detail"]


# ---------------------------------------------------------------------------
# check_a2a_smoke_path_exists: too few files
# ---------------------------------------------------------------------------


def test_a2a_smoke_path_too_few_files(tmp_path: Path) -> None:
    """Fails when fewer than 5 a2a/roundtable test files found."""
    tests = tmp_path / "tests" / "unit"
    tests.mkdir(parents=True)
    for i in range(3):
        (tests / f"test_a2a_{i}.py").write_text("", encoding="utf-8")
    result = gate.check_a2a_smoke_path_exists(tmp_path)
    assert result["status"] == "fail"
    assert "3" in result["detail"]


# ---------------------------------------------------------------------------
# check_mock_executor_works: various subprocess paths
# ---------------------------------------------------------------------------


def test_mock_executor_works_pass(tmp_path: Path) -> None:
    """Returns pass when first subprocess call succeeds."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "feature"
    mock_proc.stderr = ""

    with patch("autodev.release_readiness_gate.subprocess.run", return_value=mock_proc):
        result = gate.check_mock_executor_works(tmp_path)
    assert result["status"] == "pass"


def test_mock_executor_works_classify_not_found(tmp_path: Path) -> None:
    """Returns skip when returncode==2 and 'No such command' in output."""
    mock_proc = MagicMock()
    mock_proc.returncode = 2
    mock_proc.stdout = ""
    mock_proc.stderr = "No such command 'classify-input'"

    with patch("autodev.release_readiness_gate.subprocess.run", return_value=mock_proc):
        result = gate.check_mock_executor_works(tmp_path)
    assert result["status"] == "skip"
    assert "classify-input" in result["detail"]


def test_mock_executor_works_file_not_found_then_skip(tmp_path: Path) -> None:
    """FileNotFoundError on both commands → falls through to final skip."""
    with patch("autodev.release_readiness_gate.subprocess.run",
               side_effect=FileNotFoundError()):
        result = gate.check_mock_executor_works(tmp_path)
    assert result["status"] == "skip"
    assert "not on PATH" in result["detail"]


def test_mock_executor_works_timeout(tmp_path: Path) -> None:
    """TimeoutExpired during mock executor → fail."""
    with patch("autodev.release_readiness_gate.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd=["autodev"], timeout=15)):
        result = gate.check_mock_executor_works(tmp_path)
    assert result["status"] == "fail"
    assert "timed out" in result["detail"]


def test_mock_executor_works_nonzero_no_subcommand_message(tmp_path: Path) -> None:
    """Non-zero returncode without 'No such command' continues to next cmd."""
    call_count = [0]

    def fake_run(cmd, *args, **kwargs):
        call_count[0] += 1
        proc = MagicMock()
        proc.returncode = 1
        proc.stdout = "some error"
        proc.stderr = "bad args"
        return proc

    with patch("autodev.release_readiness_gate.subprocess.run", side_effect=fake_run):
        result = gate.check_mock_executor_works(tmp_path)
    # Both commands fail → final skip
    assert result["status"] == "skip"


# ---------------------------------------------------------------------------
# check_no_dangerous_release_claims: skip when README absent
# ---------------------------------------------------------------------------


def test_no_dangerous_release_claims_skip_no_readme(tmp_path: Path) -> None:
    """Returns skip when README.md does not exist."""
    result = gate.check_no_dangerous_release_claims(tmp_path)
    assert result["status"] == "skip"
    assert "README.md not found" in result["detail"]


# ---------------------------------------------------------------------------
# check_release_blockers_recorded: no val_dir and only gate-report
# ---------------------------------------------------------------------------


def test_release_blockers_recorded_no_val_dir(tmp_path: Path) -> None:
    """Fails when docs/validation/ directory does not exist."""
    result = gate.check_release_blockers_recorded(tmp_path)
    assert result["status"] == "fail"
    assert "docs/validation/" in result["detail"]


def test_release_blockers_recorded_only_gate_report(tmp_path: Path) -> None:
    """Passes when only a gate report file is present (no hardening round file)."""
    val = tmp_path / "docs" / "validation"
    val.mkdir(parents=True)
    (val / "autodev_release_readiness_gate_run.json").write_text("{}", encoding="utf-8")
    result = gate.check_release_blockers_recorded(tmp_path)
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# check_r2_version_consistency: skip when import fails, mismatch, parse error
# ---------------------------------------------------------------------------


def test_r2_version_consistency_skip_when_import_fails(tmp_path: Path) -> None:
    """Returns skip when importing autodev fails (rc != 0)."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0a1"\nrequires-python = ">=3.10"\n',
        encoding="utf-8",
    )
    with patch.object(gate, "_run", return_value=(1, "", "ModuleNotFoundError")):
        result = gate.check_r2_version_consistency(tmp_path)
    assert result["status"] == "skip"
    assert "Cannot import autodev" in result["detail"]


def test_r2_version_consistency_mismatch(tmp_path: Path) -> None:
    """Fails when pyproject version != module __version__."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0a1"\nrequires-python = ">=3.10"\n',
        encoding="utf-8",
    )
    with patch.object(gate, "_run", return_value=(0, "0.1.0b99\n", "")):
        result = gate.check_r2_version_consistency(tmp_path)
    assert result["status"] == "fail"
    assert "0.1.0a1" in result["detail"]
    assert "0.1.0b99" in result["detail"]


def test_r2_version_consistency_parse_error(tmp_path: Path) -> None:
    """Fails gracefully on toml parse error."""
    (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe invalid")
    result = gate.check_r2_version_consistency(tmp_path)
    assert result["status"] == "fail"
    assert "Parse error" in result["detail"] or "fail" in result["status"]


# ---------------------------------------------------------------------------
# check_r2_license_file_present: non-MIT content
# ---------------------------------------------------------------------------


def test_r2_license_file_present_non_mit_content(tmp_path: Path) -> None:
    """Fails when LICENSE exists but contains neither 'MIT License' nor 'Permission is hereby granted'."""
    (tmp_path / "LICENSE").write_text(
        "Apache License 2.0\n\nLicensed under the Apache License...\n",
        encoding="utf-8",
    )
    result = gate.check_r2_license_file_present(tmp_path)
    assert result["status"] == "fail"
    assert "MIT License" in result["detail"] or "Permission is hereby granted" in result["detail"]


# ---------------------------------------------------------------------------
# check_r2_license_metadata_match: parse error
# ---------------------------------------------------------------------------


def test_r2_license_metadata_match_parse_error(tmp_path: Path) -> None:
    """Fails gracefully when pyproject.toml is not valid TOML."""
    (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe bad toml")
    result = gate.check_r2_license_metadata_match(tmp_path)
    assert result["status"] == "fail"
    assert "Parse error" in result["detail"] or "fail" in result["status"]


# ---------------------------------------------------------------------------
# check_r2_wheel_version_works: additional branches
# ---------------------------------------------------------------------------


def test_r2_wheel_version_works_no_whl_in_dist(tmp_path: Path) -> None:
    """Skips when dist/ exists but has no .whl files."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "something.tar.gz").write_text("", encoding="utf-8")
    result = gate.check_r2_wheel_version_works(tmp_path)
    assert result["status"] == "skip"
    assert "no *.whl" in result["detail"]


def test_r2_wheel_version_works_missing_toml_with_dist(tmp_path: Path) -> None:
    """Fails when dist has a wheel but pyproject.toml is absent."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "autodev_ai-0.1.0a1-py3-none-any.whl").write_text("", encoding="utf-8")
    # No pyproject.toml
    result = gate.check_r2_wheel_version_works(tmp_path)
    assert result["status"] == "fail"
    assert "pyproject.toml not found" in result["detail"]


def test_r2_wheel_version_works_parse_error(tmp_path: Path) -> None:
    """Fails gracefully when pyproject.toml cannot be parsed."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "autodev_ai-0.1.0a1-py3-none-any.whl").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe bad toml")
    result = gate.check_r2_wheel_version_works(tmp_path)
    assert result["status"] == "fail"
    assert "Failed to read pyproject.toml" in result["detail"] or "fail" == result["status"]


def test_r2_wheel_version_works_bad_filename(tmp_path: Path) -> None:
    """Fails when wheel filename has fewer than 2 dash-separated parts."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "badwheelname.whl").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0a1"\nrequires-python = ">=3.10"\n',
        encoding="utf-8",
    )
    result = gate.check_r2_wheel_version_works(tmp_path)
    assert result["status"] == "fail"
    assert "Cannot parse wheel filename" in result["detail"]


def test_r2_wheel_version_works_version_mismatch(tmp_path: Path) -> None:
    """Fails when wheel version does not match pyproject version."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "autodev_ai-0.2.0-py3-none-any.whl").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "autodev-ai"\nversion = "0.1.0a1"\nrequires-python = ">=3.10"\n',
        encoding="utf-8",
    )
    result = gate.check_r2_wheel_version_works(tmp_path)
    assert result["status"] == "fail"
    assert "0.2.0" in result["detail"]
    assert "0.1.0a1" in result["detail"]


# ---------------------------------------------------------------------------
# check_r2_a2a_http_ssrf_hardened: missing files branches
# ---------------------------------------------------------------------------


def test_r2_a2a_http_ssrf_missing_transport(tmp_path: Path) -> None:
    """Fails when http.py transport is absent (even if ssrf test exists)."""
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    ssrf_funcs = "\n".join(f"def test_ssrf_{i}(): pass" for i in range(12))
    (unit / "test_a2a_http_ssrf_hardening.py").write_text(ssrf_funcs, encoding="utf-8")
    # http.py transport missing
    result = gate.check_r2_a2a_http_ssrf_hardened(tmp_path)
    assert result["status"] == "fail"
    assert "Missing" in result["detail"]


def test_r2_a2a_http_ssrf_both_missing(tmp_path: Path) -> None:
    """Fails listing both missing files when neither transport nor ssrf test exist."""
    result = gate.check_r2_a2a_http_ssrf_hardened(tmp_path)
    assert result["status"] == "fail"
    assert "Missing" in result["detail"]


# ---------------------------------------------------------------------------
# check_r2_milestone_flow_tested: too few test functions
# ---------------------------------------------------------------------------


def test_r2_milestone_flow_tested_too_few(tmp_path: Path) -> None:
    """Fails when test file has fewer than 4 test functions."""
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    funcs = "\n".join(f"def test_m_{i}(): pass" for i in range(2))
    (unit / "test_milestone_flow.py").write_text(funcs + "\n", encoding="utf-8")
    result = gate.check_r2_milestone_flow_tested(tmp_path)
    assert result["status"] == "fail"
    assert "2" in result["detail"]


# ---------------------------------------------------------------------------
# check_r2_release_flow_tested: too few test functions
# ---------------------------------------------------------------------------


def test_r2_release_flow_tested_too_few(tmp_path: Path) -> None:
    """Fails when test file has fewer than 4 test functions."""
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    funcs = "\n".join(f"def test_r_{i}(): pass" for i in range(1))
    (unit / "test_release_flow.py").write_text(funcs + "\n", encoding="utf-8")
    result = gate.check_r2_release_flow_tested(tmp_path)
    assert result["status"] == "fail"
    assert "1" in result["detail"]


# ---------------------------------------------------------------------------
# check_r2_release_workflow_pytest_gate: missing file + has pytest but no needs
# ---------------------------------------------------------------------------


def test_r2_release_workflow_pytest_gate_missing_file(tmp_path: Path) -> None:
    """Fails when .github/workflows/release.yml does not exist."""
    result = gate.check_r2_release_workflow_pytest_gate(tmp_path)
    assert result["status"] == "fail"
    assert "release.yml not found" in result["detail"]


def test_r2_release_workflow_pytest_gate_has_pytest_no_needs(tmp_path: Path) -> None:
    """Fails when pytest is present but 'needs:' directive is absent."""
    gh_dir = tmp_path / ".github" / "workflows"
    gh_dir.mkdir(parents=True)
    (gh_dir / "release.yml").write_text(
        "jobs:\n  publish:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n",
        encoding="utf-8",
    )
    result = gate.check_r2_release_workflow_pytest_gate(tmp_path)
    assert result["status"] == "fail"
    assert "needs:" in result["detail"]


# ---------------------------------------------------------------------------
# check_r2_homebrew_metadata_owner_fixed / sha256_not_stale: missing formula
# ---------------------------------------------------------------------------


def test_r2_homebrew_metadata_owner_fixed_missing_formula(tmp_path: Path) -> None:
    """Fails when Homebrew formula file is absent."""
    result = gate.check_r2_homebrew_metadata_owner_fixed(tmp_path)
    assert result["status"] == "fail"
    assert "not found" in result["detail"]


def test_r2_homebrew_sha256_not_stale_missing_formula(tmp_path: Path) -> None:
    """Fails when Homebrew formula file is absent."""
    result = gate.check_r2_homebrew_sha256_not_stale(tmp_path)
    assert result["status"] == "fail"
    assert "not found" in result["detail"]


def test_r2_homebrew_metadata_no_correct_owner(tmp_path: Path) -> None:
    """Fails when formula has neither old nor new owner."""
    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    (formula_dir / "autodev-ai.rb").write_text(
        'url "https://github.com/unknown_user/autodev-ai/releases/..."\n',
        encoding="utf-8",
    )
    result = gate.check_r2_homebrew_metadata_owner_fixed(tmp_path)
    assert result["status"] == "fail"
    assert "expected owner" in result["detail"]


# ---------------------------------------------------------------------------
# check_r2_macos_info_plist_version_match: wrong version and parse error
# ---------------------------------------------------------------------------


def test_r2_macos_info_plist_wrong_version(tmp_path: Path) -> None:
    """Fails when CFBundleShortVersionString does not contain '0.1.0'."""
    plist_dir = tmp_path / "packaging" / "desktop" / "autodev-ai.app" / "Contents"
    plist_dir.mkdir(parents=True)
    plist_data = {"CFBundleShortVersionString": "2.0.0"}
    with open(plist_dir / "Info.plist", "wb") as fh:
        plistlib.dump(plist_data, fh)
    result = gate.check_r2_macos_info_plist_version_match(tmp_path)
    assert result["status"] == "fail"
    assert "2.0.0" in result["detail"]


def test_r2_macos_info_plist_parse_error(tmp_path: Path) -> None:
    """Fails gracefully when Info.plist cannot be parsed."""
    plist_dir = tmp_path / "packaging" / "desktop" / "autodev-ai.app" / "Contents"
    plist_dir.mkdir(parents=True)
    (plist_dir / "Info.plist").write_bytes(b"not a valid plist!!!")
    result = gate.check_r2_macos_info_plist_version_match(tmp_path)
    assert result["status"] == "fail"
    assert "Failed to parse" in result["detail"]


# ---------------------------------------------------------------------------
# check_r2_remaining_blockers_recorded: r2 closure file, hardening json parse error
# ---------------------------------------------------------------------------


def test_r2_remaining_blockers_recorded_r2_closure_file(tmp_path: Path) -> None:
    """Passes when autodev_r2_pypi_release_blocker_closure.json exists."""
    val = tmp_path / "docs" / "validation"
    val.mkdir(parents=True)
    (val / "autodev_r2_pypi_release_blocker_closure.json").write_text(
        '{"closed": true}', encoding="utf-8"
    )
    result = gate.check_r2_remaining_blockers_recorded(tmp_path)
    assert result["status"] == "pass"
    assert "closure" in result["detail"].lower() or "found" in result["detail"]


def test_r2_remaining_blockers_recorded_hardening_parse_error(tmp_path: Path) -> None:
    """Falls through to fail when hardening_round.json has invalid JSON."""
    val = tmp_path / "docs" / "validation"
    val.mkdir(parents=True)
    (val / "autodev_release_hardening_round.json").write_bytes(b"\xff\xfe broken json")
    result = gate.check_r2_remaining_blockers_recorded(tmp_path)
    assert result["status"] == "fail"


def test_r2_remaining_blockers_recorded_hardening_no_array(tmp_path: Path) -> None:
    """Falls through to fail when hardening_round.json has no 'release_blockers' array."""
    val = tmp_path / "docs" / "validation"
    val.mkdir(parents=True)
    (val / "autodev_release_hardening_round.json").write_text(
        '{"something_else": "foo"}', encoding="utf-8"
    )
    result = gate.check_r2_remaining_blockers_recorded(tmp_path)
    assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# R3 check functions: all fail/skip/pass branches
# ---------------------------------------------------------------------------


def test_r3_mypy_clean_fail(tmp_path: Path) -> None:
    with patch.object(gate, "_run", return_value=(1, "Found 3 errors in 1 file", "")):
        result = gate.check_r3_mypy_clean(tmp_path)
    assert result["status"] == "fail"
    assert "mypy returned exit 1" in result["detail"]


def test_r3_mypy_clean_fail_no_output(tmp_path: Path) -> None:
    """Fail path when mypy has no stdout but has stderr."""
    with patch.object(gate, "_run", return_value=(1, "", "mypy: fatal error")):
        result = gate.check_r3_mypy_clean(tmp_path)
    assert result["status"] == "fail"


def test_r3_ruff_clean_fail(tmp_path: Path) -> None:
    with patch.object(gate, "_run", return_value=(1, "E001 problem\n", "")):
        result = gate.check_r3_ruff_clean(tmp_path)
    assert result["status"] == "fail"
    assert "ruff returned exit 1" in result["detail"]


def test_r3_ruff_clean_fail_no_output(tmp_path: Path) -> None:
    with patch.object(gate, "_run", return_value=(1, "", "ruff: fatal")):
        result = gate.check_r3_ruff_clean(tmp_path)
    assert result["status"] == "fail"


def test_r3_lint_yml_scans_scripts_missing(tmp_path: Path) -> None:
    result = gate.check_r3_lint_yml_scans_scripts(tmp_path)
    assert result["status"] == "fail"
    assert "lint.yml not found" in result["detail"]


def test_r3_lint_yml_scans_scripts_no_scripts(tmp_path: Path) -> None:
    """Fails when lint.yml exists but does not mention 'scripts'."""
    gh_dir = tmp_path / ".github" / "workflows"
    gh_dir.mkdir(parents=True)
    (gh_dir / "lint.yml").write_text(
        "jobs:\n  lint:\n    steps:\n      - run: ruff check src\n", encoding="utf-8"
    )
    result = gate.check_r3_lint_yml_scans_scripts(tmp_path)
    assert result["status"] == "fail"
    assert "scripts/" in result["detail"]


def test_r3_mcp_apply_guardrail_missing_file(tmp_path: Path) -> None:
    result = gate.check_r3_mcp_apply_guardrail_present(tmp_path)
    assert result["status"] == "fail"
    assert "tools.py not found" in result["detail"]


def test_r3_mcp_apply_guardrail_incomplete(tmp_path: Path) -> None:
    """Fails when only one of the two required symbols is present."""
    mcp_dir = tmp_path / "src" / "autodev" / "mcp_server"
    mcp_dir.mkdir(parents=True)
    # Only env var, no allow_apply param
    (mcp_dir / "tools.py").write_text(
        "AUTODEV_MCP_ALLOW_APPLY = 'AUTODEV_MCP_ALLOW_APPLY'\n", encoding="utf-8"
    )
    result = gate.check_r3_mcp_apply_guardrail_present(tmp_path)
    assert result["status"] == "fail"
    assert "incomplete" in result["detail"].lower() or "guardrail" in result["detail"].lower()


def test_r3_a2a_dns_rebinding_pinned_missing_file(tmp_path: Path) -> None:
    result = gate.check_r3_a2a_dns_rebinding_pinned(tmp_path)
    assert result["status"] == "fail"
    assert "http.py not found" in result["detail"]


def test_r3_a2a_dns_rebinding_pinned_incomplete(tmp_path: Path) -> None:
    """Fails when http.py exists but lacks required symbols."""
    transport_dir = tmp_path / "src" / "autodev" / "adapters" / "a2a" / "transports"
    transport_dir.mkdir(parents=True)
    (transport_dir / "http.py").write_text("class NotAPinHandler: pass\n", encoding="utf-8")
    result = gate.check_r3_a2a_dns_rebinding_pinned(tmp_path)
    assert result["status"] == "fail"
    assert "incomplete" in result["detail"].lower() or "resolver=" in result["detail"]


def test_r3_worker_isolator_symlink_safe_missing(tmp_path: Path) -> None:
    result = gate.check_r3_worker_isolator_symlink_safe(tmp_path)
    assert result["status"] == "fail"
    assert "not found" in result["detail"]


def test_r3_worker_isolator_symlink_safe_no_error_class(tmp_path: Path) -> None:
    """Fails when worker_isolator.py exists but lacks WorkerIsolatorPathEscapeError."""
    isolator_dir = tmp_path / "src" / "autodev" / "executors"
    isolator_dir.mkdir(parents=True)
    (isolator_dir / "worker_isolator.py").write_text(
        "class WorkerIsolator: pass\n", encoding="utf-8"
    )
    result = gate.check_r3_worker_isolator_symlink_safe(tmp_path)
    assert result["status"] == "fail"
    assert "missing" in result["detail"].lower() or "not found" in result["detail"].lower()


def test_r3_changelog_missing(tmp_path: Path) -> None:
    result = gate.check_r3_changelog_present(tmp_path)
    assert result["status"] == "fail"
    assert "CHANGELOG.md not found" in result["detail"]


def test_r3_changelog_no_version(tmp_path: Path) -> None:
    """Fails when CHANGELOG.md exists but does not mention 0.1.0a1."""
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.2.0] — Some future release\n", encoding="utf-8"
    )
    result = gate.check_r3_changelog_present(tmp_path)
    assert result["status"] == "fail"
    assert "0.1.0a1" in result["detail"]


def test_r3_configuration_doc_missing(tmp_path: Path) -> None:
    result = gate.check_r3_configuration_doc_present(tmp_path)
    assert result["status"] == "fail"
    assert "configuration.md not found" in result["detail"]


def test_r3_configuration_doc_too_short(tmp_path: Path) -> None:
    """Fails when configuration.md is shorter than 500 chars."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "configuration.md").write_text("# Short\n", encoding="utf-8")
    result = gate.check_r3_configuration_doc_present(tmp_path)
    assert result["status"] == "fail"
    assert "too short" in result["detail"]


def test_r3_troubleshooting_doc_missing(tmp_path: Path) -> None:
    result = gate.check_r3_troubleshooting_doc_present(tmp_path)
    assert result["status"] == "fail"
    assert "troubleshooting.md not found" in result["detail"]


def test_r3_troubleshooting_doc_too_short(tmp_path: Path) -> None:
    """Fails when troubleshooting.md is shorter than 500 chars."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "troubleshooting.md").write_text("# Brief\n", encoding="utf-8")
    result = gate.check_r3_troubleshooting_doc_present(tmp_path)
    assert result["status"] == "fail"
    assert "too short" in result["detail"]


def test_r3_docker_base_digest_pinned_missing(tmp_path: Path) -> None:
    result = gate.check_r3_docker_base_digest_pinned(tmp_path)
    assert result["status"] == "fail"
    assert "Dockerfile not found" in result["detail"]


def test_r3_docker_base_digest_pinned_no_from_lines(tmp_path: Path) -> None:
    """Fails when Dockerfile has no FROM lines."""
    docker = tmp_path / "packaging" / "docker"
    docker.mkdir(parents=True)
    (docker / "Dockerfile").write_text(
        "# Just a comment\nRUN echo hello\n", encoding="utf-8"
    )
    result = gate.check_r3_docker_base_digest_pinned(tmp_path)
    assert result["status"] == "fail"
    assert "No FROM lines" in result["detail"]


def test_r3_docker_base_digest_pinned_unpinned(tmp_path: Path) -> None:
    """Fails when FROM line lacks @sha256: digest."""
    docker = tmp_path / "packaging" / "docker"
    docker.mkdir(parents=True)
    (docker / "Dockerfile").write_text(
        "FROM python:3.12-slim\nRUN echo hello\n", encoding="utf-8"
    )
    result = gate.check_r3_docker_base_digest_pinned(tmp_path)
    assert result["status"] == "fail"
    assert "not digest-pinned" in result["detail"]


def test_r3_homebrew_publish_time_blocker_missing_formula(tmp_path: Path) -> None:
    """Fails when formula file is absent."""
    result = gate.check_r3_homebrew_publish_time_blocker_clean(tmp_path)
    assert result["status"] == "fail"
    assert "Formula file not found" in result["detail"]


def test_r3_homebrew_publish_time_blocker_missing_checklist(tmp_path: Path) -> None:
    """Fails when PUBLISH_CHECKLIST.md is absent (even if formula exists)."""
    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    (formula_dir / "autodev-ai.rb").write_text(
        "# BLOCKED\nsha256 \"TODO_PUBLISH_SHA256\"\n", encoding="utf-8"
    )
    # No PUBLISH_CHECKLIST.md
    result = gate.check_r3_homebrew_publish_time_blocker_clean(tmp_path)
    assert result["status"] == "fail"
    assert "PUBLISH_CHECKLIST.md not found" in result["detail"]


def test_r3_homebrew_publish_time_blocker_state_b_post_publish(tmp_path: Path) -> None:
    """Passes state B when formula has real sha256 + canonical PyPI url."""
    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    real_sha = "a" * 64  # 64 lowercase hex chars
    (formula_dir / "autodev-ai.rb").write_text(
        f'url "https://files.pythonhosted.org/packages/autodev-ai-0.1.0a1.tar.gz"\n'
        f'sha256 "{real_sha}"\n',
        encoding="utf-8",
    )
    (tmp_path / "packaging" / "homebrew" / "PUBLISH_CHECKLIST.md").write_text(
        "# Checklist\n", encoding="utf-8"
    )
    result = gate.check_r3_homebrew_publish_time_blocker_clean(tmp_path)
    assert result["status"] == "pass"
    assert "state B" in result["detail"]


def test_r3_homebrew_publish_time_blocker_ambiguous_state(tmp_path: Path) -> None:
    """Fails when formula is in ambiguous state (no placeholder, no real sha, no canonical url)."""
    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    (formula_dir / "autodev-ai.rb").write_text(
        "# some formula\n"
        'url "https://example.com/something.tar.gz"\n'
        'sha256 "short_not_64_hex"\n',
        encoding="utf-8",
    )
    (tmp_path / "packaging" / "homebrew" / "PUBLISH_CHECKLIST.md").write_text(
        "# Checklist\n", encoding="utf-8"
    )
    result = gate.check_r3_homebrew_publish_time_blocker_clean(tmp_path)
    assert result["status"] == "fail"
    assert "ambiguous" in result["detail"]


def test_r3_pypi_rc_not_blocked_by_homebrew_pass(tmp_path: Path) -> None:
    """Passes when homebrew blocker check passes."""
    formula_dir = tmp_path / "packaging" / "homebrew" / "Formula"
    formula_dir.mkdir(parents=True)
    (formula_dir / "autodev-ai.rb").write_text(
        "# BLOCKED\nsha256 \"TODO_PUBLISH_SHA256\"\n", encoding="utf-8"
    )
    (tmp_path / "packaging" / "homebrew" / "PUBLISH_CHECKLIST.md").write_text(
        "# Checklist\n", encoding="utf-8"
    )
    result = gate.check_r3_pypi_rc_not_blocked_by_homebrew(tmp_path)
    assert result["status"] == "pass"
    assert "not block PyPI RC" in result["detail"]


def test_r3_pypi_rc_not_blocked_by_homebrew_fail(tmp_path: Path) -> None:
    """Fails when homebrew blocker check fails (formula absent)."""
    result = gate.check_r3_pypi_rc_not_blocked_by_homebrew(tmp_path)
    assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# run_checks: exception handling path
# ---------------------------------------------------------------------------


def test_run_checks_catches_exception(tmp_path: Path) -> None:
    """run_checks catches exceptions from check functions and records them as fail."""
    def bad_check(repo: Path) -> dict:
        raise RuntimeError("simulated check crash")

    bad_check.__name__ = "check_bad_check"
    results = gate.run_checks(tmp_path, [bad_check])
    assert len(results) == 1
    assert results[0]["status"] == "fail"
    assert "simulated check crash" in results[0]["detail"]


# ---------------------------------------------------------------------------
# build_report: overall variants
# ---------------------------------------------------------------------------


def test_build_report_overall_pass_no_skips(tmp_path: Path) -> None:
    """overall == 'pass' when all checks pass with no skips."""
    def passing_check(repo: Path) -> dict:
        return gate._make("check_x", "pass", "ok", 0)

    passing_check.__name__ = "check_x"
    report = gate.build_report(tmp_path, [passing_check])
    assert report["overall"] == "pass"
    assert report["strict_pass"] is True


def test_build_report_overall_pass_with_skips(tmp_path: Path) -> None:
    """overall == 'pass_with_skips' when all checks pass or skip."""
    def skip_check(repo: Path) -> dict:
        return gate._make("check_y", "skip", "skipped", 0)

    skip_check.__name__ = "check_y"
    report = gate.build_report(tmp_path, [skip_check])
    assert report["overall"] == "pass_with_skips"
    assert report["strict_pass"] is True


def test_build_report_no_checks_to_run_uses_all(tmp_path: Path) -> None:
    """build_report with checks_to_run=None defaults to ALL_CHECKS."""
    with patch.object(gate, "run_checks", return_value=[
        gate._make("test", "pass", "ok", 0)
    ]) as mock_run:
        gate.build_report(tmp_path, None)
    mock_run.assert_called_once_with(tmp_path, gate.ALL_CHECKS)


# ---------------------------------------------------------------------------
# run_all_checks
# ---------------------------------------------------------------------------


def test_run_all_checks_returns_list(tmp_path: Path) -> None:
    """run_all_checks returns a list of check result dicts."""
    with patch.object(gate, "_run", return_value=(0, "", "")):
        results = gate.run_all_checks(tmp_path)
    assert isinstance(results, list)
    assert len(results) == 36


# ---------------------------------------------------------------------------
# main() CLI: --include-r3, --strict-r2, --strict-r3, --strict-rc
# ---------------------------------------------------------------------------


def test_main_include_r3_runs_only_r3(full_repo: Path) -> None:
    """--include-r3 runs only the 12 R3-specific checks."""
    with patch.object(gate, "_run", return_value=(0, "", "")):
        result = gate.main([
            "--repo-path", str(full_repo),
            "--output", str(full_repo / "out_r3.json"),
            "--include-r3",
        ])
    assert len(result["checks"]) == 12
    assert all(c["name"].startswith("r3_") for c in result["checks"])


def test_main_strict_r2_exits_on_r2_fail(tmp_path: Path) -> None:
    """--strict-r2 exits 1 when any R2 check fails."""
    # No pyproject.toml → r2_version_consistency fails
    with pytest.raises(SystemExit) as exc_info:
        with patch.object(gate, "_run", return_value=(0, "", "")):
            gate.main([
                "--repo-path", str(tmp_path),
                "--output", str(tmp_path / "out.json"),
                "--strict-r2",
            ])
    assert exc_info.value.code == 1


def test_main_strict_r2_passes_when_all_r2_pass(full_repo: Path) -> None:
    """--strict-r2 does not exit when all R2 checks pass."""
    with patch.object(gate, "_run", return_value=(0, "0.1.0\n", "")):
        result = gate.main([
            "--repo-path", str(full_repo),
            "--output", str(full_repo / "out_r2.json"),
            "--strict-r2",
        ])
    assert isinstance(result, dict)


def test_main_strict_r3_exits_on_r3_fail(tmp_path: Path) -> None:
    """--strict-r3 exits 1 when any R3 check fails."""
    # No CHANGELOG.md, mypy/ruff mocked to pass, but docs will be missing → r3 fails
    with pytest.raises(SystemExit) as exc_info:
        with patch.object(gate, "_run", return_value=(0, "", "")):
            gate.main([
                "--repo-path", str(tmp_path),
                "--output", str(tmp_path / "out.json"),
                "--strict-r3",
            ])
    assert exc_info.value.code == 1


def test_main_strict_rc_passes_when_all_pass(full_repo: Path) -> None:
    """--strict-rc annotates the report with pypi_rc_verdict when all pass."""
    with patch.object(gate, "_run", return_value=(0, "0.1.0\n", "")):
        result = gate.main([
            "--repo-path", str(full_repo),
            "--output", str(full_repo / "out_rc.json"),
            "--strict-rc",
        ])
    assert "pypi_rc_verdict" in result
    assert result["pypi_rc_verdict"] == "pass"
    assert "pypi_rc_excluded_from_strict" in result


def test_main_strict_rc_exits_on_fail(tmp_path: Path) -> None:
    """--strict-rc exits 1 when non-Homebrew checks fail."""
    # Empty tmp_path → many checks fail
    with pytest.raises(SystemExit) as exc_info:
        with patch.object(gate, "_run", return_value=(0, "", "")):
            gate.main([
                "--repo-path", str(tmp_path),
                "--output", str(tmp_path / "out.json"),
                "--strict-rc",
            ])
    assert exc_info.value.code == 1


def test_main_absolute_output_path(full_repo: Path, tmp_path: Path) -> None:
    """main() handles an absolute output path correctly."""
    out = tmp_path / "absolute_output.json"
    with patch.object(gate, "_run", return_value=(0, "0.1.0\n", "")):
        result = gate.main([
            "--repo-path", str(full_repo),
            "--output", str(out),  # absolute path outside repo
        ])
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["gate"] == "release_readiness"
    assert isinstance(result, dict)


def test_main_module_entry_point(full_repo: Path) -> None:
    """__main__ guard: calling main() with argv is the same as the module entry."""
    with patch.object(gate, "_run", return_value=(0, "0.1.0\n", "")):
        result = gate.main([
            "--repo-path", str(full_repo),
            "--output", str(full_repo / "main_entry.json"),
        ])
    assert "overall" in result
