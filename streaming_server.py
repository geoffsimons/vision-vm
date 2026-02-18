"""Lossless Streaming Sensor – PNG-over-TCP server.

Captures display :99 via mss, encodes each frame as lossless PNG
using OpenCV, and streams them to connected TCP clients on port 5555.

Each client thread opens its own mss display handle to avoid the
'AttributeError: display' crash caused by sharing a single X11
connection across threads.

Wire protocol (per frame):
  [8 bytes] – payload length as unsigned 64-bit big-endian integer
  [N bytes] – raw PNG image data
"""

import json
import os
import socket
import struct
import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional

import cv2
import mss
import numpy as np

# ── Configuration ────────────────────────────────────────────────────────────

HOST: str = "0.0.0.0"
PORT: int = int(os.environ.get("STREAM_PORT", "5555"))
DISPLAY: str = os.environ.get("DISPLAY", ":99")
TARGET_FPS: int = int(os.environ.get("STREAM_FPS", "30"))

HEADER_FMT: str = "!Qd"  # 8-byte length (Q) + 8-byte double (d) for timestamp
HEADER_SIZE: int = struct.calcsize(HEADER_FMT)

# OpenCV PNG compression: 0 = no compression (fastest), 9 = max compression.
# Level 1 gives a good speed/size trade-off for streaming.
PNG_PARAMS: List[int] = [cv2.IMWRITE_PNG_COMPRESSION, 1]

# ── Global State ─────────────────────────────────────────────────────────────

capture_region: Dict[str, any] = {
    "top": 0,
    "left": 0,
    "width": 1280,
    "height": 720,
    "current_time": 0.0,
    "duration": 0.0,
    "is_ended": False,
    "video_status": "playing",
}
region_lock: threading.Lock = threading.Lock()
_last_roi_log: float = 0.0

# Telemetry
current_fps: float = 0.0
active_clients: int = 0
stats_lock: threading.Lock = threading.Lock()


def _get_capture_monitor() -> dict:
    """Return an mss-compatible monitor dict from the current ROI."""
    global _last_roi_log
    with region_lock:
        # mss.grab only wants top, left, width, height
        res = {
            "top": capture_region["top"],
            "left": capture_region["left"],
            "width": capture_region["width"],
            "height": capture_region["height"],
        }

    now = time.monotonic()
    if now - _last_roi_log > 5.0:
        print(f"[DEBUG] Providing ROI to thread: {res}", flush=True)
        _last_roi_log = now
    return res


# ── Frame capture ────────────────────────────────────────────────────────────

def capture_png(sct: mss.mss, monitor: dict) -> Optional[bytes]:
    """Grab a single frame and return lossless PNG bytes via OpenCV.

    Returns *None* if a transient X11 error prevents the grab so the
    caller can skip the frame without tearing down the thread.
    """
    try:
        frame = sct.grab(monitor)
    except Exception as exc:
        print(
            f"[STREAM] Grab failed. Monitor: {monitor}, Error: {exc}",
            flush=True,
        )
        return None

    img: np.ndarray = np.array(frame, dtype=np.uint8)
    bgr: np.ndarray = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    success, png_buf = cv2.imencode(".png", bgr, PNG_PARAMS)
    if not success:
        print("[STREAM] cv2.imencode failed – skipping frame", flush=True)
        return None
    return png_buf.tobytes()


# ── Client handler ───────────────────────────────────────────────────────────

def handle_client(conn: socket.socket, addr: tuple) -> None:
    """Stream PNG frames to a single client until disconnect.

    Each invocation opens its own mss display handle so the X11
    connection is never shared across threads.  The capture region is
    read fresh on every frame so ROI updates take effect immediately.
    """
    global active_clients, current_fps
    with stats_lock:
        active_clients += 1

    print(f"[STREAM] Client connected: {addr}", flush=True)
    interval: float = 1.0 / TARGET_FPS
    f_count: int = 0
    ts_history: Deque[float] = deque(maxlen=30)

    try:
        with mss.mss(display=DISPLAY) as sct:
            print(
                f"[STREAM] Thread {threading.current_thread().name} "
                f"using ROI capture region",
                flush=True,
            )

            monitor = _get_capture_monitor()
            while True:
                t0: float = time.monotonic()

                # Logic Safeguard: Read global ROI every 10 frames
                if f_count % 10 == 0:
                    monitor = _get_capture_monitor()

                png_data: Optional[bytes] = capture_png(sct, monitor)
                if png_data is None:
                    time.sleep(interval)
                    continue

                with region_lock:
                    v_time = capture_region["current_time"]

                header: bytes = struct.pack(HEADER_FMT, len(png_data), v_time)
                conn.sendall(header + png_data)

                # Update Telemetry
                now = time.monotonic()
                ts_history.append(now)
                if len(ts_history) > 1:
                    avg_fps = (len(ts_history) - 1) / (ts_history[-1] - ts_history[0])
                    with stats_lock:
                        current_fps = avg_fps

                f_count += 1
                if f_count % 100 == 0:
                    print(
                        f"[STREAM_TRACE] Thread {threading.current_thread().name} | "
                        f"Client {addr} | Capture ROI: {monitor} | "
                        f"PNG Size: {len(png_data)} bytes",
                        flush=True,
                    )

                elapsed: float = time.monotonic() - t0
                sleep_time: float = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
    except (BrokenPipeError, ConnectionResetError, OSError) as exc:
        print(f"[STREAM] Client {addr} disconnected: {exc}", flush=True)
    except Exception as exc:
        print(f"[STREAM] Unexpected error for {addr}: {exc}", flush=True)
    finally:
        with stats_lock:
            active_clients -= 1
        conn.close()
        print(f"[STREAM] Socket closed for {addr}", flush=True)


# ── Server entry ─────────────────────────────────────────────────────────────

def _run_server() -> None:
    """Internal loop for the streaming server."""
    srv: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(4)

    try:
        while True:
            conn, addr = srv.accept()
            thread = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True,
            )
            thread.start()
    except Exception as exc:
        print(f"[STREAM] Server error: {exc}", flush=True)
    finally:
        srv.close()


def start_stream_server_thread() -> None:
    """Start the TCP streaming server in a background thread."""
    # Quick probe to log and validate the monitor geometry.
    with mss.mss(display=DISPLAY) as probe:
        monitor: dict = probe.monitors[0]

    width: int = monitor["width"]
    height: int = monitor["height"]

    if width <= 0 or height <= 0:
        raise RuntimeError(
            f"Invalid monitor dimensions {width}x{height} – "
            "is Xvfb running on the expected DISPLAY?"
        )

    print(
        f"[STREAM] Starting PNG server thread on {HOST}:{PORT} "
        f"(display={DISPLAY}, {width}x{height})",
        flush=True,
    )

    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()


def serve() -> None:
    """Start the TCP streaming server (blocking)."""
    start_stream_server_thread()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STREAM] Shutting down.", flush=True)


# ── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    serve()
