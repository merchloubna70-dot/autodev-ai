"""Unit tests for SearchReplaceParser."""
from __future__ import annotations

import pytest

from autodev.executors.sr_edit_parser import SearchReplaceParser


class TestSearchReplaceParser:
    def setup_method(self):
        self.parser = SearchReplaceParser()

    def test_single_block_basic(self):
        """Parse a single SEARCH/REPLACE block with inline file path."""
        text = """\
<<<<<<< SEARCH src/foo.py
def old():
    pass
=======
def new():
    return 42
>>>>>>> REPLACE
"""
        patches = self.parser.parse(text)
        assert len(patches) == 1
        assert patches[0].path == "src/foo.py"
        assert "def new():" in patches[0].new_content
        assert "def old():" not in patches[0].new_content

    def test_multi_block(self):
        """Parse multiple SEARCH/REPLACE blocks from the same text."""
        text = """\
<<<<<<< SEARCH src/a.py
alpha
=======
ALPHA
>>>>>>> REPLACE

<<<<<<< SEARCH src/b.py
beta
=======
BETA
>>>>>>> REPLACE
"""
        patches = self.parser.parse(text)
        assert len(patches) == 2
        paths = {p.path for p in patches}
        assert "src/a.py" in paths
        assert "src/b.py" in paths

    def test_empty_input(self):
        """Empty string should return an empty list."""
        patches = self.parser.parse("")
        assert patches == []

    def test_malformed_missing_separator(self):
        """Block without ======= separator should be silently skipped."""
        text = """\
<<<<<<< SEARCH src/foo.py
old content
>>>>>>> REPLACE
"""
        patches = self.parser.parse(text)
        assert patches == []

    def test_malformed_missing_end_marker(self):
        """Block without >>>>>>> REPLACE should be silently skipped."""
        text = """\
<<<<<<< SEARCH src/foo.py
old content
=======
new content
"""
        patches = self.parser.parse(text)
        assert patches == []

    def test_path_traversal_rejected(self):
        """Path traversal (../) should raise ValueError."""
        text = """\
<<<<<<< SEARCH ../etc/passwd
old
=======
new
>>>>>>> REPLACE
"""
        with pytest.raises(ValueError, match="traversal"):
            self.parser.parse(text)

    def test_file_header_fallback(self):
        """If SEARCH line has no path, use # File: header."""
        text = """\
# File: src/utils.py
<<<<<<< SEARCH
old_func()
=======
new_func()
>>>>>>> REPLACE
"""
        patches = self.parser.parse(text)
        assert len(patches) == 1
        assert patches[0].path == "src/utils.py"

    def test_path_traversal_with_prefix_rejected(self):
        """Paths starting with .. should also be rejected."""
        text = """\
<<<<<<< SEARCH ../secret
data
=======
evil
>>>>>>> REPLACE
"""
        with pytest.raises(ValueError):
            self.parser.parse(text)
