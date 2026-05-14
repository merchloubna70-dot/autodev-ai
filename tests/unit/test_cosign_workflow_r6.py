"""R6 — Cosign keyless signing workflow structure tests.

Validates that docker-publish.yml has all the pieces required for
Sigstore keyless signing:
  - id-token: write permission
  - sigstore/cosign-installer step
  - cosign sign step with COSIGN_EXPERIMENTAL env var
  - build step has an id so its digest output can be referenced
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

WORKFLOW_PATH = (
    pathlib.Path(__file__).parent.parent.parent
    / ".github"
    / "workflows"
    / "docker-publish.yml"
)


@pytest.fixture(scope="module")
def workflow() -> dict:
    """Load and parse docker-publish.yml once for all tests in this module."""
    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    return yaml.safe_load(raw)


@pytest.fixture(scope="module")
def publish_job(workflow: dict) -> dict:
    """Return the 'publish' job definition."""
    jobs = workflow.get("jobs", {})
    assert "publish" in jobs, "Expected a 'publish' job in docker-publish.yml"
    return jobs["publish"]


@pytest.fixture(scope="module")
def publish_steps(publish_job: dict) -> list[dict]:
    steps = publish_job.get("steps", [])
    assert steps, "publish job has no steps"
    return steps


# ---------------------------------------------------------------------------
# Permission checks
# ---------------------------------------------------------------------------


class TestPermissions:
    def test_id_token_write_present(self, publish_job: dict) -> None:
        """id-token: write is required for OIDC-based keyless signing."""
        perms = publish_job.get("permissions", {})
        assert perms.get("id-token") == "write", (
            "publish job must have 'id-token: write' under permissions for "
            "Sigstore Fulcio OIDC authentication"
        )

    def test_packages_write_still_present(self, publish_job: dict) -> None:
        """Ensure the original packages: write permission was not removed."""
        perms = publish_job.get("permissions", {})
        assert perms.get("packages") == "write", (
            "publish job must retain 'packages: write' permission to push to GHCR"
        )

    def test_contents_read_still_present(self, publish_job: dict) -> None:
        """Ensure the original contents: read permission was not removed."""
        perms = publish_job.get("permissions", {})
        assert perms.get("contents") == "read", (
            "publish job must retain 'contents: read' permission"
        )


# ---------------------------------------------------------------------------
# Step checks
# ---------------------------------------------------------------------------


def _find_steps_by(steps: list[dict], key: str, substr: str) -> list[dict]:
    return [s for s in steps if substr in str(s.get(key, ""))]


class TestCosignInstallerStep:
    def test_cosign_installer_step_exists(self, publish_steps: list[dict]) -> None:
        """sigstore/cosign-installer action must be present."""
        matches = _find_steps_by(publish_steps, "uses", "sigstore/cosign-installer")
        assert matches, (
            "Expected a step using 'sigstore/cosign-installer' in the publish job"
        )

    def test_cosign_installer_version_v3(self, publish_steps: list[dict]) -> None:
        """Pinned to v3 (latest stable major at time of writing)."""
        matches = _find_steps_by(publish_steps, "uses", "sigstore/cosign-installer@v3")
        assert matches, (
            "cosign-installer step should use @v3 pin "
            "(sigstore/cosign-installer@v3)"
        )


class TestCosignSignStep:
    def test_sign_step_exists(self, publish_steps: list[dict]) -> None:
        """A step that runs 'cosign sign' must be present."""
        sign_steps = [
            s
            for s in publish_steps
            if "run" in s and "cosign sign" in str(s["run"])
        ]
        assert sign_steps, (
            "Expected a step with 'cosign sign' in its run script"
        )

    def test_sign_step_uses_yes_flag(self, publish_steps: list[dict]) -> None:
        """cosign sign must pass --yes to avoid interactive prompts in CI."""
        sign_steps = [
            s
            for s in publish_steps
            if "run" in s and "cosign sign" in str(s["run"])
        ]
        assert any("--yes" in str(s["run"]) for s in sign_steps), (
            "cosign sign step must include --yes to suppress interactive confirmation"
        )

    def test_sign_step_references_build_digest(self, publish_steps: list[dict]) -> None:
        """The sign command must reference steps.build.outputs.digest."""
        sign_steps = [
            s
            for s in publish_steps
            if "run" in s and "cosign sign" in str(s["run"])
        ]
        assert any(
            "steps.build.outputs.digest" in str(s["run"]) for s in sign_steps
        ), (
            "cosign sign must reference ${{ steps.build.outputs.digest }} "
            "so it signs the exact pushed digest, not a mutable tag"
        )

    def test_cosign_experimental_env_set(self, publish_steps: list[dict]) -> None:
        """COSIGN_EXPERIMENTAL=true enables keyless (Fulcio OIDC) mode."""
        sign_steps = [
            s
            for s in publish_steps
            if "run" in s and "cosign sign" in str(s["run"])
        ]
        assert any(
            str(s.get("env", {}).get("COSIGN_EXPERIMENTAL", "")).lower() in ("true", "1")
            for s in sign_steps
        ), (
            "cosign sign step must set COSIGN_EXPERIMENTAL=true (or 1) to "
            "activate keyless Sigstore signing mode"
        )


class TestBuildStepId:
    def test_build_step_has_id(self, publish_steps: list[dict]) -> None:
        """The docker buildx push step must have id: build so digest is accessible."""
        build_steps = [
            s
            for s in publish_steps
            if "uses" in s and "docker/build-push-action" in str(s["uses"])
            and s.get("with", {}).get("push") is True
        ]
        assert build_steps, "Could not find a build-push-action step with push: true"
        assert any(s.get("id") == "build" for s in build_steps), (
            "The docker/build-push-action push step must have 'id: build' "
            "so that steps.build.outputs.digest is available to the cosign step"
        )


# ---------------------------------------------------------------------------
# YAML sanity
# ---------------------------------------------------------------------------


class TestYamlSanity:
    def test_workflow_parses_cleanly(self) -> None:
        """The workflow file must be valid YAML (no syntax errors)."""
        raw = WORKFLOW_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw)
        assert isinstance(parsed, dict), "Parsed YAML should be a mapping"

    def test_workflow_has_on_push_tags(self, workflow: dict) -> None:
        """Workflow must still be triggered on tag push.

        Note: PyYAML parses the bare ``on`` YAML key as Python ``True``
        (a reserved word in YAML 1.1). We look for the key under both
        ``True`` and the string ``"on"`` for robustness.
        """
        on_section = workflow.get(True, workflow.get("on", {})) or {}
        push_section = on_section.get("push", {}) or {}
        tags = push_section.get("tags", []) or []
        assert any("v*" in t for t in tags), (
            "Workflow must trigger on 'v*.*.*' tag push"
        )
