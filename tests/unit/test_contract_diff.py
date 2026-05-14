"""Tests for gates/contract_diff.py and ContractDiffReport schema."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autodev.gates.contract_diff import diff_json_schemas, diff_openapi_specs
from autodev.schemas import ContractDiffReport

FIXTURES = Path(__file__).parent.parent / "fixtures" / "openapi"


@pytest.fixture
def v1():
    return json.loads((FIXTURES / "api_v1.json").read_text())


@pytest.fixture
def v2():
    return json.loads((FIXTURES / "api_v2.json").read_text())


# ---------------------------------------------------------------------------
# diff_openapi_specs: v1 -> v2  (endpoints added, none removed)
# ---------------------------------------------------------------------------

def test_added_endpoints(v1, v2):
    result = diff_openapi_specs(v1, v2)
    assert "POST /users" in result["added_endpoints"]
    assert "GET /admin" in result["added_endpoints"]


def test_removed_endpoints_empty_when_forward(v1, v2):
    result = diff_openapi_specs(v1, v2)
    assert result["removed_endpoints"] == []


def test_no_breaking_change_forward(v1, v2):
    report = ContractDiffReport(
        added_endpoints=diff_openapi_specs(v1, v2)["added_endpoints"],
        removed_endpoints=diff_openapi_specs(v1, v2)["removed_endpoints"],
        changed_endpoints=diff_openapi_specs(v1, v2)["changed_endpoints"],
    )
    assert report.breaking_change is False


# ---------------------------------------------------------------------------
# diff_openapi_specs: v2 -> v1  (endpoints removed => breaking)
# ---------------------------------------------------------------------------

def test_removed_endpoints_nonempty_when_backward(v1, v2):
    result = diff_openapi_specs(v2, v1)
    assert len(result["removed_endpoints"]) > 0


def test_breaking_change_when_backward(v1, v2):
    result = diff_openapi_specs(v2, v1)
    report = ContractDiffReport(
        added_endpoints=result["added_endpoints"],
        removed_endpoints=result["removed_endpoints"],
        changed_endpoints=result["changed_endpoints"],
    )
    assert report.breaking_change is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_specs():
    result = diff_openapi_specs({}, {})
    assert result["added_endpoints"] == []
    assert result["removed_endpoints"] == []
    assert result["changed_endpoints"] == []
    report = ContractDiffReport(**result)
    assert report.breaking_change is False


def test_missing_paths_key():
    result = diff_openapi_specs({"info": "x"}, {"info": "y"})
    assert result["added_endpoints"] == []
    assert result["removed_endpoints"] == []


def test_identical_specs(v1):
    result = diff_openapi_specs(v1, v1)
    assert result["added_endpoints"] == []
    assert result["removed_endpoints"] == []
    report = ContractDiffReport(**result)
    assert report.breaking_change is False


# ---------------------------------------------------------------------------
# diff_json_schemas
# ---------------------------------------------------------------------------

def test_schema_diff_added_field():
    old = {"properties": {"id": {"type": "integer"}}}
    new = {"properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}
    result = diff_json_schemas(old, new)
    assert "name" in result["added_fields"]
    assert result["removed_fields"] == []
    assert result["changed_types"] == []


def test_schema_diff_removed_field():
    old = {"properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}
    new = {"properties": {"id": {"type": "integer"}}}
    result = diff_json_schemas(old, new)
    assert "name" in result["removed_fields"]


def test_schema_diff_changed_type():
    old = {"properties": {"id": {"type": "integer"}}}
    new = {"properties": {"id": {"type": "string"}}}
    result = diff_json_schemas(old, new)
    assert result["changed_types"][0]["field"] == "id"
    assert result["changed_types"][0]["old_type"] == "integer"
    assert result["changed_types"][0]["new_type"] == "string"


def test_breaking_change_from_changed_types():
    report = ContractDiffReport(
        added_endpoints=[],
        removed_endpoints=[],
        changed_endpoints=[
            {"path": "/users", "method": "GET", "added_fields": [], "removed_fields": [], "changed_types": [{"field": "id", "old_type": "integer", "new_type": "string"}]}
        ],
    )
    assert report.breaking_change is True
