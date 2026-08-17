#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DC_HOME="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="$(cd "${DC_HOME}/.." && pwd)"
export DIAGNOSTIC_CLANK_HOME="${DIAGNOSTIC_CLANK_HOME:-${DC_HOME}}"
export PYTHONPATH="${REPO_ROOT}/clank-runtime/src:${REPO_ROOT}/clank-desktop/src:${PYTHONPATH:-}"
PY="${DIAGNOSTIC_PYTHON:-python3}"
MODE="${1:-${DIAGNOSTIC_MODE:-inbox}}"
export DIAGNOSTIC_MODE="${MODE}"
LOG_DIR="${DIAGNOSTIC_CLANK_HOME}/logs"; mkdir -p "${LOG_DIR}"
echo "[launch.command] home=${DIAGNOSTIC_CLANK_HOME} mode=${MODE} python=${PY}" | tee -a "${LOG_DIR}/launcher.log"
exec "${PY}" "${DC_HOME}/launcher/common/preflight.py" "${MODE}"
