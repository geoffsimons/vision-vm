#!/usr/bin/env bash
set -euo pipefail

# ── D-Bus session ────────────────────────────────────────────────────────────
eval "$(dbus-launch --sh-syntax)"
export DBUS_SESSION_BUS_ADDRESS

# ── Xvfb (virtual framebuffer on :99) ───────────────────────────────────────
Xvfb :99 -screen 0 1920x1080x24 &
sleep 1

export DISPLAY=:99

# ── Fluxbox (window manager) ─────────────────────────────────────────────────
fluxbox &
sleep 1

# ── Google Chrome ────────────────────────────────────────────────────────────
google-chrome-stable \
    --no-sandbox \
    --disable-dev-shm-usage \
    --start-maximized \
    --remote-debugging-port=9222 \
    "https://www.youtube.com" &
sleep 3

# ── Hand off to capture script ───────────────────────────────────────────────
exec python /app/capture_heartbeat.py
