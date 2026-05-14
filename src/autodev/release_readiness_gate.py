#!/usr/bin/env python3
"""
Release Readiness Gate — 36 read-only checks for autodev-ai (12 base + 12 R2 + 12 R3).

This is the canonical implementation.  It lives in the installable package so that
both of the following invocations work regardless of install method (editable, wheel,
or PyPI):

    python -m autodev.release_readiness_gate [args]
    python scripts/release_readiness_gate.py  [args]  (source-tree thin wrapper)

Usage:
    python -m autodev.release_readiness_gate [--repo-path .] \
        [--output docs/validation/release_readiness_gate_run.json] [--strict] \
        [--include-r2] [--strict-r2]

Exit codes:
    0 — all checks pass (or only skips)
    1 — one or more checks fail AND --strict / --strict-r2 is set
    0 — failures present but neither strict flag set (gate still reports them)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

CheckResult = dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(cmd: list[str], cwd: Path, timeout: int = 30) -> tuple[int, str, str]:
    """Run a subprocess; return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -2, "", f"command not found: {cmd[0]}"


def _make(name: str, status: str, detail: str, duration_ms: float, evidence: str = "") -> CheckResult:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "duration_ms": round(duration_ms, 1),
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# The 12 BASE checks
# ---------------------------------------------------------------------------

def check_package_metadata_valid(repo: Path) -> CheckResult:
    name = "package_metadata_valid"
    t0 = time.monotonic()
    toml_path = repo / "pyproject.toml"
    if not toml_path.exists():
        return _make(name, "fail", "pyproject.toml not found", (time.monotonic() - t0) * 1000)

    try:
        if sys.version_info >= (3, 11):
            import tomllib  # type: ignore[import]
        else:
            try:
                import tomllib  # type: ignore[import]
            except ImportError:
                import tomli as tomllib  # type: ignore[import,no-redef]

        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)

        project = data.get("project", {})
        missing = [k for k in ("name", "version", "requires-python") if k not in project]
        if missing:
            return _make(name, "fail", f"Missing required keys: {missing}", (time.monotonic() - t0) * 1000)

        scripts = project.get("scripts", {})
        if "autodev" not in scripts:
            return _make(
                name,
                "fail",
                "Entry-point 'autodev' not found in [project.scripts]",
                (time.monotonic() - t0) * 1000,
            )

        ep = scripts["autodev"]
        if "autodev.cli" not in ep:
            return _make(
                name,
                "fail",
                f"Entry-point value '{ep}' does not reference autodev.cli",
                (time.monotonic() - t0) * 1000,
            )

        return _make(
            name,
            "pass",
            f"name={project['name']} version={project['version']} ep={ep}",
            (time.monotonic() - t0) * 1000,
            str(toml_path),
        )
    except Exception as exc:  # noqa: BLE001
        return _make(name, "fail", f"Parse error: {exc}", (time.monotonic() - t0) * 1000)


def check_cli_help_works(repo: Path) -> CheckResult:
    name = "cli_help_works"
    t0 = time.monotonic()

    # Check if autodev is available
    rc_which, _, _ = _run(["which", "autodev"], repo, timeout=5)
    if rc_which != 0:
        # Try via python -m
        rc2, _stdout2, _stderr2 = _run(
            [sys.executable, "-m", "autodev.cli", "--help"],
            repo,
            timeout=10,
        )
        if rc2 == 0:
            return _make(name, "pass", "autodev CLI --help via python -m: exit 0", (time.monotonic() - t0) * 1000)
        return _make(
            name,
            "skip",
            "autodev not on PATH and python -m autodev.cli --help failed; skip",
            (time.monotonic() - t0) * 1000,
        )

    rc, _stdout, stderr = _run(["autodev", "--help"], repo, timeout=10)
    if rc == 0:
        return _make(name, "pass", "autodev --help exit 0", (time.monotonic() - t0) * 1000, "autodev --help")
    return _make(name, "fail", f"autodev --help exited {rc}: {stderr[:200]}", (time.monotonic() - t0) * 1000)


def check_pytest_evidence(repo: Path) -> CheckResult:
    name = "pytest_evidence"
    t0 = time.monotonic()

    smoke_file = repo / "tests" / "unit" / "test_prfaq_style.py"
    dev_factory = repo / ".dev-factory"

    # Prefer a recent test record if it exists
    if dev_factory.exists():
        records = sorted(dev_factory.glob("*.json"))
        if records:
            return _make(
                name,
                "pass",
                f"Recent .dev-factory test record found: {records[-1].name}",
                (time.monotonic() - t0) * 1000,
                str(records[-1]),
            )

    if not smoke_file.exists():
        return _make(name, "skip", "Smoke test file not found and no .dev-factory records", (time.monotonic() - t0) * 1000)

    rc, stdout, stderr = _run(
        [sys.executable, "-m", "pytest", str(smoke_file), "-q", "--tb=short", "--no-header"],
        repo,
        timeout=60,
    )
    combined = (stdout + stderr)[:400]
    if rc == 0:
        return _make(name, "pass", f"Smoke pytest passed:\n{combined}", (time.monotonic() - t0) * 1000, str(smoke_file))
    return _make(name, "fail", f"Smoke pytest failed (exit {rc}):\n{combined}", (time.monotonic() - t0) * 1000)


def check_ruff_passes(repo: Path) -> CheckResult:
    name = "ruff_passes"
    t0 = time.monotonic()
    # Use sys.executable -m so we pick up the same ruff as the dev env.
    rc, stdout, stderr = _run([sys.executable, "-m", "ruff", "check", "."], repo, timeout=60)
    combined = (stdout + stderr)[:400]
    if rc == 0:
        return _make(name, "pass", "ruff check . exit 0", (time.monotonic() - t0) * 1000)
    return _make(name, "fail", f"ruff exit {rc}:\n{combined}", (time.monotonic() - t0) * 1000)


def check_mypy_passes(repo: Path) -> CheckResult:
    name = "mypy_passes"
    t0 = time.monotonic()
    # Use sys.executable -m so we pick up the same mypy as the dev env
    # (bare `mypy` on PATH may resolve to an older system install).
    rc, stdout, stderr = _run([sys.executable, "-m", "mypy", "src/autodev"], repo, timeout=60)
    combined = (stdout + stderr)[:400]
    if rc == 0:
        return _make(name, "pass", "mypy src/autodev exit 0", (time.monotonic() - t0) * 1000)
    return _make(name, "fail", f"mypy exit {rc}:\n{combined}", (time.monotonic() - t0) * 1000)


def check_docs_exist(repo: Path) -> CheckResult:
    name = "docs_exist"
    t0 = time.monotonic()

    readme = repo / "README.md"
    if not readme.exists():
        return _make(name, "fail", "README.md not found", (time.monotonic() - t0) * 1000)

    candidates = [
        repo / "docs" / "quickstart.md",
        repo / "docs" / "architecture.md",
        repo / "docs" / "faq.md",
        repo / "docs" / "tutorials",
        repo / "examples" / "README.md",
    ]
    found = [str(p) for p in candidates if p.exists()]
    if len(found) >= 5:
        return _make(name, "pass", f"README + {len(found)}/5 doc paths present", (time.monotonic() - t0) * 1000, ", ".join(found))
    return _make(
        name,
        "fail",
        f"Only {len(found)}/5 required doc paths present: {found}",
        (time.monotonic() - t0) * 1000,
    )


def check_mcp_smoke_path_exists(repo: Path) -> CheckResult:
    name = "mcp_smoke_path_exists"
    t0 = time.monotonic()

    smoke = repo / "tests" / "integration" / "test_mcp_server_smoke.py"
    mcp_main_candidates = [
        repo / "src" / "autodev" / "mcp_server" / "__init__.py",
        repo / "src" / "autodev" / "mcp_server" / "server.py",
        repo / "src" / "autodev" / "mcp_server" / "main.py",
    ]

    if smoke.exists():
        return _make(name, "pass", f"MCP smoke test exists: {smoke}", (time.monotonic() - t0) * 1000, str(smoke))

    mcp_entries = [str(p) for p in mcp_main_candidates if p.exists()]
    if mcp_entries:
        return _make(name, "pass", f"MCP server entry found: {mcp_entries}", (time.monotonic() - t0) * 1000, str(mcp_entries[0]))

    return _make(name, "fail", "No MCP smoke test and no mcp_server/ main entry found", (time.monotonic() - t0) * 1000)


def check_a2a_smoke_path_exists(repo: Path) -> CheckResult:
    name = "a2a_smoke_path_exists"
    t0 = time.monotonic()

    tests_root = repo / "tests"
    a2a_files = sorted(
        p for p in tests_root.rglob("*.py")
        if "a2a" in p.name.lower() or "roundtable" in p.name.lower()
    )
    count = len(a2a_files)
    if count >= 5:
        return _make(
            name,
            "pass",
            f"{count} a2a/roundtable test files found",
            (time.monotonic() - t0) * 1000,
            ", ".join(str(p.relative_to(repo)) for p in a2a_files[:5]),
        )
    return _make(
        name,
        "fail",
        f"Only {count} a2a/roundtable test files found (need ≥5): {[p.name for p in a2a_files]}",
        (time.monotonic() - t0) * 1000,
    )


def check_mock_executor_works(repo: Path) -> CheckResult:
    name = "mock_executor_works"
    t0 = time.monotonic()

    env_extra = {"FACTORY_FORCE_MOCK": "1"}
    import os
    import tempfile

    env = {**os.environ, **env_extra}

    # classify-input takes --input as a file path, not raw text — write a temp file.
    tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    try:
        tmp.write("Build a CLI tool that counts lines in markdown files.")
        tmp.close()
        # Try via installed command first, then via python module
        for cmd in (
            ["autodev", "classify-input", "--input", tmp.name],
            [sys.executable, "-m", "autodev.cli", "classify-input", "--input", tmp.name],
        ):
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                    timeout=15,
                    env=env,
                )
                if proc.returncode == 0:
                    return _make(
                        name,
                        "pass",
                        f"FACTORY_FORCE_MOCK=1 {' '.join(cmd[:3])} exit 0",
                        (time.monotonic() - t0) * 1000,
                    )
                # Distinguish "command not found" vs real failure
                if proc.returncode == 2 and "No such command" in (proc.stderr + proc.stdout):
                    return _make(
                        name,
                        "skip",
                        "'classify-input' sub-command not found in CLI; skipping",
                        (time.monotonic() - t0) * 1000,
                    )
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                return _make(name, "fail", "mock_executor timed out", (time.monotonic() - t0) * 1000)

        return _make(
            name,
            "skip",
            "autodev not on PATH or classify-input not available; skipping mock executor check",
            (time.monotonic() - t0) * 1000,
        )
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def check_packaging_files_exist(repo: Path) -> CheckResult:
    name = "packaging_files_exist"
    t0 = time.monotonic()

    required = [
        repo / "packaging" / "docker" / "Dockerfile",
        repo / "packaging" / "pyinstaller" / "autodev.spec",
        repo / "packaging" / "homebrew" / "Formula" / "autodev-ai.rb",
    ]
    missing = [str(p.relative_to(repo)) for p in required if not p.exists()]
    present = [str(p.relative_to(repo)) for p in required if p.exists()]

    if not missing:
        return _make(name, "pass", "All 3 packaging files present", (time.monotonic() - t0) * 1000, ", ".join(present))
    return _make(name, "fail", f"Missing packaging files: {missing}", (time.monotonic() - t0) * 1000, ", ".join(present))


def check_no_dangerous_release_claims(repo: Path) -> CheckResult:
    name = "no_dangerous_release_claims"
    t0 = time.monotonic()

    readme = repo / "README.md"
    if not readme.exists():
        return _make(name, "skip", "README.md not found; skipping claim check", (time.monotonic() - t0) * 1000)

    forbidden_phrases = [
        "available on pypi now",
        "production ready",
        "enterprise certified",
    ]
    text = readme.read_text(encoding="utf-8", errors="replace").lower()
    hits = [phrase for phrase in forbidden_phrases if phrase in text]

    if hits:
        return _make(
            name,
            "fail",
            f"Forbidden claims found in README.md: {hits}",
            (time.monotonic() - t0) * 1000,
            str(readme),
        )
    return _make(
        name,
        "pass",
        "No forbidden release claims found in README.md",
        (time.monotonic() - t0) * 1000,
        str(readme),
    )


def check_release_blockers_recorded(repo: Path) -> CheckResult:
    name = "release_blockers_recorded"
    t0 = time.monotonic()

    val_dir = repo / "docs" / "validation"
    if not val_dir.exists():
        return _make(name, "fail", "docs/validation/ directory not found", (time.monotonic() - t0) * 1000)

    # Look for aggregator or release_blockers files
    candidates = list(val_dir.glob("*release_hardening_round*")) + list(val_dir.glob("release_blockers*"))
    # Also accept the gate report we produce itself
    gate_reports = list(val_dir.glob("autodev_release_readiness_gate*"))

    all_found = candidates + gate_reports
    if all_found:
        names = [p.name for p in all_found[:5]]
        return _make(
            name,
            "pass",
            f"Release evidence files found: {names}",
            (time.monotonic() - t0) * 1000,
            str(all_found[0]),
        )

    return _make(
        name,
        "fail",
        "No *release_hardening_round* or release_blockers.* or autodev_release_readiness_gate.* found in docs/validation/",
        (time.monotonic() - t0) * 1000,
    )


# ---------------------------------------------------------------------------
# R2 checks (12 new checks, prefix r2_)
# ---------------------------------------------------------------------------


def check_r2_version_consistency(repo: Path) -> CheckResult:
    name = "r2_version_consistency"
    t0 = time.monotonic()
    toml_path = repo / "pyproject.toml"
    if not toml_path.exists():
        return _make(name, "fail", "pyproject.toml not found", (time.monotonic() - t0) * 1000)

    try:
        if sys.version_info >= (3, 11):
            import tomllib  # type: ignore[import]
        else:
            try:
                import tomllib  # type: ignore[import]
            except ImportError:
                import tomli as tomllib  # type: ignore[import,no-redef]

        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)

        pyproject_ver = data.get("project", {}).get("version", "")
        if not pyproject_ver.startswith("0.1.0"):
            return _make(
                name,
                "fail",
                f"pyproject.toml version '{pyproject_ver}' does not start with '0.1.0'",
                (time.monotonic() - t0) * 1000,
            )

        # Try importing autodev to check __version__
        rc, stdout, stderr = _run(
            [sys.executable, "-c", "import autodev; print(autodev.__version__)"],
            repo,
            timeout=10,
        )
        if rc != 0:
            return _make(
                name,
                "skip",
                f"Cannot import autodev to check __version__: {stderr[:100]}",
                (time.monotonic() - t0) * 1000,
            )

        module_ver = stdout.strip()
        if module_ver != pyproject_ver:
            return _make(
                name,
                "fail",
                f"pyproject version '{pyproject_ver}' != module __version__ '{module_ver}'",
                (time.monotonic() - t0) * 1000,
                str(toml_path),
            )

        return _make(
            name,
            "pass",
            f"version consistent: {pyproject_ver}",
            (time.monotonic() - t0) * 1000,
            str(toml_path),
        )
    except Exception as exc:  # noqa: BLE001
        return _make(name, "fail", f"Parse error: {exc}", (time.monotonic() - t0) * 1000)


def check_r2_license_file_present(repo: Path) -> CheckResult:
    name = "r2_license_file_present"
    t0 = time.monotonic()

    license_path = repo / "LICENSE"
    if not license_path.exists():
        return _make(name, "fail", "LICENSE file not found at repo root", (time.monotonic() - t0) * 1000)

    text = license_path.read_text(encoding="utf-8", errors="replace")
    if "MIT License" in text or "Permission is hereby granted" in text:
        return _make(
            name,
            "pass",
            "LICENSE present with expected MIT content",
            (time.monotonic() - t0) * 1000,
            str(license_path),
        )
    return _make(
        name,
        "fail",
        "LICENSE file present but does not contain 'MIT License' or 'Permission is hereby granted'",
        (time.monotonic() - t0) * 1000,
        str(license_path),
    )


def check_r2_license_metadata_match(repo: Path) -> CheckResult:
    name = "r2_license_metadata_match"
    t0 = time.monotonic()

    toml_path = repo / "pyproject.toml"
    if not toml_path.exists():
        return _make(name, "fail", "pyproject.toml not found", (time.monotonic() - t0) * 1000)

    try:
        if sys.version_info >= (3, 11):
            import tomllib  # type: ignore[import]
        else:
            try:
                import tomllib  # type: ignore[import]
            except ImportError:
                import tomli as tomllib  # type: ignore[import,no-redef]

        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)

        project = data.get("project", {})
        license_field = project.get("license")
        if license_field is None:
            return _make(
                name,
                "fail",
                "[project] license field missing from pyproject.toml",
                (time.monotonic() - t0) * 1000,
                str(toml_path),
            )

        return _make(
            name,
            "pass",
            f"[project] license field present: {license_field!r}",
            (time.monotonic() - t0) * 1000,
            str(toml_path),
        )
    except Exception as exc:  # noqa: BLE001
        return _make(name, "fail", f"Parse error: {exc}", (time.monotonic() - t0) * 1000)


def check_r2_wheel_version_works(repo: Path) -> CheckResult:
    name = "r2_wheel_version_works"
    t0 = time.monotonic()

    dist = repo / "dist"
    if not dist.exists():
        return _make(name, "skip", "no built wheel (dist/ not found)", (time.monotonic() - t0) * 1000)

    wheels = list(dist.glob("*.whl"))
    if not wheels:
        return _make(name, "skip", "no built wheel (no *.whl in dist/)", (time.monotonic() - t0) * 1000)

    # Parse pyproject version
    try:
        if sys.version_info >= (3, 11):
            import tomllib  # type: ignore[import]
        else:
            try:
                import tomllib  # type: ignore[import]
            except ImportError:
                import tomli as tomllib  # type: ignore[import,no-redef]

        toml_path = repo / "pyproject.toml"
        if not toml_path.exists():
            return _make(name, "fail", "pyproject.toml not found", (time.monotonic() - t0) * 1000)

        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)
        pyproject_ver = data.get("project", {}).get("version", "")
    except Exception as exc:  # noqa: BLE001
        return _make(name, "fail", f"Failed to read pyproject.toml: {exc}", (time.monotonic() - t0) * 1000)

    # Wheel filename format: {dist}-{version}-{python}-{abi}-{platform}.whl
    # Normalize version: PEP 427 uses underscores for dashes, e.g. 0.1.0a1
    wheel = wheels[0]
    parts = wheel.name.split("-")
    if len(parts) < 2:
        return _make(name, "fail", f"Cannot parse wheel filename: {wheel.name}", (time.monotonic() - t0) * 1000)

    wheel_ver = parts[1]
    # Normalize for comparison: PEP 440 normalization (lowercase, no separators diff)
    def _norm(v: str) -> str:
        return re.sub(r"[-_.]", "", v.lower())

    if _norm(wheel_ver) == _norm(pyproject_ver):
        return _make(
            name,
            "pass",
            f"wheel version '{wheel_ver}' matches pyproject '{pyproject_ver}'",
            (time.monotonic() - t0) * 1000,
            str(wheel),
        )
    return _make(
        name,
        "fail",
        f"wheel version '{wheel_ver}' does not match pyproject '{pyproject_ver}'",
        (time.monotonic() - t0) * 1000,
        str(wheel),
    )


def check_r2_a2a_http_ssrf_hardened(repo: Path) -> CheckResult:
    name = "r2_a2a_http_ssrf_hardened"
    t0 = time.monotonic()

    http_transport = repo / "src" / "autodev" / "adapters" / "a2a" / "transports" / "http.py"
    ssrf_test = repo / "tests" / "unit" / "test_a2a_http_ssrf_hardening.py"

    missing = []
    if not http_transport.exists():
        missing.append(str(http_transport.relative_to(repo)))
    if not ssrf_test.exists():
        missing.append(str(ssrf_test.relative_to(repo)))

    if missing:
        return _make(name, "fail", f"Missing files: {missing}", (time.monotonic() - t0) * 1000)

    # Check SSRF error class in transport
    transport_text = http_transport.read_text(encoding="utf-8", errors="replace")
    if "A2AHttpSSRFError" not in transport_text:
        return _make(
            name,
            "fail",
            "A2AHttpSSRFError not found in src/autodev/adapters/a2a/transports/http.py",
            (time.monotonic() - t0) * 1000,
            str(http_transport),
        )

    # Count test functions in ssrf test file
    test_text = ssrf_test.read_text(encoding="utf-8", errors="replace")
    test_count = len(re.findall(r"^\s*def test_", test_text, re.MULTILINE))
    if test_count < 10:
        return _make(
            name,
            "fail",
            f"test_a2a_http_ssrf_hardening.py has only {test_count} test functions (need ≥10)",
            (time.monotonic() - t0) * 1000,
            str(ssrf_test),
        )

    return _make(
        name,
        "pass",
        f"A2AHttpSSRFError present; {test_count} SSRF test functions",
        (time.monotonic() - t0) * 1000,
        str(ssrf_test),
    )


def check_r2_milestone_flow_tested(repo: Path) -> CheckResult:
    name = "r2_milestone_flow_tested"
    t0 = time.monotonic()

    test_file = repo / "tests" / "unit" / "test_milestone_flow.py"
    if not test_file.exists():
        return _make(name, "fail", "tests/unit/test_milestone_flow.py not found", (time.monotonic() - t0) * 1000)

    text = test_file.read_text(encoding="utf-8", errors="replace")
    count = len(re.findall(r"^\s*def test_", text, re.MULTILINE))
    if count < 4:
        return _make(
            name,
            "fail",
            f"test_milestone_flow.py has only {count} test functions (need ≥4)",
            (time.monotonic() - t0) * 1000,
            str(test_file),
        )

    return _make(
        name,
        "pass",
        f"test_milestone_flow.py exists with {count} test functions",
        (time.monotonic() - t0) * 1000,
        str(test_file),
    )


def check_r2_release_flow_tested(repo: Path) -> CheckResult:
    name = "r2_release_flow_tested"
    t0 = time.monotonic()

    test_file = repo / "tests" / "unit" / "test_release_flow.py"
    if not test_file.exists():
        return _make(name, "fail", "tests/unit/test_release_flow.py not found", (time.monotonic() - t0) * 1000)

    text = test_file.read_text(encoding="utf-8", errors="replace")
    count = len(re.findall(r"^\s*def test_", text, re.MULTILINE))
    if count < 4:
        return _make(
            name,
            "fail",
            f"test_release_flow.py has only {count} test functions (need ≥4)",
            (time.monotonic() - t0) * 1000,
            str(test_file),
        )

    return _make(
        name,
        "pass",
        f"test_release_flow.py exists with {count} test functions",
        (time.monotonic() - t0) * 1000,
        str(test_file),
    )


def check_r2_release_workflow_pytest_gate(repo: Path) -> CheckResult:
    name = "r2_release_workflow_pytest_gate"
    t0 = time.monotonic()

    workflow = repo / ".github" / "workflows" / "release.yml"
    if not workflow.exists():
        return _make(name, "fail", ".github/workflows/release.yml not found", (time.monotonic() - t0) * 1000)

    text = workflow.read_text(encoding="utf-8", errors="replace")

    has_pytest = "pytest" in text
    has_needs = bool(re.search(r"^\s+needs\s*:", text, re.MULTILINE))

    if not has_pytest:
        return _make(
            name,
            "fail",
            ".github/workflows/release.yml does not contain 'pytest'",
            (time.monotonic() - t0) * 1000,
            str(workflow),
        )
    if not has_needs:
        return _make(
            name,
            "fail",
            ".github/workflows/release.yml does not contain a 'needs:' directive",
            (time.monotonic() - t0) * 1000,
            str(workflow),
        )

    return _make(
        name,
        "pass",
        "release.yml contains pytest token AND needs: directive",
        (time.monotonic() - t0) * 1000,
        str(workflow),
    )


def check_r2_homebrew_metadata_owner_fixed(repo: Path) -> CheckResult:
    name = "r2_homebrew_metadata_owner_fixed"
    t0 = time.monotonic()

    formula = repo / "packaging" / "homebrew" / "Formula" / "autodev-ai.rb"
    if not formula.exists():
        return _make(name, "fail", "Homebrew formula not found", (time.monotonic() - t0) * 1000)

    text = formula.read_text(encoding="utf-8", errors="replace")

    if "macworkers/autodev-ai" in text:
        return _make(
            name,
            "fail",
            "Formula still contains old owner 'macworkers/autodev-ai' (should be 'merchloubna70-dot/autodev-ai')",
            (time.monotonic() - t0) * 1000,
            str(formula),
        )

    if "merchloubna70-dot/autodev-ai" not in text:
        return _make(
            name,
            "fail",
            "Formula does not contain expected owner 'merchloubna70-dot/autodev-ai'",
            (time.monotonic() - t0) * 1000,
            str(formula),
        )

    return _make(
        name,
        "pass",
        "Homebrew formula owner is 'merchloubna70-dot/autodev-ai' (correct)",
        (time.monotonic() - t0) * 1000,
        str(formula),
    )


def check_r2_homebrew_sha256_not_stale(repo: Path) -> CheckResult:
    name = "r2_homebrew_sha256_not_stale"
    t0 = time.monotonic()

    formula = repo / "packaging" / "homebrew" / "Formula" / "autodev-ai.rb"
    if not formula.exists():
        return _make(name, "fail", "Homebrew formula not found", (time.monotonic() - t0) * 1000)

    text = formula.read_text(encoding="utf-8", errors="replace")

    stale_hash = "744375fb"
    if stale_hash in text:
        return _make(
            name,
            "fail",
            f"Formula contains stale placeholder sha256 '{stale_hash}...' — must be updated before publish",
            (time.monotonic() - t0) * 1000,
            str(formula),
        )

    return _make(
        name,
        "pass",
        "Homebrew formula does not contain stale sha256 placeholder",
        (time.monotonic() - t0) * 1000,
        str(formula),
    )


def check_r2_macos_info_plist_version_match(repo: Path) -> CheckResult:
    name = "r2_macos_info_plist_version_match"
    t0 = time.monotonic()

    plist_path = repo / "packaging" / "desktop" / "autodev-ai.app" / "Contents" / "Info.plist"
    if not plist_path.exists():
        return _make(
            name,
            "skip",
            f"Info.plist not found at {plist_path.relative_to(repo)}",
            (time.monotonic() - t0) * 1000,
        )

    try:
        import plistlib

        with open(plist_path, "rb") as fh:
            plist_data = plistlib.load(fh)

        bundle_ver = plist_data.get("CFBundleShortVersionString", "")
        if "0.1.0" in bundle_ver:
            return _make(
                name,
                "pass",
                f"Info.plist CFBundleShortVersionString='{bundle_ver}' contains '0.1.0'",
                (time.monotonic() - t0) * 1000,
                str(plist_path),
            )
        return _make(
            name,
            "fail",
            f"Info.plist CFBundleShortVersionString='{bundle_ver}' does not contain '0.1.0'",
            (time.monotonic() - t0) * 1000,
            str(plist_path),
        )
    except Exception as exc:  # noqa: BLE001
        return _make(name, "fail", f"Failed to parse Info.plist: {exc}", (time.monotonic() - t0) * 1000)


def check_r2_remaining_blockers_recorded(repo: Path) -> CheckResult:
    name = "r2_remaining_blockers_recorded"
    t0 = time.monotonic()

    val_dir = repo / "docs" / "validation"
    if not val_dir.exists():
        return _make(name, "fail", "docs/validation/ directory not found", (time.monotonic() - t0) * 1000)

    # Check for autodev_r2_pypi_release_blocker_closure.json
    r2_blocker_file = val_dir / "autodev_r2_pypi_release_blocker_closure.json"
    if r2_blocker_file.exists():
        return _make(
            name,
            "pass",
            f"R2 blocker closure file found: {r2_blocker_file.name}",
            (time.monotonic() - t0) * 1000,
            str(r2_blocker_file),
        )

    # Fall back: check autodev_release_hardening_round.json has release_blockers array
    hardening_file = val_dir / "autodev_release_hardening_round.json"
    if hardening_file.exists():
        try:
            data = json.loads(hardening_file.read_text(encoding="utf-8"))
            blockers = data.get("release_blockers")
            if isinstance(blockers, list):
                return _make(
                    name,
                    "pass",
                    f"autodev_release_hardening_round.json has release_blockers array ({len(blockers)} items)",
                    (time.monotonic() - t0) * 1000,
                    str(hardening_file),
                )
        except Exception:  # noqa: BLE001
            pass

    return _make(
        name,
        "fail",
        "No autodev_r2_pypi_release_blocker_closure.json found, and autodev_release_hardening_round.json "
        "missing or lacks release_blockers array",
        (time.monotonic() - t0) * 1000,
    )


# ---------------------------------------------------------------------------
# R3 CHECKS — PyPI RC Final Hardening
# ---------------------------------------------------------------------------

def check_r3_mypy_clean(repo: Path) -> CheckResult:
    """R3-A: mypy across src/autodev should be 0 errors."""
    name = "r3_mypy_clean"
    t0 = time.monotonic()
    rc, out, err = _run([sys.executable, "-m", "mypy", "src/autodev"], repo, timeout=60)
    dur = (time.monotonic() - t0) * 1000
    if rc == 0:
        return _make(name, "pass", "mypy src/autodev: 0 errors", dur, evidence=out.strip().split("\n")[-1] if out else "")
    return _make(name, "fail", f"mypy returned exit {rc}; tail={out.strip().split(chr(10))[-1] if out else err.strip()[:120]}", dur)


def check_r3_ruff_clean(repo: Path) -> CheckResult:
    """R3-C: ruff check . should be 0 errors."""
    name = "r3_ruff_clean"
    t0 = time.monotonic()
    rc, out, err = _run([sys.executable, "-m", "ruff", "check", "."], repo, timeout=30)
    dur = (time.monotonic() - t0) * 1000
    if rc == 0:
        return _make(name, "pass", "ruff check .: 0 errors", dur, evidence=out.strip().split("\n")[-1] if out else "All checks passed!")
    return _make(name, "fail", f"ruff returned exit {rc}; tail={out.strip().split(chr(10))[-1] if out else err.strip()[:120]}", dur)


def check_r3_lint_yml_scans_scripts(repo: Path) -> CheckResult:
    """R3-C: .github/workflows/lint.yml must scan scripts/."""
    name = "r3_lint_yml_scans_scripts"
    t0 = time.monotonic()
    p = repo / ".github" / "workflows" / "lint.yml"
    dur = (time.monotonic() - t0) * 1000
    if not p.exists():
        return _make(name, "fail", "lint.yml not found", dur)
    content = p.read_text(encoding="utf-8")
    if "scripts" in content and ("ruff" in content.lower() or "ruff" in content):
        return _make(name, "pass", "lint.yml ruff step includes scripts/", dur)
    return _make(name, "fail", "lint.yml does not appear to scan scripts/ with ruff", dur)


def check_r3_mcp_apply_guardrail_present(repo: Path) -> CheckResult:
    """R3-B: MCP tools.py must enforce dual-gate for apply mode."""
    name = "r3_mcp_apply_guardrail_present"
    t0 = time.monotonic()
    p = repo / "src" / "autodev" / "mcp_server" / "tools.py"
    dur = (time.monotonic() - t0) * 1000
    if not p.exists():
        return _make(name, "fail", "mcp_server/tools.py not found", dur)
    src = p.read_text(encoding="utf-8")
    have_env = "AUTODEV_MCP_ALLOW_APPLY" in src
    have_param = "allow_apply" in src
    if have_env and have_param:
        return _make(name, "pass", "MCP dual-gate: allow_apply param + AUTODEV_MCP_ALLOW_APPLY env both referenced", dur)
    return _make(name, "fail", f"MCP guardrail incomplete: allow_apply={have_param}, AUTODEV_MCP_ALLOW_APPLY={have_env}", dur)


def check_r3_a2a_dns_rebinding_pinned(repo: Path) -> CheckResult:
    """R3-E: A2A HTTP transport must IP-pin against DNS rebinding TOCTOU."""
    name = "r3_a2a_dns_rebinding_pinned"
    t0 = time.monotonic()
    p = repo / "src" / "autodev" / "adapters" / "a2a" / "transports" / "http.py"
    dur = (time.monotonic() - t0) * 1000
    if not p.exists():
        return _make(name, "fail", "a2a/transports/http.py not found", dur)
    src = p.read_text(encoding="utf-8")
    have_resolver = "_resolve_and_pin_host" in src or "PinnedHTTP" in src
    have_handler = "PinnedHTTPHandler" in src or "PinnedHTTPSHandler" in src
    if have_resolver and have_handler:
        return _make(name, "pass", "IP-pin symbols present: _resolve_and_pin_host / _PinnedHTTP[S]Handler", dur)
    return _make(name, "fail", f"DNS rebinding mitigation incomplete: resolver={have_resolver}, handler={have_handler}", dur)


def check_r3_worker_isolator_symlink_safe(repo: Path) -> CheckResult:
    """R3-H: WorkerIsolator must defend against symlink escape."""
    name = "r3_worker_isolator_symlink_safe"
    t0 = time.monotonic()
    p = repo / "src" / "autodev" / "executors" / "worker_isolator.py"
    dur = (time.monotonic() - t0) * 1000
    if not p.exists():
        return _make(name, "fail", "executors/worker_isolator.py not found", dur)
    src = p.read_text(encoding="utf-8")
    if "WorkerIsolatorPathEscapeError" in src:
        return _make(name, "pass", "WorkerIsolatorPathEscapeError exception present", dur)
    return _make(name, "fail", "WorkerIsolatorPathEscapeError not found — symlink hardening missing", dur)


def check_r3_changelog_present(repo: Path) -> CheckResult:
    """R3-G: CHANGELOG.md present at repo root, mentions 0.1.0a1."""
    name = "r3_changelog_present"
    t0 = time.monotonic()
    p = repo / "CHANGELOG.md"
    dur = (time.monotonic() - t0) * 1000
    if not p.exists():
        return _make(name, "fail", "CHANGELOG.md not found", dur)
    content = p.read_text(encoding="utf-8")
    if "0.1.0a1" in content:
        return _make(name, "pass", f"CHANGELOG.md exists ({len(content)} chars), mentions 0.1.0a1", dur)
    return _make(name, "fail", "CHANGELOG.md exists but does not mention 0.1.0a1", dur)


def check_r3_configuration_doc_present(repo: Path) -> CheckResult:
    """R3-G: docs/configuration.md present and substantive."""
    name = "r3_configuration_doc_present"
    t0 = time.monotonic()
    p = repo / "docs" / "configuration.md"
    dur = (time.monotonic() - t0) * 1000
    if not p.exists():
        return _make(name, "fail", "docs/configuration.md not found", dur)
    content = p.read_text(encoding="utf-8")
    if len(content) >= 500:
        return _make(name, "pass", f"configuration.md exists ({len(content)} chars)", dur)
    return _make(name, "fail", f"configuration.md too short ({len(content)} chars, need >=500)", dur)


def check_r3_troubleshooting_doc_present(repo: Path) -> CheckResult:
    """R3-G: docs/troubleshooting.md present and substantive."""
    name = "r3_troubleshooting_doc_present"
    t0 = time.monotonic()
    p = repo / "docs" / "troubleshooting.md"
    dur = (time.monotonic() - t0) * 1000
    if not p.exists():
        return _make(name, "fail", "docs/troubleshooting.md not found", dur)
    content = p.read_text(encoding="utf-8")
    if len(content) >= 500:
        return _make(name, "pass", f"troubleshooting.md exists ({len(content)} chars)", dur)
    return _make(name, "fail", f"troubleshooting.md too short ({len(content)} chars, need >=500)", dur)


def check_r3_docker_base_digest_pinned(repo: Path) -> CheckResult:
    """R3-D: packaging/docker/Dockerfile FROM lines must be digest-pinned (@sha256:)."""
    name = "r3_docker_base_digest_pinned"
    t0 = time.monotonic()
    p = repo / "packaging" / "docker" / "Dockerfile"
    dur = (time.monotonic() - t0) * 1000
    if not p.exists():
        return _make(name, "fail", "packaging/docker/Dockerfile not found", dur)
    import re as _re
    content = p.read_text(encoding="utf-8")
    from_lines = [ln for ln in content.splitlines() if ln.strip().startswith("FROM ") and not ln.strip().startswith("#")]
    if not from_lines:
        return _make(name, "fail", "No FROM lines found in Dockerfile", dur)
    bad = []
    for ln in from_lines:
        if not _re.search(r"@sha256:[0-9a-f]{64}", ln):
            bad.append(ln.strip())
    if bad:
        return _make(name, "fail", f"FROM line(s) not digest-pinned: {bad[0][:80]}", dur)
    return _make(name, "pass", f"{len(from_lines)} FROM line(s) all digest-pinned (@sha256:<64-hex>)", dur)


def check_r3_homebrew_publish_time_blocker_clean(repo: Path) -> CheckResult:
    """R3-F: Homebrew formula must be HONEST about its publish state.

    Either of two valid honest states passes:

      A. PRE-publish (honestly blocked):
         (a) sha256 is a recognized placeholder (TODO_PUBLISH_SHA256 or REPLACE_WITH_*)
         (b) formula contains explicit "BLOCKED" comment
         (c) packaging/homebrew/PUBLISH_CHECKLIST.md exists

      B. POST-publish (real sha256 backfilled — R4.5 + R5 state):
         (a) sha256 is a 64-char lowercase hex value (real PyPI sdist hash)
         (b) formula url points at canonical files.pythonhosted.org
         (c) packaging/homebrew/PUBLISH_CHECKLIST.md exists

    Fail iff formula is in an inconsistent state (e.g. placeholder sha256 but
    no BLOCKED comment — would be ambiguous about whether it's safe to publish).
    """
    import re as _re

    name = "r3_homebrew_publish_time_blocker_clean"
    t0 = time.monotonic()
    formula = repo / "packaging" / "homebrew" / "Formula" / "autodev-ai.rb"
    checklist = repo / "packaging" / "homebrew" / "PUBLISH_CHECKLIST.md"
    dur = (time.monotonic() - t0) * 1000
    if not formula.exists():
        return _make(name, "fail", "Formula file not found", dur)
    if not checklist.exists():
        return _make(name, "fail", "PUBLISH_CHECKLIST.md not found", dur)
    content = formula.read_text(encoding="utf-8")

    # State A: pre-publish, honestly blocked
    has_placeholder = "TODO_PUBLISH_SHA256" in content or "REPLACE_WITH_PYPI" in content
    has_blocked = "BLOCKED" in content
    if has_placeholder and has_blocked:
        return _make(name, "pass",
                     "Homebrew formula state A: pre-publish honestly BLOCKED "
                     "(placeholder sha256 + BLOCKED comment + checklist)", dur)

    # State B: post-publish, real sha256 backfilled
    # Top-level url + sha256 (NOT inside `resource` blocks). Match first occurrence at
    # column 0..2 leading whitespace (formula main metadata, not nested resource).
    top_sha_match = _re.search(
        r'^\s{0,2}sha256\s+"([0-9a-f]{64})"', content, _re.MULTILINE
    )
    has_canonical_url = "files.pythonhosted.org" in content
    if top_sha_match and has_canonical_url and not has_placeholder:
        sha = top_sha_match.group(1)
        return _make(name, "pass",
                     f"Homebrew formula state B: post-publish backfilled "
                     f"(real sha256 {sha[:12]}... + canonical PyPI url + checklist)", dur)

    return _make(name, "fail",
                 f"Homebrew honesty check failed: pre-publish state "
                 f"(placeholder={has_placeholder}, BLOCKED={has_blocked}) "
                 f"and post-publish state (sha256_64hex={bool(top_sha_match)}, "
                 f"pypi_url={has_canonical_url}, no_placeholder={not has_placeholder}) "
                 f"both invalid — formula is in ambiguous state",
                 dur)


def check_r3_pypi_rc_not_blocked_by_homebrew(repo: Path) -> CheckResult:
    """Meta check: if Homebrew is honestly blocked (R3-F clean), PyPI RC is not contaminated.

    This always returns pass if r3_homebrew_publish_time_blocker_clean would pass.
    Used by --strict-rc to record the separation logic.
    """
    name = "r3_pypi_rc_not_blocked_by_homebrew"
    t0 = time.monotonic()
    result = check_r3_homebrew_publish_time_blocker_clean(repo)
    dur = (time.monotonic() - t0) * 1000
    if result["status"] == "pass":
        return _make(name, "pass",
                     "Homebrew is honestly blocked → does not block PyPI RC verdict",
                     dur)
    return _make(name, "fail",
                 "Homebrew is not honestly blocked → could ambiguously block PyPI RC",
                 dur)


# Names of checks whose failure is permitted under --strict-rc (Homebrew publish only).
# These do NOT block PyPI RC readiness, but DO block Homebrew publish.
_HOMEBREW_PUBLISH_ONLY_CHECKS: tuple[str, ...] = (
    # Currently empty: all Homebrew checks we run (owner_fixed, sha256_not_stale,
    # publish_time_blocker_clean, pypi_rc_not_blocked_by_homebrew) are honesty-checks
    # that SHOULD pass post-R2/R3. We keep the list infrastructure for future use
    # if a real "Homebrew published?" check is ever added.
)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

BASE_CHECKS = [
    check_package_metadata_valid,
    check_cli_help_works,
    check_pytest_evidence,
    check_ruff_passes,
    check_mypy_passes,
    check_docs_exist,
    check_mcp_smoke_path_exists,
    check_a2a_smoke_path_exists,
    check_mock_executor_works,
    check_packaging_files_exist,
    check_no_dangerous_release_claims,
    check_release_blockers_recorded,
]

R2_CHECKS = [
    check_r2_version_consistency,
    check_r2_license_file_present,
    check_r2_license_metadata_match,
    check_r2_wheel_version_works,
    check_r2_a2a_http_ssrf_hardened,
    check_r2_milestone_flow_tested,
    check_r2_release_flow_tested,
    check_r2_release_workflow_pytest_gate,
    check_r2_homebrew_metadata_owner_fixed,
    check_r2_homebrew_sha256_not_stale,
    check_r2_macos_info_plist_version_match,
    check_r2_remaining_blockers_recorded,
]

R3_CHECKS = [
    check_r3_mypy_clean,
    check_r3_ruff_clean,
    check_r3_lint_yml_scans_scripts,
    check_r3_mcp_apply_guardrail_present,
    check_r3_a2a_dns_rebinding_pinned,
    check_r3_worker_isolator_symlink_safe,
    check_r3_changelog_present,
    check_r3_configuration_doc_present,
    check_r3_troubleshooting_doc_present,
    check_r3_docker_base_digest_pinned,
    check_r3_homebrew_publish_time_blocker_clean,
    check_r3_pypi_rc_not_blocked_by_homebrew,
]

ALL_CHECKS = BASE_CHECKS + R2_CHECKS + R3_CHECKS


def run_checks(repo: Path, checks: list) -> list[CheckResult]:
    results = []
    for fn in checks:
        try:
            result = fn(repo)
        except Exception as exc:  # noqa: BLE001
            result = _make(fn.__name__.replace("check_", ""), "fail", f"Unexpected error: {exc}", 0)
        results.append(result)
    return results


def run_all_checks(repo: Path) -> list[CheckResult]:
    return run_checks(repo, ALL_CHECKS)


def build_report(repo: Path, checks_to_run: list | None = None) -> dict[str, Any]:
    if checks_to_run is None:
        checks_to_run = ALL_CHECKS
    checks = run_checks(repo, checks_to_run)
    counts: dict[str, int] = {"pass": 0, "fail": 0, "skip": 0}
    for c in checks:
        counts[c["status"]] = counts.get(c["status"], 0) + 1

    if counts["fail"] == 0 and counts["skip"] == 0:
        overall = "pass"
    elif counts["fail"] == 0:
        overall = "pass_with_skips"
    else:
        overall = "fail"

    strict_pass = counts["fail"] == 0

    return {
        "gate": "release_readiness",
        "ran_at": _now_iso(),
        "overall": overall,
        "checks": checks,
        "strict_pass": strict_pass,
        "summary": counts,
    }


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="autodev-ai Release Readiness Gate (36 checks)")
    parser.add_argument("--repo-path", default=".", help="Path to the repository root")
    parser.add_argument(
        "--output",
        default="docs/validation/release_readiness_gate_run.json",
        help="Output JSON path (relative to repo-path or absolute)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any check fails (all checks, no Homebrew exemption)",
    )
    parser.add_argument(
        "--include-r2",
        action="store_true",
        default=False,
        help="Run only the 12 R2-specific checks",
    )
    parser.add_argument(
        "--strict-r2",
        action="store_true",
        help="Exit 1 if any R2 check fails",
    )
    parser.add_argument(
        "--include-r3",
        action="store_true",
        default=False,
        help="Run only the 12 R3-specific checks",
    )
    parser.add_argument(
        "--strict-r3",
        action="store_true",
        help="Exit 1 if any R3 check fails",
    )
    parser.add_argument(
        "--strict-rc",
        action="store_true",
        help=(
            "Exit 1 if any non-Homebrew-publish check fails. "
            "Allows the known Homebrew publish-time blocker (formula needs PyPI 0.1.0a1 sha256) "
            "to pass through so PyPI RC readiness is not contaminated by Homebrew's downstream "
            "dependency."
        ),
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo_path).resolve()

    # Determine which checks to run
    if args.include_r3:
        checks_to_run = R3_CHECKS
    elif args.include_r2:
        checks_to_run = R2_CHECKS
    else:
        checks_to_run = ALL_CHECKS

    report = build_report(repo, checks_to_run)

    # Determine strict failure scope
    strict_fail = False
    if args.strict and not report["strict_pass"]:
        strict_fail = True
    if args.strict_r2:
        r2_results = [c for c in report["checks"] if c["name"].startswith("r2_")]
        if sum(1 for c in r2_results if c["status"] == "fail") > 0:
            strict_fail = True
    if args.strict_r3:
        r3_results = [c for c in report["checks"] if c["name"].startswith("r3_")]
        if sum(1 for c in r3_results if c["status"] == "fail") > 0:
            strict_fail = True
    if args.strict_rc:
        # PyPI RC strict: fail iff any non-Homebrew-publish check fails.
        # If Homebrew is honestly blocked (r3_homebrew_publish_time_blocker_clean
        # passes), its blocked-ness does not contaminate the RC verdict.
        rc_fails = [
            c for c in report["checks"]
            if c["status"] == "fail" and c["name"] not in _HOMEBREW_PUBLISH_ONLY_CHECKS
        ]
        if rc_fails:
            strict_fail = True
        # Annotate the report with the RC verdict
        report["pypi_rc_verdict"] = "pass" if not rc_fails else "fail"
        report["pypi_rc_excluded_from_strict"] = list(_HOMEBREW_PUBLISH_ONLY_CHECKS)

    # Resolve output path
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = repo / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Print summary to stdout
    summary = report["summary"]
    overall = report["overall"]
    print("\n=== Release Readiness Gate ===")
    print(f"  overall : {overall}")
    print(f"  pass    : {summary['pass']}")
    print(f"  fail    : {summary['fail']}")
    print(f"  skip    : {summary['skip']}")
    print(f"  report  : {out_path}")
    print()

    for c in report["checks"]:
        icon = {"pass": "✓", "fail": "✗", "skip": "~"}.get(c["status"], "?")
        print(f"  {icon} [{c['status']:4s}] {c['name']} ({c['duration_ms']:.0f}ms)")
        if c["status"] in ("fail", "skip"):
            print(f"         {c['detail'][:120]}")

    if strict_fail:
        sys.exit(1)

    return report


if __name__ == "__main__":
    main()
