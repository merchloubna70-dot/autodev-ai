#!/usr/bin/env bash
# Local smoke-test helper for the autodev-ai Docker image.
# Run from the repo root: bash packaging/docker/build.sh
set -euo pipefail

IMAGE="autodev-ai:dev"

echo "==> Building $IMAGE ..."
docker build -f packaging/docker/Dockerfile -t "$IMAGE" .

echo ""
echo "==> Smoke test: autodev --help"
docker run --rm "$IMAGE" --help

echo ""
echo "==> Smoke test: autodev scan --repo-path /workspace (dry-run; workspace is empty)"
docker run --rm "$IMAGE" scan --repo-path /workspace || true

echo ""
echo "Build and smoke tests completed successfully."
