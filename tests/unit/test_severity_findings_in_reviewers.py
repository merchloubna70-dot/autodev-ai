"""Tests that reviewers emit severity-prefixed findings and severity_findings attr."""


from autodev.agents.code_reviewer import CodeReviewerAgent
from autodev.agents.integration_reviewer import IntegrationReviewerAgent
from autodev.agents.security_reviewer import SecurityReviewerAgent
from autodev.schemas import (
    ApiContract,
    ApiEndpoint,
    Language,
    Severity,
)


def test_security_reviewer_findings_have_severity_prefix(tmp_path):
    """SecurityReviewerAgent findings start with a [SEVERITY] prefix."""
    # Create a file that triggers a BLOCKER (secret pattern)
    (tmp_path / "secret.py").write_text("AKIA_FAKE_SECRET = 'AKIA1234567890EXAMPLE'")
    agent = SecurityReviewerAgent()
    report = agent.review(repo_path=str(tmp_path))
    assert report.findings, "Expected at least one finding"
    for f in report.findings:
        assert f.startswith("[BLOCKER]") or f.startswith("[MAJOR]") or \
               f.startswith("[MINOR]") or f.startswith("[NITPICK]"), \
               f"Finding missing severity prefix: {f!r}"
    # severity_findings attribute is populated
    assert hasattr(report, "severity_findings"), "severity_findings attr missing"
    assert any(sf.severity == Severity.BLOCKER for sf in report.severity_findings)


def test_integration_reviewer_contract_diff_finding_is_major():
    """IntegrationReviewerAgent '[ContractDiff]' finding maps to MAJOR severity."""
    # Duplicate endpoint triggers a finding
    api = ApiContract(endpoints=[
        ApiEndpoint(name="a", method="get", path="/x", description="d"),
        ApiEndpoint(name="b", method="GET", path="/x", description="d"),
    ])
    agent = IntegrationReviewerAgent()
    report = agent.review(api_contract=api, dependency_graph=None, languages=[Language.PYTHON])
    assert report.findings, "Expected at least one finding"
    # All findings should be prefixed
    for f in report.findings:
        assert f.startswith("[BLOCKER]") or f.startswith("[MAJOR]") or \
               f.startswith("[MINOR]") or f.startswith("[NITPICK]"), \
               f"Finding missing severity prefix: {f!r}"
    # Duplicate endpoint should be MAJOR
    assert hasattr(report, "severity_findings")
    majors = [sf for sf in report.severity_findings if sf.severity == Severity.MAJOR]
    assert majors, "Expected at least one MAJOR severity finding for duplicate endpoint"


def test_code_reviewer_no_execution_result_is_major():
    """CodeReviewerAgent 'no execution result' finding maps to MAJOR severity."""
    from autodev.agents.milestone_planner import MilestonePlannerAgent
    from autodev.agents.system_architect import SystemArchitectAgent
    from autodev.agents.task_decomposer import TaskDecomposerAgent
    from autodev.schemas import PRD, RepoScanResult

    prd = PRD(product_name="X", overview="o", functional_requirements=[],
              non_functional_requirements=[], acceptance_criteria=[])
    scan = RepoScanResult(repo_path="/tmp", is_empty=False, is_monorepo=False,
                          detected_languages=[Language.PYTHON], language_results={})
    arch = SystemArchitectAgent().design(prd=prd, scan=scan, languages=[Language.PYTHON])
    ms = MilestonePlannerAgent().plan(architecture=arch, languages=[Language.PYTHON])
    tasks = TaskDecomposerAgent().decompose(milestones=ms, architecture=arch, languages=[Language.PYTHON])

    agent = CodeReviewerAgent()
    report = agent.review(tasks=tasks, results=[])

    # findings with "no execution result" should be prefixed [MAJOR]
    assert any("no execution result" in f for f in report.findings)
    no_result_findings = [f for f in report.findings if "no execution result" in f]
    for f in no_result_findings:
        assert f.startswith("[MAJOR]"), f"Expected [MAJOR] prefix, got: {f!r}"

    # severity_findings also populated
    assert hasattr(report, "severity_findings")
    major_sfs = [sf for sf in report.severity_findings
                 if sf.severity == Severity.MAJOR and "no execution result" in sf.title.lower()]
    assert major_sfs, "Expected SeverityFinding with MAJOR severity for no execution result"
