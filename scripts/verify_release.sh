#!/usr/bin/env bash
# verify_release.sh — verify supply-chain provenance for an autodev-x release.
#
# Usage:
#   scripts/verify_release.sh v0.1.0a6
#
# Requires: cosign (https://github.com/sigstore/cosign)
# Optional: slsa-verifier (https://github.com/slsa-framework/slsa-verifier)
#
# Exit codes:
#   0  all available checks passed
#   1  one or more checks failed
#   2  bad usage / missing arguments

set -euo pipefail

CERT_IDENTITY_REGEX="https://github\.com/merchloubna70-dot/autodev-x/.+"
OIDC_ISSUER="https://token.actions.githubusercontent.com"
GHCR_IMAGE_BASE="ghcr.io/merchloubna70-dot/autodev-x"
GITHUB_REPO="merchloubna70-dot/autodev-x"

# ── helpers ──────────────────────────────────────────────────────────────────

usage() {
    echo "Usage: $0 <version-tag>"
    echo "  e.g.: $0 v0.1.0a6"
    exit 2
}

info()    { echo "[INFO]  $*"; }
ok()      { echo "[OK]    $*"; }
warn()    { echo "[WARN]  $*"; }
fail()    { echo "[FAIL]  $*"; }

require_cmd() {
    if ! command -v "$1" &>/dev/null; then
        fail "Required command '$1' not found. Install it and retry."
        exit 1
    fi
}

# ── argument handling ─────────────────────────────────────────────────────────

if [[ $# -eq 0 ]]; then
    usage
fi

if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "verify_release.sh — verify cosign + SLSA provenance for autodev-x releases."
    echo ""
    echo "Usage:"
    echo "  $0 <version-tag>"
    echo ""
    echo "Checks performed:"
    echo "  1. cosign verify on the GHCR Docker image"
    echo "  2. slsa-verifier verify-artifact on the GitHub release wheel (if slsa-verifier is installed)"
    echo ""
    echo "Environment:"
    echo "  COSIGN_EXPERIMENTAL=1  already set internally for keyless verification"
    exit 0
fi

TAG="${1}"
# Strip leading 'v' to get the bare version number used in wheel filenames.
VERSION="${TAG#v}"

# ── pre-flight ────────────────────────────────────────────────────────────────

require_cmd cosign

OVERALL_OK=0  # 0 = all good; 1 = something failed

# ── 1. cosign verify (Docker image) ──────────────────────────────────────────

IMAGE_REF="${GHCR_IMAGE_BASE}:${TAG}"

info "Verifying cosign signature for image: ${IMAGE_REF}"

if COSIGN_EXPERIMENTAL=1 cosign verify \
        --certificate-identity-regexp="${CERT_IDENTITY_REGEX}" \
        --certificate-oidc-issuer="${OIDC_ISSUER}" \
        "${IMAGE_REF}" 2>&1; then
    ok "cosign verify passed for ${IMAGE_REF}"
else
    fail "cosign verify FAILED for ${IMAGE_REF}"
    OVERALL_OK=1
fi

# ── 2. slsa-verifier (GitHub release wheel) ──────────────────────────────────

if command -v slsa-verifier &>/dev/null; then
    WHEEL_NAME="autodev_x-${VERSION}-py3-none-any.whl"
    RELEASE_URL="https://github.com/${GITHUB_REPO}/releases/download/${TAG}/${WHEEL_NAME}"
    PROVENANCE_URL="${RELEASE_URL}.intoto.jsonl"

    TMPDIR_SLSA="$(mktemp -d)"
    trap 'rm -rf "${TMPDIR_SLSA}"' EXIT

    WHEEL_PATH="${TMPDIR_SLSA}/${WHEEL_NAME}"
    PROV_PATH="${TMPDIR_SLSA}/${WHEEL_NAME}.intoto.jsonl"

    info "Downloading wheel for SLSA verification: ${RELEASE_URL}"
    if curl -fsSL -o "${WHEEL_PATH}" "${RELEASE_URL}" \
       && curl -fsSL -o "${PROV_PATH}" "${PROVENANCE_URL}"; then

        info "Running slsa-verifier on ${WHEEL_NAME}"
        if slsa-verifier verify-artifact \
                --provenance-path "${PROV_PATH}" \
                --source-uri "github.com/${GITHUB_REPO}" \
                "${WHEEL_PATH}" 2>&1; then
            ok "slsa-verifier passed for ${WHEEL_NAME}"
        else
            fail "slsa-verifier FAILED for ${WHEEL_NAME}"
            OVERALL_OK=1
        fi
    else
        warn "Could not download wheel/provenance from GitHub Releases — skipping SLSA check."
        warn "  (The release asset may not exist yet for ${TAG})"
    fi
else
    warn "slsa-verifier not installed — skipping SLSA provenance check."
    warn "  Install: https://github.com/slsa-framework/slsa-verifier#installation"
fi

# ── summary ──────────────────────────────────────────────────────────────────

echo ""
if [[ "${OVERALL_OK}" -eq 0 ]]; then
    ok "All available supply-chain checks PASSED for ${TAG}."
else
    fail "One or more supply-chain checks FAILED for ${TAG}."
fi

exit "${OVERALL_OK}"
