"""Unit tests for BrownfieldDocFlow.

Real signatures:
  BrownfieldDocFlow() -- no args
  BrownfieldDocFlow.run(inp: BrownfieldDocInput) -> BrownfieldDoc

BrownfieldDocInput:
  repo_path: str = "."
  languages: list[Language] = []  (empty list is valid; None is NOT — field is list)

BrownfieldDoc:
  repo_path, sections (list[BrownfieldDocSection]), generated_at, output_dir, languages

DocumentProjectAgent.document always produces exactly 7 sections:
  overview, architecture-overview, entry-points, key-data-models,
  external-deps, testing-conventions, commit-history-patterns
"""
from __future__ import annotations

from pathlib import Path

from autodev.flows.brownfield_doc_flow import BrownfieldDocFlow
from autodev.schemas import BrownfieldDoc, BrownfieldDocInput, Language

_EXPECTED_SECTION_NAMES = {
    "overview",
    "architecture-overview",
    "entry-points",
    "key-data-models",
    "external-deps",
    "testing-conventions",
    "commit-history-patterns",
}


class TestBrownfieldDocFlowInitialization:
    def test_brownfield_doc_flow_initialization(self):
        flow = BrownfieldDocFlow()
        assert flow is not None
        assert hasattr(flow, "_agent"), "BrownfieldDocFlow must expose ._agent"


class TestBrownfieldDocFlowHappyPath:
    def test_brownfield_doc_flow_happy_path_python(self, tmp_path):
        """Happy path: Python repo produces exactly 7 expected doc artifacts."""
        # Minimal Python project scaffold so the agent has something to scan
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "testpkg"\ndescription = "A test package"\n',
            encoding="utf-8",
        )
        pkg = tmp_path / "src" / "testpkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("# init\n", encoding="utf-8")

        flow = BrownfieldDocFlow()
        inp = BrownfieldDocInput(repo_path=str(tmp_path), languages=[Language.PYTHON])
        result = flow.run(inp)

        assert isinstance(result, BrownfieldDoc)
        assert len(result.sections) == 7, f"Expected 7 sections, got {len(result.sections)}"

        produced_names = {s.name for s in result.sections}
        assert produced_names == _EXPECTED_SECTION_NAMES, (
            f"Section names mismatch: {produced_names} != {_EXPECTED_SECTION_NAMES}"
        )

        # Every section must have an on-disk .md file
        for section in result.sections:
            assert section.file_path is not None, f"section {section.name!r} missing file_path"
            assert Path(section.file_path).exists(), f"section file {section.file_path!r} not on disk"


class TestBrownfieldDocFlowLanguagesNonePassthrough:
    def test_brownfield_doc_flow_languages_none_passthrough(self, tmp_path):
        """languages=[] (empty list) doesn't crash; flow delegates None to agent."""
        flow = BrownfieldDocFlow()
        # BrownfieldDocInput.languages default is [] (empty list), not None
        inp = BrownfieldDocInput(repo_path=str(tmp_path), languages=[])
        result = flow.run(inp)  # must not raise

        assert isinstance(result, BrownfieldDoc)
        assert result.sections, "At least one section must be generated even with empty languages"


class TestBrownfieldDocFlowOutputDirWritable:
    def test_brownfield_doc_flow_output_dir_writable(self, tmp_path):
        """Verify produced .md files exist under .autodev/brownfield-docs/."""
        flow = BrownfieldDocFlow()
        inp = BrownfieldDocInput(repo_path=str(tmp_path))
        result = flow.run(inp)

        out_dir = tmp_path / ".autodev" / "brownfield-docs"
        assert out_dir.is_dir(), "output directory must be created"

        md_files = list(out_dir.glob("*.md"))
        assert len(md_files) == 7, f"Expected 7 .md files in output dir, found {len(md_files)}"

        for section in result.sections:
            assert section.file_path is not None
            p = Path(section.file_path)
            assert p.exists() and p.suffix == ".md"
            # File must have content (not empty)
            assert p.stat().st_size > 0, f"{section.file_path} is empty"
