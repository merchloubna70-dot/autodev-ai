"""Tests for scripts/coverage_gate.py — the coverage threshold gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import coverage_gate as gate  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Minimal fake repo with a small coverage.json."""
    cov = {
        "totals": {"percent_covered": 82.5, "num_statements": 100, "missing_lines": 18},
        "files": {
            "src/autodev/cli.py": {"summary": {"percent_covered": 88.0}},
            "src/autodev/release_readiness_gate.py": {"summary": {"percent_covered": 97.0}},
            "src/autodev/mcp_server/server.py": {"summary": {"percent_covered": 90.0}},
            "src/autodev/mcp_server/tools.py": {"summary": {"percent_covered": 92.0}},
            "src/autodev/adapters/a2a/server.py": {"summary": {"percent_covered": 95.0}},
            "src/autodev/adapters/a2a/client.py": {"summary": {"percent_covered": 95.0}},
            "src/autodev/executors/executor_router.py": {"summary": {"percent_covered": 91.0}},
            "src/autodev/executors/worker_isolator.py": {"summary": {"percent_covered": 95.0}},
            "src/autodev/flows/release_flow.py": {"summary": {"percent_covered": 100.0}},
            "src/autodev/flows/milestone_flow.py": {"summary": {"percent_covered": 100.0}},
            "src/autodev/flows/replay_flow.py": {"summary": {"percent_covered": 88.0}},
            "src/autodev/adapters/a2a/transports/http.py": {"summary": {"percent_covered": 95.0}},
            "src/autodev/utils/command_safety.py": {"summary": {"percent_covered": 95.0}},
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov), encoding="utf-8")
    return tmp_path


def test_overall_pass_when_above_threshold(repo: Path) -> None:
    result = gate.run_gate(repo, overall_threshold=80, release_threshold=85, security_threshold=90)
    overall = next(c for c in result["checks"] if c["name"] == "overall")
    assert overall["status"] == "pass"
    assert overall["actual"] == 82.5


def test_overall_fail_when_below_threshold(repo: Path) -> None:
    result = gate.run_gate(repo, overall_threshold=85, release_threshold=85, security_threshold=90)
    overall = next(c for c in result["checks"] if c["name"] == "overall")
    assert overall["status"] == "fail"


def test_release_critical_modules_evaluated(repo: Path) -> None:
    result = gate.run_gate(repo, overall_threshold=80, release_threshold=85, security_threshold=90)
    release_checks = [c for c in result["checks"] if c["name"].startswith("release::")]
    assert len(release_checks) == len(gate.RELEASE_CRITICAL)


def test_security_critical_modules_evaluated(repo: Path) -> None:
    result = gate.run_gate(repo, overall_threshold=80, release_threshold=85, security_threshold=90)
    security_checks = [c for c in result["checks"] if c["name"].startswith("security::")]
    assert len(security_checks) == len(gate.SECURITY_CRITICAL)


def test_exempt_module_does_not_fail(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tier-listed module with 0% coverage should not fail the gate when exempted."""
    cov_path = repo / "coverage.json"
    cov = json.loads(cov_path.read_text())
    cov["files"]["src/autodev/cli.py"]["summary"]["percent_covered"] = 0.0
    cov_path.write_text(json.dumps(cov))
    monkeypatch.setitem(gate.EXEMPTIONS, "src/autodev/cli.py", "test-only exemption")

    result = gate.run_gate(repo, overall_threshold=80, release_threshold=85, security_threshold=90)
    exempt = next(c for c in result["checks"]
                  if c["name"] == "release::src/autodev/cli.py")
    assert exempt["status"] == "exempt"
    assert exempt["detail"]


def test_exemption_reason_present(repo: Path) -> None:
    for f, reason in gate.EXEMPTIONS.items():
        assert reason, f"Exemption for {f} has empty reason"


def test_strict_pass_true_when_no_fails(repo: Path) -> None:
    result = gate.run_gate(repo, overall_threshold=80, release_threshold=85, security_threshold=90)
    assert result["strict_pass"] is True


def test_strict_pass_false_when_release_critical_too_low(repo: Path) -> None:
    """Lower cli.py coverage below threshold → strict_pass False."""
    cov_path = repo / "coverage.json"
    cov = json.loads(cov_path.read_text())
    cov["files"]["src/autodev/cli.py"]["summary"]["percent_covered"] = 40.0
    cov_path.write_text(json.dumps(cov))

    result = gate.run_gate(repo, overall_threshold=80, release_threshold=85, security_threshold=90)
    assert result["strict_pass"] is False
    cli = next(c for c in result["checks"]
               if c["name"] == "release::src/autodev/cli.py")
    assert cli["status"] == "fail"


def test_summary_counts_match_checks(repo: Path) -> None:
    result = gate.run_gate(repo, overall_threshold=80, release_threshold=85, security_threshold=90)
    summary = result["summary"]
    by_status: dict[str, int] = {"pass": 0, "fail": 0, "exempt": 0, "missing": 0}
    for c in result["checks"]:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    assert summary == by_status


def test_strict_exits_1_on_fail(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cov_path = repo / "coverage.json"
    cov = json.loads(cov_path.read_text())
    cov["files"]["src/autodev/cli.py"]["summary"]["percent_covered"] = 30.0
    cov_path.write_text(json.dumps(cov))

    with pytest.raises(SystemExit) as exc_info:
        gate.main([
            "--repo-path", str(repo),
            "--output", str(repo / "out.json"),
            "--overall-threshold", "80",
            "--release-threshold", "85",
            "--security-threshold", "90",
            "--strict",
        ])
    assert exc_info.value.code == 1


def test_main_non_strict_does_not_exit_on_fail(repo: Path) -> None:
    cov_path = repo / "coverage.json"
    cov = json.loads(cov_path.read_text())
    cov["files"]["src/autodev/cli.py"]["summary"]["percent_covered"] = 30.0
    cov_path.write_text(json.dumps(cov))

    # No --strict; should return a dict, not SystemExit
    result = gate.main([
        "--repo-path", str(repo),
        "--output", str(repo / "out.json"),
        "--overall-threshold", "80",
        "--release-threshold", "85",
        "--security-threshold", "90",
    ])
    assert result["strict_pass"] is False


def test_missing_coverage_json_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        gate.run_gate(tmp_path, 80, 85, 90)


def test_output_json_written(repo: Path) -> None:
    out = repo / "gate_out.json"
    gate.main([
        "--repo-path", str(repo),
        "--output", str(out),
        "--overall-threshold", "80",
    ])
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["gate"] == "coverage_threshold"
    assert "checks" in data
