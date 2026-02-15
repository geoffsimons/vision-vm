#!/usr/bin/env bash
set -euo pipefail

# ── X11 lock file cleanup ───────────────────────────────────────────────────
# Removes stale X server lock files from a previous run so Xvfb can bind :99
# without a "Display already in use" error.

rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

echo "[MAINTENANCE] Cleared X11 lock files for display 99."

# ── Chrome profile lock cleanup ──────────────────────────────────────────────
# Removes stale lock files left behind by previous container runs or hostname
# changes, allowing Chrome to start cleanly with the persisted profile.

CHROME_DIR="${CHROME_USER_DATA:-/chrome-data}"

find "$CHROME_DIR" -name 'Singleton*' -delete 2>/dev/null || true
find "$CHROME_DIR" -name 'lock' -delete 2>/dev/null || true
find "$CHROME_DIR" -name '.parentlock' -delete 2>/dev/null || true

echo "[MAINTENANCE] Stale Chrome locks cleared."

# ── Chrome exit-state reset ──────────────────────────────────────────────────
# Patches both the profile-level Preferences and the browser-level Local State
# so Chrome believes it shut down cleanly, suppressing all restoration bubbles.

PATCHED=0

for TARGET in "Preferences" "Local State"; do
    MATCH=$(find "$CHROME_DIR" -name "$TARGET" 2>/dev/null | head -n 1)
    if [ -n "$MATCH" ]; then
        sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/g' "$MATCH"
        sed -i 's/"exited_cleanly":false/"exited_cleanly":true/g' "$MATCH"
        PATCHED=$((PATCHED + 1))
    fi
done

if [ "$PATCHED" -gt 0 ]; then
    echo "[MAINTENANCE] Force-cleared Chrome crash state."
else
    echo "[MAINTENANCE] No profile files found; skipping exit-state reset."
fi
