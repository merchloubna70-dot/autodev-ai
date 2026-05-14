#!/usr/bin/env bash
# release_preflight.sh — one-shot pre-tag gate for autodev-ai
#
# Runs the same checks as CI + release_readiness_gate against the local tree.
# Exits non-zero on the first failure. Run this BEFORE `git tag v*` to catch
# the kinds of drift that R11 surfaced post-tag (mypy override mismatch,
# workflow extras drift, Info.plist version lag).
#
# Usage:
#   scripts/release_preflight.sh                       # use current PATH python
#   PYBIN=~/autodev-r11-venv/bin/python scripts/release_preflight.sh
#
# Environment:
#   PYBIN        — python interpreter to use (default: python3)
#   SKIP_BUILD   — set to 1 to skip wheel/sdist build + twine check
set -euo pipefail

PYBIN="${PYBIN:-python3}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }

step "1/8  python interpreter"
"$PYBIN" --version || fail "PYBIN=$PYBIN not executable"

step "2/8  ruff check"
"$PYBIN" -m ruff check . || fail "ruff"

step "3/8  mypy (strict, no --ignore-missing-imports)"
"$PYBIN" -m mypy src/autodev || fail "mypy strict"

step "4/8  pytest (with coverage)"
"$PYBIN" -m pytest -q --cov=src/autodev --cov-report=json --cov-report=term --tb=short \
  || fail "pytest"

step "5/8  coverage_gate --strict"
"$PYBIN" scripts/coverage_gate.py --strict || fail "coverage gate"

step "6/8  release_readiness_gate --strict-rc (most stringent mode)"
"$PYBIN" -m autodev.release_readiness_gate --strict-rc || fail "release readiness gate"

step "7/8  version-drift cross-check"
PYPROJECT_VER=$(grep -E '^version = ' pyproject.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
MODULE_VER=$("$PYBIN" -c 'import autodev; print(autodev.__version__)')
PLIST_VER=$(grep -A1 'CFBundleShortVersionString' packaging/desktop/autodev-ai.app/Contents/Info.plist | tail -1 | sed -E 's/.*<string>([^<]+)<\/string>.*/\1/')
echo "  pyproject : $PYPROJECT_VER"
echo "  module    : $MODULE_VER"
echo "  Info.plist: $PLIST_VER"
if [ "$PYPROJECT_VER" != "$MODULE_VER" ] || [ "$PYPROJECT_VER" != "$PLIST_VER" ]; then
  fail "version drift across pyproject/module/Info.plist — re-pip-install -e . after bumping pyproject + bump Info.plist"
fi

if [ "${SKIP_BUILD:-0}" != "1" ]; then
  step "8/8  build + twine check"
  rm -rf dist/
  "$PYBIN" -m build || fail "build"
  "$PYBIN" -m twine check dist/* || fail "twine"
else
  step "8/8  build + twine check  [SKIPPED via SKIP_BUILD=1]"
fi

printf '\n\033[1;32mALL CHECKS PASSED — safe to tag %s\033[0m\n' "$PYPROJECT_VER"
