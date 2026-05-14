"""
R6 — SBOM workflow structure tests.

Validates that .github/workflows/sbom.yml is syntactically valid YAML and
contains the expected triggers, jobs, steps, and format coverage.
Does NOT execute the workflow.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

WORKFLOW_PATH = (
    pathlib.Path(__file__).parent.parent.parent
    / ".github"
    / "workflows"
    / "sbom.yml"
)


@pytest.fixture(scope="module")
def workflow() -> dict:
    """Parse sbom.yml once for the entire test module."""
    assert WORKFLOW_PATH.exists(), f"Workflow file not found: {WORKFLOW_PATH}"
    with WORKFLOW_PATH.open() as fh:
        parsed = yaml.safe_load(fh)
    assert isinstance(parsed, dict), "YAML root must be a mapping"
    return parsed


# ---------------------------------------------------------------------------
# Trigger tests
# ---------------------------------------------------------------------------


class TestTriggers:
    def test_push_tag_trigger_present(self, workflow: dict) -> None:
        on = workflow.get("on") or workflow.get(True)  # 'on' can parse as True
        assert on is not None, "Workflow must have an 'on' trigger block"
        push = on.get("push", {}) if isinstance(on, dict) else {}
        assert push, "Workflow must have a 'push' trigger"

    def test_push_tag_pattern(self, workflow: dict) -> None:
        on = workflow.get("on") or workflow.get(True)
        push = on.get("push", {})
        tags = push.get("tags", [])
        assert any("v*.*.*" in t for t in tags), (
            "push trigger must include a 'v*.*.*' tag pattern"
        )

    def test_workflow_dispatch_trigger(self, workflow: dict) -> None:
        on = workflow.get("on") or workflow.get(True)
        assert "workflow_dispatch" in on, (
            "Workflow must support manual dispatch via workflow_dispatch"
        )


# ---------------------------------------------------------------------------
# Permission tests
# ---------------------------------------------------------------------------


class TestPermissions:
    def test_contents_write_permission(self, workflow: dict) -> None:
        perms = workflow.get("permissions", {})
        assert perms.get("contents") == "write", (
            "contents permission must be 'write' to upload release assets"
        )

    def test_id_token_write_permission(self, workflow: dict) -> None:
        perms = workflow.get("permissions", {})
        assert perms.get("id-token") == "write", (
            "id-token permission must be 'write' for future signing support"
        )


# ---------------------------------------------------------------------------
# Job / step structure tests
# ---------------------------------------------------------------------------


class TestJobStructure:
    def _get_sbom_steps(self, workflow: dict) -> list[dict]:
        jobs = workflow.get("jobs", {})
        assert jobs, "Workflow must define at least one job"
        # Accept any job name that looks like the sbom job
        for job_name, job in jobs.items():
            steps = job.get("steps", [])
            if steps:
                return steps
        pytest.fail("No jobs with steps found in workflow")

    def test_checkout_step_present(self, workflow: dict) -> None:
        steps = self._get_sbom_steps(workflow)
        uses_values = [s.get("uses", "") for s in steps]
        assert any("actions/checkout" in u for u in uses_values), (
            "Workflow must check out the repository"
        )

    def test_cyclonedx_sbom_step_present(self, workflow: dict) -> None:
        steps = self._get_sbom_steps(workflow)
        uses_values = [s.get("uses", "") for s in steps]
        assert any(
            "anchore/sbom-action" in u or "CycloneDX/cyclonedx-action" in u
            for u in uses_values
        ), "Workflow must invoke anchore/sbom-action or CycloneDX/cyclonedx-action"

    def test_spdx_format_configured(self, workflow: dict) -> None:
        steps = self._get_sbom_steps(workflow)
        spdx_steps = [
            s
            for s in steps
            if "sbom-action" in s.get("uses", "") or "cyclonedx-action" in s.get("uses", "")
        ]
        formats_declared = []
        for s in spdx_steps:
            with_block = s.get("with", {})
            fmt = with_block.get("format", "")
            output = with_block.get("output-file", "")
            formats_declared.extend([fmt, output])

        combined = " ".join(formats_declared).lower()
        assert "spdx" in combined, (
            "At least one sbom-action step must produce SPDX output"
        )

    def test_cyclonedx_format_configured(self, workflow: dict) -> None:
        steps = self._get_sbom_steps(workflow)
        sbom_steps = [
            s
            for s in steps
            if "sbom-action" in s.get("uses", "") or "cyclonedx-action" in s.get("uses", "")
        ]
        formats_declared = []
        for s in sbom_steps:
            with_block = s.get("with", {})
            fmt = with_block.get("format", "")
            output = with_block.get("output-file", "")
            formats_declared.extend([fmt, output])

        combined = " ".join(formats_declared).lower()
        assert "cyclonedx" in combined or "cdx" in combined, (
            "At least one sbom-action step must produce CycloneDX output"
        )

    def test_release_asset_upload_step_present(self, workflow: dict) -> None:
        steps = self._get_sbom_steps(workflow)
        uses_values = [s.get("uses", "") for s in steps]
        assert any("softprops/action-gh-release" in u for u in uses_values), (
            "Workflow must upload assets to GitHub Release via softprops/action-gh-release"
        )

    def test_release_upload_includes_cdx_json(self, workflow: dict) -> None:
        steps = self._get_sbom_steps(workflow)
        release_steps = [
            s for s in steps if "softprops/action-gh-release" in s.get("uses", "")
        ]
        assert release_steps, "softprops/action-gh-release step must exist"
        files_field = release_steps[0].get("with", {}).get("files", "")
        assert "sbom.cdx.json" in str(files_field), (
            "Release step must list sbom.cdx.json in 'files'"
        )

    def test_release_upload_includes_spdx_json(self, workflow: dict) -> None:
        steps = self._get_sbom_steps(workflow)
        release_steps = [
            s for s in steps if "softprops/action-gh-release" in s.get("uses", "")
        ]
        assert release_steps, "softprops/action-gh-release step must exist"
        files_field = release_steps[0].get("with", {}).get("files", "")
        assert "sbom.spdx.json" in str(files_field), (
            "Release step must list sbom.spdx.json in 'files'"
        )


# ---------------------------------------------------------------------------
# YAML validity (smoke)
# ---------------------------------------------------------------------------


class TestYamlValidity:
    def test_workflow_parses_without_error(self) -> None:
        """Re-parse independently to confirm no side-effects from fixture."""
        with WORKFLOW_PATH.open() as fh:
            result = yaml.safe_load(fh)
        assert result is not None

    def test_workflow_name_is_string(self, workflow: dict) -> None:
        assert isinstance(workflow.get("name"), str), (
            "Workflow 'name' must be a string"
        )
