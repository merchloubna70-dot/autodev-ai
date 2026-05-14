"""R3-D: Docker base image digest pinning tests (closes F-04).

Verifies that packaging/docker/Dockerfile pins its base image by sha256 digest
rather than a floating tag, and that the companion UPDATE.md guidance exists.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DOCKERFILE = REPO_ROOT / "packaging" / "docker" / "Dockerfile"
UPDATE_MD = REPO_ROOT / "packaging" / "docker" / "UPDATE.md"

# Regex that matches a digest-pinned FROM line, e.g.:
#   FROM python@sha256:abc...  [AS stage]
_FROM_DIGEST_RE = re.compile(
    r"^\s*FROM\s+\S+@sha256:([0-9a-f]+)(\s+AS\s+\S+)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_SHA256_LENGTH = 64  # SHA-256 produces 256 bits = 64 hex chars


def test_dockerfile_exists() -> None:
    """packaging/docker/Dockerfile must be present in the repository."""
    assert DOCKERFILE.exists(), f"Dockerfile not found at {DOCKERFILE}"


def test_dockerfile_from_lines_contain_digest() -> None:
    """Every FROM line in the Dockerfile must use @sha256: digest pinning."""
    content = DOCKERFILE.read_text(encoding="utf-8")
    # Collect all FROM lines (ignoring comment lines)
    from_lines = [
        line.strip()
        for line in content.splitlines()
        if re.match(r"^\s*FROM\s", line, re.IGNORECASE)
        and not line.strip().startswith("#")
    ]
    assert from_lines, "Dockerfile contains no FROM lines"
    for line in from_lines:
        assert "@sha256:" in line, (
            f"FROM line does not contain '@sha256:' digest pin: {line!r}\n"
            "Replace the floating tag with the digest-pinned form, e.g.:\n"
            "  FROM python@sha256:<64-hex-chars> AS builder"
        )


def test_dockerfile_sha256_hash_is_64_hex_chars() -> None:
    """The sha256 digest value in every FROM line must be exactly 64 hex characters."""
    content = DOCKERFILE.read_text(encoding="utf-8")
    matches = _FROM_DIGEST_RE.findall(content)
    assert matches, (
        "No digest-pinned FROM lines found in Dockerfile. "
        "Expected pattern: FROM <image>@sha256:<64-hex-chars>"
    )
    for digest_hex, _alias in matches:
        assert len(digest_hex) == _SHA256_LENGTH, (
            f"SHA-256 digest has {len(digest_hex)} hex chars, expected {_SHA256_LENGTH}: "
            f"{digest_hex!r}"
        )
        assert re.fullmatch(r"[0-9a-f]+", digest_hex, re.IGNORECASE), (
            f"SHA-256 digest contains non-hex characters: {digest_hex!r}"
        )


def test_update_md_exists_and_mentions_digest() -> None:
    """packaging/docker/UPDATE.md must exist and contain the word 'digest'."""
    assert UPDATE_MD.exists(), (
        f"UPDATE.md not found at {UPDATE_MD}. "
        "Create it with instructions for updating the pinned digest."
    )
    content = UPDATE_MD.read_text(encoding="utf-8").lower()
    assert "digest" in content, (
        "UPDATE.md does not mention 'digest'. "
        "The file should explain how to fetch and update the pinned sha256 digest."
    )


def test_both_stages_use_same_digest() -> None:
    """Builder and runtime stages must reference the same digest for cache consistency."""
    content = DOCKERFILE.read_text(encoding="utf-8")
    digests = _FROM_DIGEST_RE.findall(content)
    assert len(digests) >= 2, (
        f"Expected at least 2 digest-pinned FROM lines (builder + runtime), "
        f"found {len(digests)}"
    )
    unique_digests = {d[0] for d in digests}
    assert len(unique_digests) == 1, (
        f"Builder and runtime stages use different digests: {unique_digests}. "
        "Both stages should pin to the same base image digest."
    )


def test_dockerfile_no_floating_python_tag() -> None:
    """The Dockerfile must not contain any un-pinned 'FROM python:3.12-slim' floating tag."""
    content = DOCKERFILE.read_text(encoding="utf-8")
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if re.match(r"^\s*FROM\s+python:3\.12-slim\s*", line, re.IGNORECASE):
            raise AssertionError(
                f"Floating tag found: {line!r}\n"
                "Replace with digest-pinned form: FROM python@sha256:<hash>"
            )
