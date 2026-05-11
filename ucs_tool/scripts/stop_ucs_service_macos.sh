#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${ENZ_UCS_URL:-http://127.0.0.1:8000}"

if curl -fsS --max-time 1.0 -X POST "${BASE_URL}/api/v1/shutdown" >/dev/null 2>&1; then
  echo "ENZ UCS service shutdown requested."
  exit 0
fi

echo "ENZ UCS service is not running, or it did not respond." >&2
exit 1
