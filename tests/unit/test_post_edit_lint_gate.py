"""Unit tests for PostEditLintGate."""
from __future__ import annotations

import pytest

from autodev.gates.post_edit_lint_gate import PostEditLintGate
from autodev.schemas import LintGateResult


@pytest.fixture()
def tmp_repo(tmp_path):
    """Return a temporary directory acting as a repo root."""
    return tmp_path


class TestPostEditLintGate:
    def setup_method(self):
        self.gate = PostEditLintGate()

    def test_python_valid_file_ok(self, tmp_repo):
        """A syntactically valid Python file should produce ok=True."""
        src = tmp_repo / "hello.py"
        src.write_text("def hello():\n    return 42\n")
        result = self.gate.run(
            repo_path=str(tmp_repo),
            changed_files=["hello.py"],
            language="python",
        )
        assert isinstance(result, LintGateResult)
        assert result.ok is True
        assert result.errors == []

    def test_python_syntax_error_ok_false(self, tmp_repo):
        """A Python file with a syntax error should produce ok=False."""
        src = tmp_repo / "bad.py"
        src.write_text("def broken(\n")  # unclosed parenthesis
        result = self.gate.run(
            repo_path=str(tmp_repo),
            changed_files=["bad.py"],
            language="python",
        )
        assert result.ok is False
        assert len(result.errors) >= 1
        assert "bad.py" in result.errors[0]

    def test_unsupported_language_skipped(self, tmp_repo):
        """An unsupported language should be skipped and return ok=True."""
        result = self.gate.run(
            repo_path=str(tmp_repo),
            changed_files=["query.sql"],
            language="sql",
        )
        assert result.ok is True
        assert result.errors == []

    def test_python_missing_file_ignored(self, tmp_repo):
        """Non-existent file should be silently ignored."""
        result = self.gate.run(
            repo_path=str(tmp_repo),
            changed_files=["nonexistent.py"],
            language="python",
        )
        assert result.ok is True

    def test_language_field_set(self, tmp_repo):
        """language field should be normalised and stored."""
        result = self.gate.run(
            repo_path=str(tmp_repo),
            changed_files=[],
            language="python",
        )
        assert result.language == "python"

    def test_changed_files_reflected(self, tmp_repo):
        """changed_files should appear in the result."""
        result = self.gate.run(
            repo_path=str(tmp_repo),
            changed_files=["a.py", "b.py"],
            language="python",
        )
        assert "a.py" in result.changed_files
        assert "b.py" in result.changed_files

    def test_non_py_files_ignored_in_python_mode(self, tmp_repo):
        """Non-.py files should be skipped when language=python."""
        (tmp_repo / "readme.md").write_text("# bad syntax !!!")
        result = self.gate.run(
            repo_path=str(tmp_repo),
            changed_files=["readme.md"],
            language="python",
        )
        assert result.ok is True
