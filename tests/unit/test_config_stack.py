"""Unit tests for ConfigStack 4-layer TOML deep-merge."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from autodev.utils.config_stack import ConfigStack, _deep_merge
from autodev.config import FactoryConfig


# ---------------------------------------------------------------------------
# 1. Load missing file does not crash
# ---------------------------------------------------------------------------

def test_load_missing_files_no_crash(tmp_path):
    """ConfigStack with a non-existent repo path should not raise."""
    stack = ConfigStack(repo_path=str(tmp_path / "nonexistent")).load()
    assert stack.data == {}


# ---------------------------------------------------------------------------
# 2. Deep-merge scalars: override wins
# ---------------------------------------------------------------------------

def test_deep_merge_scalars_override():
    base = {"a": 1, "b": {"x": 10, "y": 20}}
    override = {"a": 99, "b": {"x": 55}}
    result = _deep_merge(base, override)
    assert result["a"] == 99
    assert result["b"]["x"] == 55
    assert result["b"]["y"] == 20  # preserved from base


def test_deep_merge_new_key_appended():
    base = {"existing": True}
    override = {"new_key": "hello"}
    result = _deep_merge(base, override)
    assert result["new_key"] == "hello"
    assert result["existing"] is True


# ---------------------------------------------------------------------------
# 3. Arrays-of-tables: key replacement
# ---------------------------------------------------------------------------

def test_deep_merge_array_of_tables_key_replace():
    base = {"plugins": [{"code": "alpha", "value": 1}, {"code": "beta", "value": 2}]}
    override = {"plugins": [{"code": "alpha", "value": 99}]}
    result = _deep_merge(base, override)
    codes = {p["code"]: p["value"] for p in result["plugins"]}
    assert codes["alpha"] == 99   # replaced
    assert codes["beta"] == 2     # preserved


def test_deep_merge_array_of_tables_append_new():
    base = {"items": [{"id": "x", "v": 1}]}
    override = {"items": [{"id": "y", "v": 2}]}
    result = _deep_merge(base, override)
    ids = [item["id"] for item in result["items"]]
    assert "x" in ids
    assert "y" in ids


# ---------------------------------------------------------------------------
# 4. User-override beats team-base
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib stdlib requires 3.11+")
def test_user_override_beats_team_base(tmp_path):
    autodev_dir = tmp_path / ".autodev"
    autodev_dir.mkdir()

    (autodev_dir / "config.toml").write_text(
        textwrap.dedent("""\
        [codex]
        timeout_seconds = 300
        binary = "codex-team"
        """),
        encoding="utf-8",
    )
    (autodev_dir / "config.user.toml").write_text(
        textwrap.dedent("""\
        [codex]
        timeout_seconds = 999
        """),
        encoding="utf-8",
    )

    stack = ConfigStack(repo_path=str(tmp_path)).load()
    assert stack.data["codex"]["timeout_seconds"] == 999   # user override wins
    assert stack.data["codex"]["binary"] == "codex-team"   # team-base preserved


# ---------------------------------------------------------------------------
# 5. materialize_into FactoryConfig
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib stdlib requires 3.11+")
def test_materialize_into_factory_config(tmp_path):
    autodev_dir = tmp_path / ".autodev"
    autodev_dir.mkdir()

    (autodev_dir / "config.toml").write_text(
        textwrap.dedent("""\
        concurrency = 8
        fail_fast = false

        [codex]
        timeout_seconds = 42
        """),
        encoding="utf-8",
    )

    cfg = FactoryConfig()
    stack = ConfigStack(repo_path=str(tmp_path)).load()
    stack.materialize_into(cfg)

    assert cfg.concurrency == 8
    assert cfg.fail_fast is False
    assert cfg.codex.timeout_seconds == 42


# ---------------------------------------------------------------------------
# 6. from_stack classmethod
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib stdlib requires 3.11+")
def test_from_stack_classmethod(tmp_path):
    autodev_dir = tmp_path / ".autodev"
    autodev_dir.mkdir()
    (autodev_dir / "config.toml").write_text("concurrency = 5\n", encoding="utf-8")

    cfg = FactoryConfig.from_stack(repo_path=str(tmp_path))
    assert cfg.concurrency == 5


def test_from_stack_no_repo(tmp_path):
    """from_stack with no repo should not raise; env-layer defaults apply."""
    cfg = FactoryConfig.from_stack(repo_path=None)
    assert isinstance(cfg, FactoryConfig)
