from autodev.agents.issue_analyst import IssueAnalystAgent


def test_parse_md_issue():
    text = (
        "# Fix login\n\n"
        "Login is broken.\n\n"
        "## Acceptance\n- user can log in\n- password reset works\n\n"
        "impacted areas: auth, ui\nLabels: bug, security\n"
    )
    iss = IssueAnalystAgent().parse(text, issue_id="42")
    assert iss.issue_id == "42"
    assert iss.title.lower().startswith("fix")
    assert "user can log in" in iss.acceptance_criteria
    assert "auth" in iss.impacted_areas
    assert iss.risk_level.value in ("medium", "low")


def test_parse_json_issue():
    text = '{"number": 7, "title": "Add JSON", "body": "details", "labels": ["enhancement"]}'
    iss = IssueAnalystAgent().parse(text)
    assert iss.issue_id == "7"
    assert iss.title == "Add JSON"
    assert "enhancement" in iss.labels
