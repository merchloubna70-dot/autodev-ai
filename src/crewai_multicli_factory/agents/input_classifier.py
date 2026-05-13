"""Classify raw input into an InputType and recommend a flow."""
from __future__ import annotations

from pathlib import Path

from ..schemas import InputClassification, InputType, Language
from ._crewai_bridge import make_agent


class InputClassifierAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Input Classifier",
            goal="Decide whether the input is an issue, a PRD, a project brief, an empty repo, or existing project work.",
            backstory="A meticulous triage analyst at the entrance of a software factory.",
        )

    def classify(self, *, text: str, source_path: str | None = None, source_url: str | None = None,
                 is_empty_repo: bool = False, has_existing_code: bool = False) -> InputClassification:
        lower = text.lower()
        # URL hint
        if source_url and "github.com" in source_url and "/issues/" in source_url:
            return InputClassification(
                input_type=InputType.GITHUB_ISSUE, confidence=0.95,
                rationale="URL matches GitHub issue pattern.",
                suggested_flow="issue_pipeline_flow", source_url=source_url,
            )
        # Strong markers
        if any(k in lower for k in ("steps to reproduce", "bug:", "traceback", "stacktrace")):
            return InputClassification(
                input_type=InputType.BUGFIX_REQUEST, confidence=0.85,
                rationale="Contains bug-report markers.",
                suggested_flow="issue_pipeline_flow", source_path=source_path,
            )
        if any(k in lower for k in ("# prd", "product requirements", "functional requirements", "acceptance criteria")):
            return InputClassification(
                input_type=InputType.PRD, confidence=0.85,
                rationale="Contains PRD-style sections.",
                suggested_flow="project_delivery_flow", source_path=source_path,
            )
        if any(k in lower for k in ("# brief", "project brief", "we want to build", "vision:")):
            return InputClassification(
                input_type=InputType.PROJECT_BRIEF, confidence=0.8,
                rationale="Reads like a project brief.",
                suggested_flow="project_delivery_flow", source_path=source_path,
            )
        if any(k in lower for k in ("architecture", "module map", "data model")):
            return InputClassification(
                input_type=InputType.ARCHITECTURE_DOC, confidence=0.6,
                rationale="Mentions architecture vocabulary.",
                suggested_flow="project_delivery_flow", source_path=source_path,
            )
        # Repo state hints
        if is_empty_repo:
            return InputClassification(
                input_type=InputType.EMPTY_REPO_PROJECT, confidence=0.7,
                rationale="Target repo is empty.",
                suggested_flow="project_delivery_flow", source_path=source_path,
            )
        if has_existing_code:
            # default: assume it's an issue/request against existing code
            if source_path and Path(source_path).name in ("issue.md", "issue.json"):
                return InputClassification(
                    input_type=InputType.LOCAL_ISSUE, confidence=0.75,
                    rationale="Local issue file against existing repo.",
                    suggested_flow="issue_pipeline_flow", source_path=source_path,
                )
            return InputClassification(
                input_type=InputType.EXISTING_REPO_PROJECT, confidence=0.6,
                rationale="Existing repo with input; defaulting to project delivery flow.",
                suggested_flow="project_delivery_flow", source_path=source_path,
            )
        return InputClassification(
            input_type=InputType.UNKNOWN, confidence=0.3,
            rationale="Could not confidently classify.",
            suggested_flow="project_delivery_flow", source_path=source_path,
            detected_languages=[Language.UNKNOWN],
        )
