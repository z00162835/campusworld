#!/usr/bin/env bash
set -euo pipefail

# Run from repository root:
#   ./scripts/run_f10_pg_integration_tests.sh
#
# This command enforces:
# - campusworld conda env
# - backend pytest config
# - serial execution to reduce lock contention

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is required but not found in PATH" >&2
  exit 1
fi

conda run -n campusworld pytest \
  backend/tests/api/test_f10_postgres_integration_filters.py \
  -m postgres_integration \
  -n 0 \
  -q
