"""Edge-case coverage for autodev/utils/config_stack.py (82.9% → target 92%+).

Uncovered branches:
- lines 18-24: Python < 3.11 tomllib fallback (mocked)
- line 57: array-of-tables item with key=None → appended as-is
- line 61: plain list (not AoT) → concatenated
- line 73: tomllib is None → RuntimeError
- line 135: ConfigStack.get with missing key returns default
- line 143: ConfigStack.data property
- lines 173-175: materialize_into claude_code sub-section
"""
from __future__ import annotations

import sys
import textwrap
from unittest.mock import patch

import pytest

from autodev.utils.config_stack import ConfigStack, _aot_key, _deep_merge, _is_array_of_tables

# ---------------------------------------------------------------------------
# 1. _is_array_of_tables — True only for non-empty list of dicts
# ---------------------------------------------------------------------------

def test_is_array_of_tables_true():
    assert _is_array_of_tables([{"code": "x"}]) is True


def test_is_array_of_tables_false_plain_list():
    assert _is_array_of_tables([1, 2, 3]) is False


def test_is_array_of_tables_false_empty():
    assert _is_array_of_tables([]) is False


# ---------------------------------------------------------------------------
# 2. _aot_key — prefers code, falls back to id, then None
# ---------------------------------------------------------------------------

def test_aot_key_prefers_code():
    assert _aot_key({"code": "alpha", "id": "beta"}) == "alpha"


def test_aot_key_falls_back_to_id():
    assert _aot_key({"id": "beta"}) == "beta"


def test_aot_key_none_when_neither():
    assert _aot_key({"value": 1}) is None


# ---------------------------------------------------------------------------
# 3. _deep_merge — AoT item with key=None is appended (not merged)
# ---------------------------------------------------------------------------

def test_deep_merge_aot_keyless_item_appended():
    base = {"items": [{"code": "x", "v": 1}]}
    override = {"items": [{"v": 99}]}  # no code/id
    result = _deep_merge(base, override)
    assert len(result["items"]) == 2  # appended, not merged
    assert result["items"][0]["code"] == "x"
    assert result["items"][1]["v"] == 99


# ---------------------------------------------------------------------------
# 4. _deep_merge — plain list (non-AoT) is concatenated
# ---------------------------------------------------------------------------

def test_deep_merge_plain_list_concatenated():
    base = {"tags": ["a", "b"]}
    override = {"tags": ["c"]}
    result = _deep_merge(base, override)
    assert result["tags"] == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# 5. _deep_merge — list vs dict mismatch: override wins (scalar path)
# ---------------------------------------------------------------------------

def test_deep_merge_list_vs_dict_mismatch_override_wins():
    base = {"cfg": {"nested": True}}
    override = {"cfg": [1, 2, 3]}  # override is a plain list, base is dict
    result = _deep_merge(base, override)
    assert result["cfg"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 6. ConfigStack.get — missing key returns supplied default
# ---------------------------------------------------------------------------

def test_config_stack_get_missing_key_returns_default(tmp_path):
    stack = ConfigStack(repo_path=str(tmp_path)).load()
    assert stack.get("nonexistent_key", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# 7. ConfigStack.data — property returns merged dict
# ---------------------------------------------------------------------------

def test_config_stack_data_property(tmp_path):
    stack = ConfigStack(runtime={"foo": "bar"}).load()
    assert isinstance(stack.data, dict)
    assert stack.data.get("foo") == "bar"


# ---------------------------------------------------------------------------
# 8. ConfigStack — empty runtime layer doesn't mark layer as loaded
# ---------------------------------------------------------------------------

def test_runtime_empty_layer_not_marked_loaded(tmp_path):
    stack = ConfigStack(repo_path=str(tmp_path), runtime={}).load()
    runtime_layer = stack.layers[3]
    assert runtime_layer["loaded"] is False
    assert runtime_layer["keys_count"] == 0


# ---------------------------------------------------------------------------
# 9. ConfigStack — runtime layer with data is marked loaded
# ---------------------------------------------------------------------------

def test_runtime_nonempty_layer_marked_loaded(tmp_path):
    stack = ConfigStack(repo_path=str(tmp_path), runtime={"x": 1}).load()
    runtime_layer = stack.layers[3]
    assert runtime_layer["loaded"] is True
    assert runtime_layer["keys_count"] == 1


# ---------------------------------------------------------------------------
# 10. _load_toml — tomllib=None raises RuntimeError
# ---------------------------------------------------------------------------

def test_load_toml_raises_when_tomllib_none(tmp_path):
    """If tomllib is unavailable and a config file exists, RuntimeError is raised."""
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[section]\nkey = 1\n", encoding="utf-8")

    import autodev.utils.config_stack as cs_mod

    with patch.object(cs_mod, "tomllib", None):
        from autodev.utils.config_stack import _load_toml
        with pytest.raises(RuntimeError, match="tomllib"):
            _load_toml(cfg_file)


# ---------------------------------------------------------------------------
# 11. materialize_into — claude_code sub-section applied
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib stdlib requires 3.11+")
def test_materialize_into_claude_code_section(tmp_path):
    autodev_dir = tmp_path / ".autodev"
    autodev_dir.mkdir()
    (autodev_dir / "config.toml").write_text(
        textwrap.dedent("""\
        [claude_code]
        timeout_seconds = 77
        """),
        encoding="utf-8",
    )
    from autodev.config import FactoryConfig
    cfg = FactoryConfig()
    stack = ConfigStack(repo_path=str(tmp_path)).load()
    stack.materialize_into(cfg)
    # claude_code.timeout_seconds must have been applied
    assert cfg.claude_code.timeout_seconds == 77
