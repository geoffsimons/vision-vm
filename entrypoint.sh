#!/usr/bin/env bash
set -euo pipefail

# ── D-Bus session ────────────────────────────────────────────────────────────
eval "$(dbus-launch --sh-syntax)"
export DBUS_SESSION_BUS_ADDRESS

# ── Xvfb (virtual framebuffer on :99) ───────────────────────────────────────
Xvfb :99 -screen 0 1920x1080x24 &
sleep 5

export DISPLAY=:99

# ── VNC server ────────────────────────────────────────────────────────────────
x11vnc -display :99 -forever -nopw -listen 0.0.0.0 -rfbport 5900 &

# ── Fluxbox (window manager) ─────────────────────────────────────────────────
fluxbox &
sleep 1

# ── Google Chrome ────────────────────────────────────────────────────────────
google-chrome-stable \
    --no-sandbox \
    --disable-dev-shm-usage \
    --start-maximized \
    --remote-debugging-port=9222 \
    --user-data-dir="$CHROME_USER_DATA" \
    --no-first-run \
    --no-default-browser-check \
    --password-store=basic \
    "https://www.youtube.com" &
sleep 3

# ── Hand off to capture script ───────────────────────────────────────────────
exec python /app/capture_heartbeat.py
