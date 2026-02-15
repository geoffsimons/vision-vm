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

# ── Chrome exit-state reset ──────────────────────────────────────────────────
# Rewrites the Preferences file so Chrome believes it shut down cleanly,
# suppressing the "Chrome didn't shut down correctly" restoration bubble.

PREFS_FILE=$(find "$CHROME_DIR" -name 'Preferences' -path '*/Default/*' 2>/dev/null | head -n 1)

if [ -n "$PREFS_FILE" ]; then
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/g' "$PREFS_FILE"
    sed -i 's/"exited_cleanly":false/"exited_cleanly":true/g' "$PREFS_FILE"
    echo "[MAINTENANCE] Chrome exit state reset to 'Normal'."
else
    echo "[MAINTENANCE] No Preferences file found; skipping exit-state reset."
fi
