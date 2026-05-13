"""Tests: SecurityReviewerAgent false-positive suppression for doc files."""
from __future__ import annotations

from pathlib import Path


def _make_file(tmp_path: Path, rel: str, content: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Test 1: Plain prose ".md" mentioning "env" is NOT flagged for " env "
# ---------------------------------------------------------------------------

def test_md_prose_env_not_flagged(tmp_path):
    """A .md file with prose 'env vars' or 'environment variables' must NOT trigger ' env '."""
    repo = tmp_path / "repo"
    _make_file(
        repo,
        "docs/architecture.md",
        "# Architecture\n\ndeployment: env vars are set via the CI pipeline.\n"
        "The service reads environment variables at startup.\n",
    )
    from autodev.agents.security_reviewer import SecurityReviewerAgent
    report = SecurityReviewerAgent().review(repo_path=str(repo))
    env_blocked = [f for f in report.findings if "' env '" in f or "\"env\"" in f or " env " in f]
    assert not env_blocked, (
        f"Expected no ' env ' findings for plain-prose markdown, got: {env_blocked}"
    )
    # Should be recorded in false_positives_filtered if the pattern was present
    fp_filtered = getattr(report, "false_positives_filtered", [])
    # The file contained " env " so it should be noted as filtered
    assert any("env" in fp for fp in fp_filtered), (
        f"Expected ' env ' to appear in false_positives_filtered, got: {fp_filtered}"
    )


# ---------------------------------------------------------------------------
# Test 2: Shell ".sh" file containing "env LANG=…" IS flagged
# ---------------------------------------------------------------------------

def test_sh_file_env_is_flagged(tmp_path):
    """A .sh script with 'env LANG=C command' must be flagged as a security finding."""
    repo = tmp_path / "repo"
    _make_file(
        repo,
        "scripts/run.sh",
        "#!/bin/bash\n env LANG=C python manage.py migrate\n",
    )
    from autodev.agents.security_reviewer import SecurityReviewerAgent
    report = SecurityReviewerAgent().review(repo_path=str(repo))
    env_findings = [f for f in report.findings if "env" in f]
    assert env_findings, (
        "Expected ' env ' pattern to be flagged in a .sh file, but got no findings"
    )


# ---------------------------------------------------------------------------
# Test 3: .md with fenced bash block containing "env LANG=…" IS flagged
# ---------------------------------------------------------------------------

def test_md_fenced_bash_env_is_flagged(tmp_path):
    """A .md file with a fenced bash block containing 'env LANG=…' must still be flagged."""
    repo = tmp_path / "repo"
    _make_file(
        repo,
        "README.md",
        "# Usage\n\nRun like this:\n\n```bash\n env LANG=C make build\n```\n",
    )
    from autodev.agents.security_reviewer import SecurityReviewerAgent
    report = SecurityReviewerAgent().review(repo_path=str(repo))
    env_findings = [f for f in report.findings if "env" in f]
    assert env_findings, (
        "Expected ' env ' to be flagged in a .md file with a fenced bash block, but no findings found"
    )


# ---------------------------------------------------------------------------
# Test 4: "rm -rf" is still flagged in .md files (other denylist entries unaffected)
# ---------------------------------------------------------------------------

def test_rm_rf_still_flagged_in_md(tmp_path):
    """'rm -rf' must still be flagged in .md files — only ' env ' gets the doc-FP exemption."""
    repo = tmp_path / "repo"
    _make_file(
        repo,
        "CONTRIBUTING.md",
        "# Cleanup\n\nTo clean up run `rm -rf build/`.\n",
    )
    from autodev.agents.security_reviewer import SecurityReviewerAgent
    report = SecurityReviewerAgent().review(repo_path=str(repo))
    rm_findings = [f for f in report.findings if "rm -rf" in f]
    assert rm_findings, (
        "Expected 'rm -rf' to be flagged even in a .md file, but no finding was raised"
    )
