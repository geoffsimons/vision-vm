#!/usr/bin/env bash
set -euo pipefail

# ── Chrome profile lock cleanup ──────────────────────────────────────────────
# Removes stale lock files left behind by previous container runs or hostname
# changes, allowing Chrome to start cleanly with the persisted profile.

CHROME_DIR="${CHROME_USER_DATA:-/chrome-data}"

find "$CHROME_DIR" -name 'Singleton*' -delete 2>/dev/null || true
find "$CHROME_DIR" -name 'lock' -delete 2>/dev/null || true
find "$CHROME_DIR" -name '.parentlock' -delete 2>/dev/null || true

echo "[MAINTENANCE] Stale Chrome locks cleared."
