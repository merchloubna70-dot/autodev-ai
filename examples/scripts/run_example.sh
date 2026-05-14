#!/usr/bin/env bash
# Usage: bash examples/scripts/run_example.sh <EXAMPLE_DIR>
# Example: bash examples/scripts/run_example.sh 01-mdlines
set -euo pipefail

EXAMPLE=${1:?Usage: run_example.sh <EXAMPLE_DIR>}

autodev deliver-project \
  --repo-path /tmp/autodev-example-"$EXAMPLE" \
  --project-brief examples/"$EXAMPLE"/brief.md \
  --from-scratch true \
  --mode dry-run \
  --executor auto \
  --allow-mock-executor true
