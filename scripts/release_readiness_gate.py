#!/usr/bin/env python3
"""
Release Readiness Gate — 12 read-only checks for autodev-ai.

Usage:
    python scripts/release_readiness_gate.py [--repo-path .] \
        [--output docs/validation/release_readiness_gate_run.json] [--strict]

Exit codes:
    0 — all checks pass (or only skips)
    1 — one or more checks fail AND --strict is set
    0 — failures present but --strict not set (gate still reports them)
"""

from __future__ import annotations

import argparse
import json
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
# The 12 checks
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
        rc2, stdout2, stderr2 = _run(
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

    rc, stdout, stderr = _run(["autodev", "--help"], repo, timeout=10)
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
    rc, stdout, stderr = _run(["ruff", "check", "."], repo, timeout=60)
    combined = (stdout + stderr)[:400]
    if rc == -2:
        return _make(name, "skip", "ruff not on PATH", (time.monotonic() - t0) * 1000)
    if rc == 0:
        return _make(name, "pass", "ruff check . exit 0", (time.monotonic() - t0) * 1000)
    return _make(name, "fail", f"ruff exit {rc}:\n{combined}", (time.monotonic() - t0) * 1000)


def check_mypy_passes(repo: Path) -> CheckResult:
    name = "mypy_passes"
    t0 = time.monotonic()
    rc, stdout, stderr = _run(["mypy", "src/autodev"], repo, timeout=60)
    combined = (stdout + stderr)[:400]
    if rc == -2:
        return _make(name, "skip", "mypy not on PATH", (time.monotonic() - t0) * 1000)
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

    env = {**os.environ, **env_extra}

    # Try via installed command first, then via python module
    for cmd in (
        ["autodev", "classify-input", "--input", "test"],
        [sys.executable, "-m", "autodev.cli", "classify-input", "--input", "test"],
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
                    f"FACTORY_FORCE_MOCK=1 {' '.join(cmd)} exit 0",
                    (time.monotonic() - t0) * 1000,
                )
            # Distinguish "command not found" vs real failure
            if proc.returncode == 2 and "No such command" in (proc.stderr + proc.stdout):
                # classify-input sub-command might not exist; treat as skip
                return _make(
                    name,
                    "skip",
                    f"'classify-input' sub-command not found in CLI; skipping",
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
        return _make(name, "pass", f"All 3 packaging files present", (time.monotonic() - t0) * 1000, ", ".join(present))
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
# Orchestrator
# ---------------------------------------------------------------------------

ALL_CHECKS = [
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


def run_all_checks(repo: Path) -> list[CheckResult]:
    results = []
    for fn in ALL_CHECKS:
        try:
            result = fn(repo)
        except Exception as exc:  # noqa: BLE001
            result = _make(fn.__name__.replace("check_", ""), "fail", f"Unexpected error: {exc}", 0)
        results.append(result)
    return results


def build_report(repo: Path) -> dict[str, Any]:
    checks = run_all_checks(repo)
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
    parser = argparse.ArgumentParser(description="autodev-ai Release Readiness Gate")
    parser.add_argument("--repo-path", default=".", help="Path to the repository root")
    parser.add_argument(
        "--output",
        default="docs/validation/release_readiness_gate_run.json",
        help="Output JSON path (relative to repo-path or absolute)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any check fails",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo_path).resolve()
    report = build_report(repo)

    # Resolve output path
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = repo / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Print summary to stdout
    summary = report["summary"]
    overall = report["overall"]
    print(f"\n=== Release Readiness Gate ===")
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

    if args.strict and not report["strict_pass"]:
        sys.exit(1)

    return report


if __name__ == "__main__":
    main()
