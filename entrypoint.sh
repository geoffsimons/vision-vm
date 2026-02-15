#!/usr/bin/env bash
set -euo pipefail

# ── Cleanup trap ─────────────────────────────────────────────────────────────
# On SIGTERM/SIGINT, remove X11 lock files so the next container start is clean.
cleanup() {
    echo "[SHUTDOWN] Removing X11 lock files for display 99..."
    rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
}
trap cleanup SIGTERM SIGINT

# ── Pre-launch cleanup (must run before Xvfb) ────────────────────────────────
./reset-chrome.sh

# ── D-Bus session ────────────────────────────────────────────────────────────
eval "$(dbus-launch --sh-syntax)"
export DBUS_SESSION_BUS_ADDRESS

# ── Display geometry (from environment, with defaults) ───────────────────────
WIDTH="${WIDTH:-1280}"
HEIGHT="${HEIGHT:-720}"
DEPTH="${DEPTH:-24}"

# ── Xvfb (virtual framebuffer on :99) ───────────────────────────────────────
Xvfb :99 -screen 0 "${WIDTH}x${HEIGHT}x${DEPTH}" &
sleep 5

export DISPLAY=:99

# ── VNC server ────────────────────────────────────────────────────────────────
x11vnc -display :99 -forever -shared -rfbauth ~/.vnc/passwd -listen 0.0.0.0 -rfbport 5900 &

# ── Fluxbox (window manager) ─────────────────────────────────────────────────
fluxbox &
sleep 5

# ── socat CDP relay (external :9222 → Chrome :9223) ─────────────────────────
# Chrome binds its DevTools socket to 127.0.0.1 only.  socat listens on all
# interfaces so the host Mac can reach CDP through the published Docker port.
socat TCP-LISTEN:9222,fork,reuseaddr TCP:127.0.0.1:9223 &

# ── Google Chrome ────────────────────────────────────────────────────────────
google-chrome-stable \
    --remote-debugging-port=9223 \
    --remote-debugging-address=127.0.0.1 \
    --no-sandbox \
    --disable-dev-shm-usage \
    --start-fullscreen \
    --window-size="${WIDTH},${HEIGHT}" \
    --window-position=0,0 \
    --force-device-scale-factor=1 \
    --user-data-dir="$CHROME_USER_DATA" \
    --no-first-run \
    --no-default-browser-check \
    --password-store=basic \
    --disable-session-crashed-bubble \
    --disable-infobars \
    --noerrdialogs \
    "https://www.youtube.com" &
sleep 3

# ── PNG streaming server (TCP :5555, background) ────────────────────────────
python /app/streaming_server.py &

# ── Hand off to capture script ───────────────────────────────────────────────
exec python /app/capture_heartbeat.py
