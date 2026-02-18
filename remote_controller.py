"""Remote Controller – Thin CLI client for the Vision VM Control API.

Communicates with the Control API running inside the VM to navigate
the browser, query status, and reset capture regions.
"""

import argparse
import requests
import sys
from typing import Optional

# ── Configuration ────────────────────────────────────────────────────────────

DEFAULT_URL: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VM_HOST: str = "localhost"
CONTROL_PORT: int = 8001

# ── API Client ───────────────────────────────────────────────────────────────

def navigate(url: str, host: str = VM_HOST, port: int = CONTROL_PORT) -> bool:
    """Request the VM to navigate to a specific URL."""
    try:
        endpoint = f"http://{host}:{port}/browser/navigate"
        payload = {"url": url, "mode": "theater"}
        resp = requests.post(endpoint, json=payload, timeout=10.0)
        resp.raise_for_status()
        print(f"[CTRL] Navigation triggered: {url}")
        return True
    except Exception as e:
        print(f"[CTRL] Navigation failed: {e}")
        return False

def get_status(host: str = VM_HOST, port: int = CONTROL_PORT) -> Optional[dict]:
    """Query the VM Control API for status and telemetry."""
    try:
        endpoint = f"http://{host}:{port}/status"
        resp = requests.get(endpoint, timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[CTRL] Status query failed: {e}")
        return None

def reset_roi(host: str = VM_HOST, port: int = CONTROL_PORT) -> bool:
    """Reset the capture ROI to full-screen (1280x720)."""
    try:
        endpoint = f"http://{host}:{port}/sensor/region"
        payload = {"top": 0, "left": 0, "width": 1280, "height": 720}
        resp = requests.post(endpoint, json=payload, timeout=5.0)
        resp.raise_for_status()
        print("[CTRL] ROI reset to 1280x720.")
        return True
    except Exception as e:
        print(f"[CTRL] ROI reset failed: {e}")
        return False

# ── CLI Entrypoint ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Vision VM Remote Controller Client")
    parser.add_argument("url", nargs="?", default=None, help="YouTube URL to play")
    parser.add_argument("--ping", action="store_true", help="Get VM status")
    parser.add_argument("--reset", action="store_true", help="Reset capture ROI")
    parser.add_argument("--host", default=VM_HOST, help="VM hostname")
    parser.add_argument("--port", type=int, default=CONTROL_PORT, help="Control API port")

    args = parser.parse_args()

    if args.ping:
        status = get_status(args.host, args.port)
        if status:
            region = status.get("capture_region", {})
            video = status.get("video", {})
            print(f"VM STATUS: {status.get('status')}")
            print(f"  FPS: {status.get('fps', 0.0):.1f}")
            print(f"  Clients: {status.get('active_clients', 0)}")
            print(f"  ROI: {region.get('left')},{region.get('top')} {region.get('width')}x{region.get('height')}")
            print(f"  Time: {video.get('current_time', 0.0):.2f}s / {video.get('duration', 0.0):.2f}s")
            print(f"  State: {video.get('status', 'unknown')}")
        return

    if args.reset:
        reset_roi(args.host, args.port)
        return

    target_url = args.url if args.url else DEFAULT_URL
    navigate(target_url, args.host, args.port)

if __name__ == "__main__":
    main()
