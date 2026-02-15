#!/usr/bin/env bash
# setup_host.sh – Bootstrap the Mac-side Python environment.
#
# Creates a .venv, installs project dependencies from requirements.txt,
# and downloads the Playwright Chromium browser binary.
#
# Usage:
#   chmod +x setup_host.sh
#   ./setup_host.sh
set -euo pipefail

VENV_DIR=".venv"

echo "[setup] Creating Python venv in ${VENV_DIR}/ …"
python3 -m venv "${VENV_DIR}"

echo "[setup] Activating venv …"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "[setup] Installing requirements …"
pip install --upgrade pip
pip install -r requirements.txt

echo "[setup] Installing Playwright Chromium …"
playwright install chromium

echo ""
echo "Done.  Activate the environment with:"
echo "  source ${VENV_DIR}/bin/activate"
