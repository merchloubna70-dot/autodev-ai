"""Unit tests for ProjectContextFlow.

Real signatures:
  ProjectContextFlow() -- no args
  ProjectContextFlow.run(inputs: ProjectContextInput) -> ProjectContext

ProjectContextInput:
  repo_path: str = "."
  product_name: str = ""
  brief_path: str | None = None

ProjectContext:
  product_name, generated_at, rules, discovery, file_path

commit_to_disk writes:
  <repo_path>/_autodev/project-context.md
  <repo_path>/_autodev/project-context.json
"""
from __future__ import annotations

from pathlib import Path

from autodev.flows.project_context_flow import ProjectContextFlow
from autodev.schemas import ProjectContext, ProjectContextInput


class TestProjectContextFlowInitialization:
    def test_project_context_flow_initialization(self):
        flow = ProjectContextFlow()
        assert flow is not None
        assert hasattr(flow, "_agent"), "ProjectContextFlow must expose ._agent"


class TestProjectContextFlowHappyPath:
    def test_project_context_flow_happy_path(self, tmp_path):
        """Happy path: generates _autodev/project-context.{md,json} files."""
        # Minimal Python project so the agent has hints to discover
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "myapp"\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
            encoding="utf-8",
        )
        (tmp_path / "uv.lock").write_text("# lockfile\n", encoding="utf-8")

        flow = ProjectContextFlow()
        inp = ProjectContextInput(repo_path=str(tmp_path), product_name="MyApp")
        result = flow.run(inp)

        assert isinstance(result, ProjectContext)
        assert result.file_path is not None

        md_path = tmp_path / "_autodev" / "project-context.md"
        json_path = tmp_path / "_autodev" / "project-context.json"
        assert md_path.exists(), "_autodev/project-context.md must exist"
        assert json_path.exists(), "_autodev/project-context.json must exist"

        md_content = md_path.read_text(encoding="utf-8")
        assert "# Project Context" in md_content


class TestProjectContextFlowBriefPathOsErrorSilenced:
    def test_project_context_flow_brief_path_oserror_silenced(self, tmp_path):
        """Invalid brief_path results in brief=None, not an exception propagating."""
        flow = ProjectContextFlow()
        inp = ProjectContextInput(
            repo_path=str(tmp_path),
            brief_path="/nonexistent/path/brief.md",  # does not exist
        )
        result = flow.run(inp)  # must NOT raise

        assert isinstance(result, ProjectContext)
        # The flow silences the OSError; product_name falls back to repo dir name
        assert result.product_name  # non-empty fallback


class TestProjectContextFlowWithProductName:
    def test_project_context_flow_with_product_name(self, tmp_path):
        """product_name passed through correctly to ProjectContext.product_name."""
        flow = ProjectContextFlow()
        inp = ProjectContextInput(repo_path=str(tmp_path), product_name="SpecialApp")
        result = flow.run(inp)

        assert isinstance(result, ProjectContext)
        assert result.product_name == "SpecialApp", (
            f"Expected product_name='SpecialApp', got {result.product_name!r}"
        )

        md_content = Path(result.file_path).read_text(encoding="utf-8")
        assert "SpecialApp" in md_content, "product_name must appear in the generated markdown"
