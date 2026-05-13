from autodev.agents.input_classifier import InputClassifierAgent
from autodev.schemas import InputType


def test_classifies_github_issue_url():
    cls = InputClassifierAgent().classify(text="hi", source_url="https://github.com/o/r/issues/9")
    assert cls.input_type == InputType.GITHUB_ISSUE
    assert cls.suggested_flow == "issue_pipeline_flow"


def test_classifies_prd_text():
    text = "# PRD\n## Functional requirements\n- thing"
    cls = InputClassifierAgent().classify(text=text)
    assert cls.input_type == InputType.PRD


def test_classifies_empty_repo():
    cls = InputClassifierAgent().classify(text="some text", is_empty_repo=True)
    assert cls.input_type == InputType.EMPTY_REPO_PROJECT


def test_bugfix_marker():
    cls = InputClassifierAgent().classify(text="Steps to reproduce: ...")
    assert cls.input_type == InputType.BUGFIX_REQUEST
