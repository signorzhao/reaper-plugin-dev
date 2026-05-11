#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_PATH="${SCRIPT_DIR}/../backend/ucs_service.py"
BASE_URL="${ENZ_UCS_URL:-http://127.0.0.1:8000}"
UI_URL="${BASE_URL}/ui"
LOG_PATH="${SCRIPT_DIR}/enz_ucs_service.log"
CONFIG_PATH="${SCRIPT_DIR}/../config.json"

if [[ ! -f "${SERVICE_PATH}" ]]; then
  echo "Cannot find UCS service: ${SERVICE_PATH}" >&2
  exit 1
fi

cd "${SCRIPT_DIR}/.."

if [[ -z "${ENZ_UCS_EMBEDDING_MODEL:-}" && -f "${CONFIG_PATH}" ]]; then
  if grep -q '"embedding_enabled"[[:space:]]*:[[:space:]]*true' "${CONFIG_PATH}"; then
    CONFIG_MODEL="$(awk -F'"' '/"embedding_model"/ {print $4; exit}' "${CONFIG_PATH}")"
    if [[ -n "${CONFIG_MODEL}" ]]; then
      export ENZ_UCS_EMBEDDING_MODEL="${CONFIG_MODEL}"
    fi
  fi
fi

EXPECTED_VERSION="$(awk -F'"' '/^SERVICE_VERSION = / {print $2; exit}' "${SERVICE_PATH}")"
HEALTH_JSON="$(curl -fsS --max-time 0.5 "${BASE_URL}/health" 2>/dev/null || true)"
if [[ -n "${HEALTH_JSON}" ]]; then
  RUNNING_VERSION="$(printf "%s" "${HEALTH_JSON}" | awk -F'"' '/version/ {for (i=1; i<=NF; i++) if ($i=="version") {print $(i+2); exit}}')"
  if [[ -z "${EXPECTED_VERSION}" || "${RUNNING_VERSION}" == "${EXPECTED_VERSION}" ]]; then
    if command -v open >/dev/null 2>&1; then
      open "${UI_URL}"
    fi
    exit 0
  fi

  curl -fsS --max-time 1.0 -X POST "${BASE_URL}/api/v1/shutdown" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do
    if ! curl -fsS --max-time 0.5 "${BASE_URL}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON_TO_RUN="${PYTHON_BIN}"
elif [[ -x "${SCRIPT_DIR}/../.venv-ucs/bin/python" ]]; then
  PYTHON_TO_RUN="${SCRIPT_DIR}/../.venv-ucs/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_TO_RUN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_TO_RUN="$(command -v python)"
else
  echo "Python 3 is required but was not found." >&2
  exit 1
fi

nohup "${PYTHON_TO_RUN}" "${SERVICE_PATH}" >> "${LOG_PATH}" 2>&1 &

WAIT_ATTEMPTS=40
if [[ -n "${ENZ_UCS_EMBEDDING_MODEL:-}" ]]; then
  WAIT_ATTEMPTS=240
fi

for _ in $(seq 1 "${WAIT_ATTEMPTS}"); do
  if curl -fsS --max-time 0.5 "${BASE_URL}/health" >/dev/null 2>&1; then
    if command -v open >/dev/null 2>&1; then
      open "${UI_URL}"
    fi
    exit 0
  fi
  sleep 0.25
done

echo "Service did not respond in time. Log: ${LOG_PATH}" >&2
exit 1
