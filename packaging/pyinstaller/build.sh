#!/usr/bin/env bash
# build.sh — Build a single-file `autodev` binary with PyInstaller.
#
# Usage:
#   cd packaging/pyinstaller
#   bash build.sh
#
# The script is safe to run repeatedly; PyInstaller --clean wipes prior output.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ---------------------------------------------------------------------------
# 1. Activate the project venv (must already exist; created by `uv venv` or
#    `python -m venv .venv` in the repo root).
# ---------------------------------------------------------------------------
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
VENV_ACTIVATE="${REPO_ROOT}/.venv/bin/activate"

if [[ ! -f "${VENV_PYTHON}" ]]; then
    echo "ERROR: venv not found at ${REPO_ROOT}/.venv" >&2
    echo "       Run: python -m venv ${REPO_ROOT}/.venv && source ${VENV_ACTIVATE} && pip install -e ${REPO_ROOT}[all]" >&2
    exit 1
fi

# shellcheck source=/dev/null
source "${VENV_ACTIVATE}"

echo "==> Python: $(which python) ($(python --version))"

# ---------------------------------------------------------------------------
# 2. Install PyInstaller into the venv (dev-only tool; NOT in pyproject.toml).
# ---------------------------------------------------------------------------
echo "==> Installing PyInstaller..."
pip install --quiet pyinstaller

# ---------------------------------------------------------------------------
# 3. Run PyInstaller from the spec file directory so relative paths resolve.
# ---------------------------------------------------------------------------
cd "${SCRIPT_DIR}"

echo "==> Running PyInstaller..."
pyinstaller autodev.spec \
    --clean \
    --noconfirm \
    --distpath ./dist \
    --workpath ./build \
    --log-level WARN

# ---------------------------------------------------------------------------
# 4. Verify the binary was produced.
# ---------------------------------------------------------------------------
BINARY="${SCRIPT_DIR}/dist/autodev"
if [[ ! -f "${BINARY}" ]]; then
    echo "ERROR: expected binary not found: ${BINARY}" >&2
    exit 1
fi

echo ""
echo "==> Build info:"
BINARY_SIZE=$(du -sh "${BINARY}" | cut -f1)
echo "    Size  : ${BINARY_SIZE}"
echo "    SHA256: $(shasum -a 256 "${BINARY}" | awk '{print $1}')"
echo "    Arch  : $(file "${BINARY}")"

# ---------------------------------------------------------------------------
# 5. Smoke test — must exit 0.
# ---------------------------------------------------------------------------
echo ""
echo "==> Smoke test: dist/autodev --help"
if "${BINARY}" --help > /dev/null 2>&1; then
    echo "    PASS: --help exited 0"
else
    echo "ERROR: dist/autodev --help failed (exit code $?)" >&2
    exit 1
fi

echo ""
echo "==> Done. Binary at: ${BINARY}"
