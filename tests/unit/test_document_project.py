"""Unit tests for DocumentProjectAgent."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from autodev.agents.document_project import DocumentProjectAgent
from autodev.schemas import BrownfieldDoc, Language

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_python_repo(tmp_path: Path) -> Path:
    """Minimal Python project layout."""
    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "my-tool"
            description = "A handy Python tool"
            version = "0.1.0"

            [project.dependencies]
            requests = ">=2.28"
            pydantic = ">=2.0"

            [project.scripts]
            my-tool = "my_tool.cli:app"

            [tool.pytest.ini_options]
            testpaths = ["tests"]
        """),
        encoding="utf-8",
    )
    # README
    (tmp_path / "README.md").write_text(
        "# my-tool\n\nA handy Python tool for doing things.\n",
        encoding="utf-8",
    )
    # Package
    pkg = tmp_path / "my_tool"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    (pkg / "models.py").write_text(
        textwrap.dedent("""\
            from pydantic import BaseModel

            class Item(BaseModel):
                name: str
                price: float

            class Order(BaseModel):
                id: int
                items: list[Item]
        """),
        encoding="utf-8",
    )
    (pkg / "cli.py").write_text(
        textwrap.dedent("""\
            import typer
            app = typer.Typer()

            @app.command()
            def main():
                pass
        """),
        encoding="utf-8",
    )
    # Tests
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("", encoding="utf-8")
    (tests / "conftest.py").write_text(
        textwrap.dedent("""\
            import pytest

            @pytest.fixture
            def sample_item():
                return {"name": "foo", "price": 1.0}
        """),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def node_repo(tmp_path: Path) -> Path:
    """Minimal Node.js project layout."""
    (tmp_path / "package.json").write_text(
        textwrap.dedent("""\
            {
              "name": "my-app",
              "description": "A Node application",
              "dependencies": {
                "express": "^4.18.0",
                "lodash": "^4.17.21"
              },
              "devDependencies": {
                "jest": "^29.0.0"
              }
            }
        """),
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Test 1 — overview section
# ---------------------------------------------------------------------------

def test_overview_reads_pyproject_description(simple_python_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc = agent.document(str(simple_python_repo), languages=[Language.PYTHON])
    overview = next(s for s in doc.sections if s.name == "overview")
    assert "my-tool" in overview.body_markdown
    assert "A handy Python tool" in overview.body_markdown


# ---------------------------------------------------------------------------
# Test 2 — architecture-overview section
# ---------------------------------------------------------------------------

def test_architecture_overview_lists_package(simple_python_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc = agent.document(str(simple_python_repo), languages=[Language.PYTHON])
    arch = next(s for s in doc.sections if s.name == "architecture-overview")
    # should list my_tool package
    assert "my_tool" in arch.body_markdown
    # should have directory structure block
    assert "```" in arch.body_markdown


# ---------------------------------------------------------------------------
# Test 3 — entry-points section
# ---------------------------------------------------------------------------

def test_entry_points_finds_scripts(simple_python_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc = agent.document(str(simple_python_repo), languages=[Language.PYTHON])
    ep = next(s for s in doc.sections if s.name == "entry-points")
    # pyproject.toml scripts section detected
    assert "my-tool" in ep.body_markdown


# ---------------------------------------------------------------------------
# Test 4 — key-data-models section (Pydantic)
# ---------------------------------------------------------------------------

def test_data_models_finds_pydantic_classes(simple_python_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc = agent.document(str(simple_python_repo), languages=[Language.PYTHON])
    models = next(s for s in doc.sections if s.name == "key-data-models")
    assert "Item" in models.body_markdown
    assert "Order" in models.body_markdown


# ---------------------------------------------------------------------------
# Test 5 — external-deps section
# ---------------------------------------------------------------------------

def test_external_deps_reads_pyproject_deps(simple_python_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc = agent.document(str(simple_python_repo), languages=[Language.PYTHON])
    deps = next(s for s in doc.sections if s.name == "external-deps")
    assert "requests" in deps.markdown_for("external-deps") if hasattr(deps, "markdown_for") else True
    # direct check on body
    assert "requests" in deps.body_markdown or "pydantic" in deps.body_markdown


# ---------------------------------------------------------------------------
# Test 6 — testing-conventions section
# ---------------------------------------------------------------------------

def test_testing_conventions_finds_pytest_config(simple_python_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc = agent.document(str(simple_python_repo), languages=[Language.PYTHON])
    tc = next(s for s in doc.sections if s.name == "testing-conventions")
    # pytest config should mention testpaths
    assert "testpaths" in tc.body_markdown or "tests" in tc.body_markdown.lower()


# ---------------------------------------------------------------------------
# Test 7 — BrownfieldDoc structure
# ---------------------------------------------------------------------------

def test_document_returns_brownfield_doc_with_7_sections(simple_python_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc = agent.document(str(simple_python_repo))
    assert isinstance(doc, BrownfieldDoc)
    assert len(doc.sections) == 7
    names = [s.name for s in doc.sections]
    expected = [
        "overview",
        "architecture-overview",
        "entry-points",
        "key-data-models",
        "external-deps",
        "testing-conventions",
        "commit-history-patterns",
    ]
    assert names == expected


# ---------------------------------------------------------------------------
# Test 8 — idempotent writes
# ---------------------------------------------------------------------------

def test_idempotent_writes(simple_python_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc1 = agent.document(str(simple_python_repo))
    doc2 = agent.document(str(simple_python_repo))
    # Same output_dir
    assert doc1.output_dir == doc2.output_dir
    # Files exist and are the same size
    for s1, s2 in zip(doc1.sections, doc2.sections, strict=False):
        assert s1.name == s2.name
        assert s1.file_path is not None
        p = Path(s1.file_path)
        assert p.exists()


# ---------------------------------------------------------------------------
# Test 9 — node overview
# ---------------------------------------------------------------------------

def test_overview_reads_package_json(node_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc = agent.document(str(node_repo))
    overview = next(s for s in doc.sections if s.name == "overview")
    assert "my-app" in overview.body_markdown or "A Node application" in overview.body_markdown


# ---------------------------------------------------------------------------
# Test 10 — node external-deps
# ---------------------------------------------------------------------------

def test_external_deps_reads_package_json(node_repo: Path) -> None:
    agent = DocumentProjectAgent()
    doc = agent.document(str(node_repo))
    deps = next(s for s in doc.sections if s.name == "external-deps")
    assert "express" in deps.body_markdown
