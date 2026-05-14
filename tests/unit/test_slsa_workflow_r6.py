"""Policy tests for .github/workflows/slsa.yml — R6 SLSA L3 provenance.

Verifies that the SLSA workflow:
1. Exists and parses as valid YAML.
2. Triggers on tag pushes matching 'v*.*.*'.
3. References the slsa-framework/slsa-github-generator reusable workflow
   (generator_generic_slsa3.yml) for unforgeable L3 provenance.
4. Grants id-token: write in the provenance job (required for OIDC).
5. Wires base64-subjects from the build job's hashes output.
6. Resets top-level permissions to {} (principle of least privilege).
"""
from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).parents[2] / ".github" / "workflows" / "slsa.yml"

SLSA_GENERATOR_PREFIX = "slsa-framework/slsa-github-generator"
SLSA_GENERATOR_WORKFLOW = "generator_generic_slsa3.yml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_slsa_workflow_file_exists():
    """The slsa.yml workflow file must be present."""
    assert WORKFLOW_PATH.exists(), f"Missing: {WORKFLOW_PATH}"


def test_slsa_workflow_yaml_parses():
    """slsa.yml must be valid YAML with a 'jobs' key at the root."""
    data = _load_workflow()
    assert isinstance(data, dict), "YAML root must be a mapping"
    assert "jobs" in data, "Workflow must define at least one job"


def test_slsa_workflow_triggers_on_version_tags():
    """Workflow must fire on push events matching 'v*.*.*' tags."""
    data = _load_workflow()
    on = data.get("on", data.get(True, {}))  # 'on' can parse as True in PyYAML
    push_tags = on.get("push", {}).get("tags", [])
    version_patterns = [t for t in push_tags if "v*" in t]
    assert version_patterns, (
        f"No 'v*.*.*' tag pattern found in on.push.tags; got: {push_tags}"
    )


def test_slsa_top_level_permissions_reset():
    """Top-level permissions must be explicitly reset to {} (empty dict or null).

    SLSA L3 requires the generator job to have minimal permissions; the reusable
    workflow itself grants id-token:write scoped to that job only.
    """
    data = _load_workflow()
    perms = data.get("permissions")
    # {} (empty mapping) or None/null are both acceptable resets
    assert perms == {} or perms is None, (
        f"Top-level permissions must be {{}} or null to reset defaults; got: {perms!r}"
    )


def test_slsa_provenance_job_references_slsa_generator():
    """The provenance job must use the slsa-framework generator_generic_slsa3 reusable workflow."""
    data = _load_workflow()
    jobs = data.get("jobs", {})
    provenance_job = jobs.get("provenance")
    assert provenance_job is not None, "Workflow must contain a 'provenance' job"

    uses = provenance_job.get("uses", "")
    assert SLSA_GENERATOR_PREFIX in uses, (
        f"provenance job 'uses' must reference '{SLSA_GENERATOR_PREFIX}'; got: {uses!r}"
    )
    assert SLSA_GENERATOR_WORKFLOW in uses, (
        f"provenance job 'uses' must reference '{SLSA_GENERATOR_WORKFLOW}'; got: {uses!r}"
    )


def test_slsa_provenance_job_has_id_token_write():
    """The provenance job must declare id-token: write.

    This is the OIDC permission that allows the slsa-github-generator to obtain
    an ephemeral Sigstore certificate — the core of SLSA L3 non-forgeability.
    """
    data = _load_workflow()
    jobs = data.get("jobs", {})
    provenance_job = jobs.get("provenance", {})
    perms = provenance_job.get("permissions", {})
    id_token_perm = perms.get("id-token", "")
    assert id_token_perm == "write", (
        f"provenance job must have 'id-token: write'; got: {id_token_perm!r}"
    )


def test_slsa_provenance_job_wires_base64_subjects_from_build():
    """The provenance job must pass base64-subjects wired from the build job's hashes output."""
    data = _load_workflow()
    jobs = data.get("jobs", {})
    provenance_job = jobs.get("provenance", {})

    with_block = provenance_job.get("with", {})
    base64_subjects = str(with_block.get("base64-subjects", ""))

    # Must reference the build job output named 'hashes'
    assert "build" in base64_subjects, (
        f"base64-subjects must reference needs.build.outputs.hashes; got: {base64_subjects!r}"
    )
    assert "hashes" in base64_subjects, (
        f"base64-subjects must reference needs.build.outputs.hashes; got: {base64_subjects!r}"
    )


def test_slsa_provenance_job_needs_build():
    """The provenance job must declare needs: [build] to ensure artifacts exist first."""
    data = _load_workflow()
    jobs = data.get("jobs", {})
    provenance_job = jobs.get("provenance", {})
    needs = provenance_job.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    assert "build" in needs, (
        f"provenance job must declare 'needs: [build]'; got: {needs!r}"
    )


def test_slsa_build_job_computes_hashes_output():
    """The build job must declare an 'outputs.hashes' field for the provenance job to consume."""
    data = _load_workflow()
    jobs = data.get("jobs", {})
    build_job = jobs.get("build", {})
    outputs = build_job.get("outputs", {})
    assert "hashes" in outputs, (
        f"build job must declare 'outputs.hashes'; got outputs: {list(outputs.keys())}"
    )


def test_slsa_build_job_has_contents_read_permission():
    """The build job should have at most 'contents: read' (not write)."""
    data = _load_workflow()
    jobs = data.get("jobs", {})
    build_job = jobs.get("build", {})
    perms = build_job.get("permissions", {})
    contents_perm = perms.get("contents", "read")
    assert contents_perm == "read", (
        f"build job should have 'contents: read', not 'contents: {contents_perm}'"
    )
