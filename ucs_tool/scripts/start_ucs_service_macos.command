#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
SERVICE_PATH="${SCRIPT_DIR}/../backend/ucs_service.py"
BASE_URL="${ENZ_UCS_URL:-http://127.0.0.1:8000}"
UI_URL="${BASE_URL}/ui"
LOG_PATH="${SCRIPT_DIR}/enz_ucs_service.log"
CONFIG_PATH="${SCRIPT_DIR}/../config.json"

if [[ ! -f "${SERVICE_PATH}" ]]; then
  echo "Cannot find UCS service:"
  echo "${SERVICE_PATH}"
  read -r "?Press Enter to close..."
  exit 1
fi

cd "${SCRIPT_DIR}/.."

if [[ -z "${ENZ_UCS_EMBEDDING_MODEL:-}" && -f "${CONFIG_PATH}" ]]; then
  if /usr/bin/grep -q '"embedding_enabled"[[:space:]]*:[[:space:]]*true' "${CONFIG_PATH}"; then
    CONFIG_MODEL="$(/usr/bin/awk -F'"' '/"embedding_model"/ {print $4; exit}' "${CONFIG_PATH}")"
    if [[ -n "${CONFIG_MODEL}" ]]; then
      export ENZ_UCS_EMBEDDING_MODEL="${CONFIG_MODEL}"
    fi
  fi
fi

EXPECTED_VERSION="$(awk -F'"' '/^SERVICE_VERSION = / {print $2; exit}' "${SERVICE_PATH}")"
HEALTH_JSON="$(/usr/bin/curl -fsS --max-time 0.5 "${BASE_URL}/health" 2>/dev/null || true)"
if [[ -n "${HEALTH_JSON}" ]]; then
  RUNNING_VERSION="$(printf "%s" "${HEALTH_JSON}" | awk -F'"' '/version/ {for (i=1; i<=NF; i++) if ($i=="version") {print $(i+2); exit}}')"
  if [[ -z "${EXPECTED_VERSION}" || "${RUNNING_VERSION}" == "${EXPECTED_VERSION}" ]]; then
    echo "ENZ UCS service is already running: ${RUNNING_VERSION:-unknown}"
    echo "Opening ${UI_URL}"
    /usr/bin/open "${UI_URL}"
    exit 0
  fi

  echo "Existing ENZ UCS service is ${RUNNING_VERSION:-unknown}; current source is ${EXPECTED_VERSION}."
  echo "Restarting service..."
  /usr/bin/curl -fsS --max-time 1.0 -X POST "${BASE_URL}/api/v1/shutdown" >/dev/null 2>&1 || true
  for _ in {1..20}; do
    if ! /usr/bin/curl -fsS --max-time 0.5 "${BASE_URL}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "${SCRIPT_DIR}/../.venv-ucs/bin/python" ]]; then
    PYTHON_BIN="${SCRIPT_DIR}/../.venv-ucs/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "Python 3 is required but was not found."
    echo "Install Python 3, then run this launcher again."
    read -r "?Press Enter to close..."
    exit 1
  fi
fi

echo "Starting ENZ UCS service in the background with:"
echo "${PYTHON_BIN}"
if [[ -n "${ENZ_UCS_EMBEDDING_MODEL:-}" ]]; then
  echo "Embedding model enabled:"
  echo "${ENZ_UCS_EMBEDDING_MODEL}"
  echo "First startup can take a while while the model loads."
fi
echo
nohup "${PYTHON_BIN}" "${SERVICE_PATH}" >> "${LOG_PATH}" 2>&1 &

WAIT_ATTEMPTS=40
if [[ -n "${ENZ_UCS_EMBEDDING_MODEL:-}" ]]; then
  WAIT_ATTEMPTS=240
fi

for _ in $(seq 1 "${WAIT_ATTEMPTS}"); do
  if /usr/bin/curl -fsS --max-time 0.5 "${BASE_URL}/health" >/dev/null 2>&1; then
    echo "ENZ UCS service is running."
    echo "Opening ${UI_URL}"
    /usr/bin/open "${UI_URL}"
    exit 0
  fi
  sleep 0.25
done

echo "Service did not respond in time. Log:"
echo "${LOG_PATH}"
read -r "?Press Enter to close..."
exit 1
