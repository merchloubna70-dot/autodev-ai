"""Coverage tests for autodev/adapters/filesystem_adapter.py (43.8% → target 85%+).

Covers uncovered lines: exists (True/False), read, listdir (existing + missing).
"""
from __future__ import annotations

import pytest

from autodev.adapters.filesystem_adapter import FilesystemAdapter

# ---------------------------------------------------------------------------
# 1. exists — True for present file/dir, False for missing path
# ---------------------------------------------------------------------------

def test_exists_true_for_file(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("content")
    adapter = FilesystemAdapter(str(tmp_path))
    assert adapter.exists("hello.txt") is True


def test_exists_false_for_missing(tmp_path):
    adapter = FilesystemAdapter(str(tmp_path))
    assert adapter.exists("no_such_file.txt") is False


# ---------------------------------------------------------------------------
# 2. read — returns file text
# ---------------------------------------------------------------------------

def test_read_returns_file_content(tmp_path):
    f = tmp_path / "data.json"
    f.write_text('{"key": "value"}', encoding="utf-8")
    adapter = FilesystemAdapter(str(tmp_path))
    content = adapter.read("data.json")
    assert content == '{"key": "value"}'


def test_read_raises_on_missing_file(tmp_path):
    adapter = FilesystemAdapter(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        adapter.read("nonexistent.txt")


# ---------------------------------------------------------------------------
# 3. listdir — returns names for existing dir, empty list for missing
# ---------------------------------------------------------------------------

def test_listdir_returns_names(tmp_path):
    (tmp_path / "a.py").write_text("# a")
    (tmp_path / "b.py").write_text("# b")
    adapter = FilesystemAdapter(str(tmp_path))
    names = adapter.listdir()
    assert "a.py" in names
    assert "b.py" in names


def test_listdir_missing_subdir_returns_empty(tmp_path):
    adapter = FilesystemAdapter(str(tmp_path))
    result = adapter.listdir("no_such_subdir")
    assert result == []


def test_listdir_nested_rel(tmp_path):
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "main.py").write_text("pass")
    adapter = FilesystemAdapter(str(tmp_path))
    names = adapter.listdir("src")
    assert "main.py" in names
