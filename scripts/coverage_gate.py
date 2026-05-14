#!/usr/bin/env python3
"""autodev-ai Coverage Threshold Gate.

Reads ``coverage.json`` and validates three thresholds:

  1. Overall combined line+branch coverage >= ``--overall-threshold`` (default 80)
  2. Release-critical modules each >= ``--release-threshold`` (default 85)
     except documented exemptions
  3. Security-critical modules each >= ``--security-threshold`` (default 90)
     except documented exemptions

Documented exemptions (with reasons) are intentional and don't fail the gate:

  - src/autodev/tasks/*           — crewai optional dep not installed
  - src/autodev/tui/dashboard.py  — textual optional dep not installed
  - src/autodev/tui/widgets.py    — textual optional dep not installed

CLI:

  python scripts/coverage_gate.py                   # default thresholds
  python scripts/coverage_gate.py --strict          # exit 1 on any fail
  python scripts/coverage_gate.py --output gate.json

Output JSON shape::

  {
    "gate": "coverage_threshold",
    "ran_at": "2026-05-14T...",
    "thresholds": {"overall": 80, "release": 85, "security": 90},
    "overall_pct": 80,
    "checks": [{"name": "overall", "status": "pass|fail|exempt",
                "actual": 80, "threshold": 80, "detail": "..."}],
    "summary": {"pass": N, "fail": N, "exempt": N},
    "strict_pass": bool
  }
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Release-critical modules — must meet --release-threshold
RELEASE_CRITICAL: tuple[str, ...] = (
    "src/autodev/cli.py",
    "src/autodev/release_readiness_gate.py",
    "src/autodev/mcp_server/server.py",
    "src/autodev/mcp_server/tools.py",
    "src/autodev/adapters/a2a/server.py",
    "src/autodev/adapters/a2a/client.py",
    "src/autodev/executors/executor_router.py",
    "src/autodev/executors/worker_isolator.py",
    "src/autodev/flows/release_flow.py",
    "src/autodev/flows/milestone_flow.py",
    "src/autodev/flows/replay_flow.py",
)

# Security-critical modules — must meet --security-threshold
SECURITY_CRITICAL: tuple[str, ...] = (
    "src/autodev/adapters/a2a/transports/http.py",
    "src/autodev/executors/worker_isolator.py",
    "src/autodev/utils/command_safety.py",
)

# Modules whose coverage is intentionally low and not gate-checked.
# Each exemption requires a documented reason.
EXEMPTIONS: dict[str, str] = {
    "src/autodev/tasks/__init__.py": "crewai optional dep not installed",
    "src/autodev/tasks/architecture_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/commit_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/documentation_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/implementation_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/input_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/issue_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/milestone_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/product_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/quality_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/release_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/requirement_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/review_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/security_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/test_tasks.py": "crewai optional dep not installed",
    "src/autodev/tasks/verification_tasks.py": "crewai optional dep not installed",
}


def _load_coverage(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"coverage.json not found at {path}. Run pytest --cov first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _file_pct(cov: dict[str, Any], file_path: str) -> float | None:
    files = cov.get("files", {})
    entry = files.get(file_path)
    if entry is None:
        return None
    summary = entry.get("summary", {})
    return float(summary.get("percent_covered", 0.0))


def _check(name: str, actual: float | None, threshold: float, detail: str = "") -> dict[str, Any]:
    if actual is None:
        return {"name": name, "status": "missing", "actual": None, "threshold": threshold,
                "detail": detail or "file not in coverage report"}
    if actual >= threshold:
        return {"name": name, "status": "pass", "actual": round(actual, 1), "threshold": threshold,
                "detail": detail}
    return {"name": name, "status": "fail", "actual": round(actual, 1), "threshold": threshold,
            "detail": detail}


def run_gate(repo_root: Path, overall_threshold: float, release_threshold: float,
             security_threshold: float) -> dict[str, Any]:
    cov_path = repo_root / "coverage.json"
    cov = _load_coverage(cov_path)
    totals = cov.get("totals", {})
    overall_pct = float(totals.get("percent_covered", 0.0))

    checks: list[dict[str, Any]] = []

    # Overall
    checks.append(_check("overall", overall_pct, overall_threshold,
                         "line+branch combined coverage from coverage.json totals"))

    # Release-critical
    for f in RELEASE_CRITICAL:
        if f in EXEMPTIONS:
            checks.append({"name": f"release::{f}", "status": "exempt", "actual": None,
                           "threshold": release_threshold, "detail": EXEMPTIONS[f]})
            continue
        pct = _file_pct(cov, f)
        checks.append(_check(f"release::{f}", pct, release_threshold))

    # Security-critical
    for f in SECURITY_CRITICAL:
        if f in EXEMPTIONS:
            checks.append({"name": f"security::{f}", "status": "exempt", "actual": None,
                           "threshold": security_threshold, "detail": EXEMPTIONS[f]})
            continue
        pct = _file_pct(cov, f)
        checks.append(_check(f"security::{f}", pct, security_threshold))

    summary = {"pass": 0, "fail": 0, "exempt": 0, "missing": 0}
    for c in checks:
        summary[c["status"]] = summary.get(c["status"], 0) + 1

    strict_pass = summary["fail"] == 0 and summary.get("missing", 0) == 0

    return {
        "gate": "coverage_threshold",
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "thresholds": {
            "overall": overall_threshold,
            "release": release_threshold,
            "security": security_threshold,
        },
        "overall_pct": round(overall_pct, 1),
        "checks": checks,
        "summary": summary,
        "strict_pass": strict_pass,
    }


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="autodev-ai coverage threshold gate")
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--overall-threshold", type=float, default=80.0)
    parser.add_argument("--release-threshold", type=float, default=85.0)
    parser.add_argument("--security-threshold", type=float, default=90.0)
    parser.add_argument("--output", default="docs/validation/coverage_gate_run.json")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 if any non-exempt check fails")
    args = parser.parse_args(argv)

    repo = Path(args.repo_path).resolve()
    report = run_gate(repo, args.overall_threshold, args.release_threshold,
                      args.security_threshold)

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = repo / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["summary"]
    print("\n=== Coverage Threshold Gate ===")
    print(f"  overall_pct : {report['overall_pct']}% (threshold {args.overall_threshold}%)")
    print(f"  pass        : {summary['pass']}")
    print(f"  fail        : {summary['fail']}")
    print(f"  exempt      : {summary['exempt']}")
    print(f"  missing     : {summary.get('missing', 0)}")
    print(f"  report      : {out_path}")
    print()
    for c in report["checks"]:
        icon = {"pass": "✓", "fail": "✗", "exempt": "·", "missing": "?"}.get(c["status"], "?")
        actual = c["actual"]
        actual_str = f"{actual}%" if actual is not None else "-"
        print(f"  {icon} [{c['status']:7s}] {c['name']:60s} {actual_str:>7s} / {c['threshold']:.0f}%")
        if c["status"] in ("fail", "missing") and c.get("detail"):
            print(f"           {c['detail']}")

    if args.strict and not report["strict_pass"]:
        sys.exit(1)
    return report


if __name__ == "__main__":
    main()
