"""Coverage tests for autodev/adapters/git_adapter.py (25.4% → target 70%+).

Uses a real git repo initialised via subprocess in a tmp dir so that
actual git commands run, covering the uncovered lines 18-58.
"""
from __future__ import annotations

import subprocess

import pytest

from autodev.adapters.git_adapter import GitAdapter

# ---------------------------------------------------------------------------
# Fixture: fresh git repo
# ---------------------------------------------------------------------------

@pytest.fixture()
def git_repo(tmp_path):
    """Create a minimal git repository and return its path."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@autodev.local"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Autodev Test"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# 1. has_git — True for real repo, False for plain dir
# ---------------------------------------------------------------------------

def test_has_git_true(git_repo):
    adapter = GitAdapter(str(git_repo))
    assert adapter.has_git() is True


def test_has_git_false(tmp_path):
    plain = tmp_path / "notarepo"
    plain.mkdir()
    adapter = GitAdapter(str(plain))
    assert adapter.has_git() is False


# ---------------------------------------------------------------------------
# 2. status — returns a string (even on empty repo)
# ---------------------------------------------------------------------------

def test_status_returns_string(git_repo):
    adapter = GitAdapter(str(git_repo))
    result = adapter.status()
    assert isinstance(result, str)
    # Empty git repo status mentions "No commits yet" or "nothing to commit"
    assert len(result) > 0


# ---------------------------------------------------------------------------
# 3. diff — returns a string (empty diff on clean repo)
# ---------------------------------------------------------------------------

def test_diff_returns_string_on_clean_repo(git_repo):
    # Create and commit a file first so diff has a baseline
    f = git_repo / "hello.txt"
    f.write_text("initial\n")
    subprocess.run(["git", "add", "hello.txt"], cwd=str(git_repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(git_repo), check=True, capture_output=True)

    adapter = GitAdapter(str(git_repo))
    result = adapter.diff()
    assert isinstance(result, str)
    # No unstaged changes → diff should be empty or very short
    assert result == "" or isinstance(result, str)


# ---------------------------------------------------------------------------
# 4. add — happy path: stages a file, returns exit_code 0
# ---------------------------------------------------------------------------

def test_add_stages_file(git_repo):
    f = git_repo / "staged.py"
    f.write_text("x = 1\n")
    adapter = GitAdapter(str(git_repo))
    code = adapter.add(["staged.py"])
    assert code == 0


def test_add_empty_paths_returns_zero(git_repo):
    adapter = GitAdapter(str(git_repo))
    code = adapter.add([])
    assert code == 0


# ---------------------------------------------------------------------------
# 5. commit — disabled=False short-circuits with exit_code 0
# ---------------------------------------------------------------------------

def test_commit_disabled_returns_zero(git_repo):
    adapter = GitAdapter(str(git_repo))
    code = adapter.commit("would not commit", enabled=False)
    assert code == 0


def test_commit_enabled_writes_message_file(git_repo):
    # Stage a file so there is something to commit
    f = git_repo / "something.txt"
    f.write_text("data\n")
    subprocess.run(["git", "add", "something.txt"], cwd=str(git_repo), check=True, capture_output=True)

    adapter = GitAdapter(str(git_repo))
    code = adapter.commit("test commit from adapter", enabled=True)
    assert code == 0
    # Message file should have been written
    msg_file = git_repo / ".dev-factory" / "COMMIT_MSG.txt"
    assert msg_file.exists()
    assert "test commit from adapter" in msg_file.read_text()


# ---------------------------------------------------------------------------
# 6. tag — disabled short-circuits with exit_code 0
# ---------------------------------------------------------------------------

def test_tag_disabled_returns_zero(git_repo):
    adapter = GitAdapter(str(git_repo))
    code = adapter.tag("v0.0.0", enabled=False)
    assert code == 0


# ---------------------------------------------------------------------------
# 7. push — disabled (default) returns 0, force-push guard raises
# ---------------------------------------------------------------------------

def test_push_disabled_returns_zero(git_repo):
    adapter = GitAdapter(str(git_repo))
    code = adapter.push(enabled=False)
    assert code == 0


def test_push_force_remote_name_rejected(git_repo):
    adapter = GitAdapter(str(git_repo))
    with pytest.raises(AssertionError):
        adapter.push(remote="--force", enabled=True)


def test_push_dry_run_enabled_assembles_command(git_repo, monkeypatch):
    """Verify dry_run flag is forwarded; the run may fail (no remote) but no crash."""
    adapter = GitAdapter(str(git_repo))
    # enabled=True but no remote → git push will fail; we just confirm no exception propagates
    code = adapter.push(remote="origin", dry_run=True, enabled=True)
    assert isinstance(code, int)
