"""Coverage tests for autodev/utils/json_io.py (51% → target 90%+).

Uncovered branches (from coverage.json):
- lines 15-19: _default Enum/isoformat/TypeError paths
- lines 47-56: read_jsonl (existing file, blank lines, multiple entries)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum

import pytest
from pydantic import BaseModel

from autodev.utils.json_io import (
    _default,
    append_jsonl,
    dumps,
    read_json,
    read_jsonl,
    write_json,
)

# ---------------------------------------------------------------------------
# 1. _default — Enum produces .value
# ---------------------------------------------------------------------------

class _Color(Enum):
    RED = "red"
    BLUE = "blue"


def test_default_enum_returns_value():
    result = _default(_Color.RED)
    assert result == "red"


# ---------------------------------------------------------------------------
# 2. _default — datetime-like object calls .isoformat()
# ---------------------------------------------------------------------------

def test_default_isoformat_called():
    dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = _default(dt)
    assert "2024-01-15" in result


# ---------------------------------------------------------------------------
# 3. _default — unserializable type raises TypeError
# ---------------------------------------------------------------------------

def test_default_unserializable_raises_type_error():
    class _Blob:
        pass

    with pytest.raises(TypeError, match="unserializable"):
        _default(_Blob())


# ---------------------------------------------------------------------------
# 4. _default — pydantic BaseModel is serialized to dict
# ---------------------------------------------------------------------------

class _SampleModel(BaseModel):
    name: str
    count: int


def test_default_pydantic_model_serialized():
    m = _SampleModel(name="hello", count=42)
    result = _default(m)
    assert isinstance(result, dict)
    assert result["name"] == "hello"
    assert result["count"] == 42


# ---------------------------------------------------------------------------
# 5. dumps — end-to-end with enum and datetime inside a dict
# ---------------------------------------------------------------------------

def test_dumps_with_enum_and_datetime():
    payload = {"color": _Color.BLUE, "ts": datetime(2024, 6, 1, tzinfo=timezone.utc)}
    out = dumps(payload)
    parsed = json.loads(out)
    assert parsed["color"] == "blue"
    assert "2024-06-01" in parsed["ts"]


# ---------------------------------------------------------------------------
# 6. write_json / read_json — roundtrip including nested parent dir creation
# ---------------------------------------------------------------------------

def test_write_json_creates_parent_dirs(tmp_path):
    target = tmp_path / "a" / "b" / "data.json"
    write_json(target, {"key": 123})
    assert target.exists()
    loaded = read_json(target)
    assert loaded["key"] == 123


# ---------------------------------------------------------------------------
# 7. append_jsonl — creates file, then appends correctly
# ---------------------------------------------------------------------------

def test_append_jsonl_creates_and_appends(tmp_path):
    p = tmp_path / "events.jsonl"
    append_jsonl(p, {"event": "start"})
    append_jsonl(p, {"event": "end"})
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "start"
    assert json.loads(lines[1])["event"] == "end"


# ---------------------------------------------------------------------------
# 8. read_jsonl — missing file returns empty list
# ---------------------------------------------------------------------------

def test_read_jsonl_missing_file_returns_empty(tmp_path):
    result = read_jsonl(tmp_path / "nonexistent.jsonl")
    assert result == []


# ---------------------------------------------------------------------------
# 9. read_jsonl — blank lines in file are skipped
# ---------------------------------------------------------------------------

def test_read_jsonl_skips_blank_lines(tmp_path):
    p = tmp_path / "mixed.jsonl"
    p.write_text('\n{"a": 1}\n\n{"b": 2}\n\n', encoding="utf-8")
    result = read_jsonl(p)
    assert len(result) == 2
    assert result[0] == {"a": 1}
    assert result[1] == {"b": 2}


# ---------------------------------------------------------------------------
# 10. read_jsonl — multiple valid entries returned in order
# ---------------------------------------------------------------------------

def test_read_jsonl_multiple_entries(tmp_path):
    p = tmp_path / "log.jsonl"
    entries = [{"n": i} for i in range(5)]
    for e in entries:
        append_jsonl(p, e)
    result = read_jsonl(p)
    assert [r["n"] for r in result] == list(range(5))
