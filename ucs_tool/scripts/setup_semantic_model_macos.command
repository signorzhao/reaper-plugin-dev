#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
TOOL_DIR="${SCRIPT_DIR}/.."
VENV_DIR="${TOOL_DIR}/.venv-ucs"
MODEL_NAME="${ENZ_UCS_EMBEDDING_MODEL:-sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2}"

cd "${TOOL_DIR}"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install sentence-transformers

echo
echo "Semantic model Python environment is ready:"
echo "${VENV_DIR}/bin/python"
echo
echo "To start with the model in this terminal:"
echo "export ENZ_UCS_EMBEDDING_MODEL=\"${MODEL_NAME}\""
echo "./ucs_tool/scripts/start_ucs_service_macos.command"
echo
read -r "?Press Enter to close..."
