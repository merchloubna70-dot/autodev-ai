#!/usr/bin/env bash
# build-universal-mac.sh — Build a universal (arm64 + x86_64) macOS binary.
#
# Requirements:
#   • Two Python installations that match the target architectures:
#       - arm64:  /usr/local/bin/python3  (or wherever Homebrew arm64 Python lives)
#       - x86_64: /usr/local/bin/python3  compiled for x86_64 (e.g. via Rosetta venv)
#     The paths can be overridden with env vars (see below).
#   • Both Pythons must have the autodev package installed (pip install -e .).
#   • Xcode command-line tools (for `lipo`).
#
# Usage:
#   cd packaging/pyinstaller
#   bash build-universal-mac.sh
#
# Output:
#   dist/autodev-universal  — fat binary
#   dist/autodev-arm64      — arm64 slice (kept for debugging)
#   dist/autodev-x64        — x86_64 slice (kept for debugging)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ---------------------------------------------------------------------------
# Configurable Python paths — override with env vars if needed.
# ---------------------------------------------------------------------------
ARM64_PYTHON="${ARM64_PYTHON:-${REPO_ROOT}/.venv-arm64/bin/python}"
X86_PYTHON="${X86_PYTHON:-${REPO_ROOT}/.venv-x64/bin/python}"

check_python() {
    local py="$1"
    local arch="$2"
    if [[ ! -f "${py}" ]]; then
        echo "ERROR: ${arch} Python not found at ${py}" >&2
        echo "       Set ${arch^^}_PYTHON env var to override, e.g.:" >&2
        echo "         ARM64_PYTHON=/opt/homebrew/bin/python3  (native M-series)" >&2
        echo "         X86_PYTHON=<path-to-x86_64-venv>/bin/python" >&2
        return 1
    fi
    local detected
    detected=$(python3 -c "import platform; print(platform.machine())" 2>/dev/null || true)
    echo "    ${arch} Python: ${py}"
}

echo "==> Checking Python installations..."
check_python "${ARM64_PYTHON}" "arm64"
check_python "${X86_PYTHON}" "x86_64"

# ---------------------------------------------------------------------------
# Helper: build one arch slice
# ---------------------------------------------------------------------------
build_slice() {
    local py="$1"
    local target_arch="$2"   # arm64 | x86_64
    local out_name="$3"       # autodev-arm64 | autodev-x64

    echo ""
    echo "==> Building ${target_arch} slice using ${py}..."

    # Install pyinstaller into this venv
    "${py}" -m pip install --quiet pyinstaller

    # Run pyinstaller with target_arch override via env
    "${py}" -m PyInstaller autodev.spec \
        --clean \
        --noconfirm \
        --distpath "./dist-${target_arch}" \
        --workpath "./build-${target_arch}" \
        --log-level WARN

    local slice_bin="${SCRIPT_DIR}/dist-${target_arch}/autodev"
    if [[ ! -f "${slice_bin}" ]]; then
        echo "ERROR: expected slice binary not found: ${slice_bin}" >&2
        exit 1
    fi

    cp "${slice_bin}" "${SCRIPT_DIR}/dist/${out_name}"
    echo "    Slice: $(file "${SCRIPT_DIR}/dist/${out_name}")"
}

# ---------------------------------------------------------------------------
# Create dist/ if it doesn't exist
# ---------------------------------------------------------------------------
mkdir -p "${SCRIPT_DIR}/dist"
cd "${SCRIPT_DIR}"

# ---------------------------------------------------------------------------
# Build both slices
# ---------------------------------------------------------------------------
build_slice "${ARM64_PYTHON}" "arm64" "autodev-arm64"
build_slice "${X86_PYTHON}" "x86_64" "autodev-x64"

# ---------------------------------------------------------------------------
# Combine with lipo
# ---------------------------------------------------------------------------
echo ""
echo "==> Creating universal binary with lipo..."
lipo -create \
    -output "${SCRIPT_DIR}/dist/autodev-universal" \
    "${SCRIPT_DIR}/dist/autodev-arm64" \
    "${SCRIPT_DIR}/dist/autodev-x64"

echo "    $(file "${SCRIPT_DIR}/dist/autodev-universal")"
UNIVERSAL_SIZE=$(du -sh "${SCRIPT_DIR}/dist/autodev-universal" | cut -f1)
echo "    Size  : ${UNIVERSAL_SIZE}"
echo "    SHA256: $(shasum -a 256 "${SCRIPT_DIR}/dist/autodev-universal" | awk '{print $1}')"

# ---------------------------------------------------------------------------
# Smoke test the universal binary
# ---------------------------------------------------------------------------
echo ""
echo "==> Smoke test: dist/autodev-universal --help"
if "${SCRIPT_DIR}/dist/autodev-universal" --help > /dev/null 2>&1; then
    echo "    PASS: --help exited 0"
else
    echo "ERROR: dist/autodev-universal --help failed (exit code $?)" >&2
    exit 1
fi

echo ""
echo "==> Universal build complete."
echo "    Binaries:"
echo "      dist/autodev-arm64       (arm64 slice)"
echo "      dist/autodev-x64         (x86_64 slice)"
echo "      dist/autodev-universal   (fat binary for distribution)"
echo ""
echo "    To remove quarantine attribute before distributing:"
echo "      xattr -dr com.apple.quarantine dist/autodev-universal"
