"""Integration tests for the `document-project` CLI subcommand."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from autodev.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def python_project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "python-project"
            description = "Integration test Python project"
            version = "0.1.0"

            [project.dependencies]
            httpx = ">=0.24"
        """),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# python-project\n\nIntegration test.\n", encoding="utf-8")
    src = tmp_path / "python_project"
    src.mkdir()
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "models.py").write_text(
        textwrap.dedent("""\
            from pydantic import BaseModel

            class Widget(BaseModel):
                widget_id: int
                label: str
        """),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def mixed_project(tmp_path: Path) -> Path:
    # Python part
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "mixed-project"
            description = "A mixed Python+JS project"
            version = "0.2.0"

            [project.dependencies]
            fastapi = ">=0.100"
        """),
        encoding="utf-8",
    )
    # Node part
    (tmp_path / "package.json").write_text(
        textwrap.dedent("""\
            {
              "name": "mixed-frontend",
              "description": "Frontend for mixed project",
              "dependencies": {
                "react": "^18.0.0"
              }
            }
        """),
        encoding="utf-8",
    )
    src = tmp_path / "app"
    src.mkdir()
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "routes.py").write_text(
        textwrap.dedent("""\
            from fastapi import APIRouter
            router = APIRouter()

            @router.get("/health")
            def health():
                return {"status": "ok"}

            @router.post("/items")
            def create_item():
                pass
        """),
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Test 1 — python_project generates docs and exits 0
# ---------------------------------------------------------------------------

def test_cli_document_project_python(python_project: Path) -> None:
    result = runner.invoke(app, ["document-project", "--repo-path", str(python_project)])
    assert result.exit_code == 0, result.output
    # Check output includes expected fields
    assert "sections=7" in result.output
    assert "output_dir" in result.output
    # Verify files were written on disk
    output_dir = python_project / ".autodev" / "brownfield-docs"
    assert output_dir.exists()
    assert (output_dir / "overview.md").exists()
    assert (output_dir / "external-deps.md").exists()
    # Content checks
    overview_text = (output_dir / "overview.md").read_text(encoding="utf-8")
    assert "python-project" in overview_text
    deps_text = (output_dir / "external-deps.md").read_text(encoding="utf-8")
    assert "httpx" in deps_text


# ---------------------------------------------------------------------------
# Test 2 — mixed_project with --languages python,javascript
# ---------------------------------------------------------------------------

def test_cli_document_project_mixed(mixed_project: Path) -> None:
    result = runner.invoke(
        app,
        [
            "document-project",
            "--repo-path",
            str(mixed_project),
            "--languages",
            "python,javascript",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "sections=7" in result.output
    output_dir = mixed_project / ".autodev" / "brownfield-docs"
    assert output_dir.exists()

    # entry-points should find the HTTP routes
    ep_text = (output_dir / "entry-points.md").read_text(encoding="utf-8")
    assert "/health" in ep_text or "routes.py" in ep_text

    # external-deps should include both pyproject and package.json deps
    deps_text = (output_dir / "external-deps.md").read_text(encoding="utf-8")
    assert "fastapi" in deps_text
    assert "react" in deps_text
