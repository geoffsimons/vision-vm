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

import os
import socket
import struct
import threading
import time
from typing import List, Optional

import cv2
import mss
import numpy as np

# ── Configuration ────────────────────────────────────────────────────────────

HOST: str = "0.0.0.0"
PORT: int = int(os.environ.get("STREAM_PORT", "5555"))
DISPLAY: str = os.environ.get("DISPLAY", ":99")
TARGET_FPS: int = int(os.environ.get("STREAM_FPS", "30"))

HEADER_FMT: str = "!Q"  # 8-byte unsigned long long, big-endian
HEADER_SIZE: int = struct.calcsize(HEADER_FMT)

# OpenCV PNG compression: 0 = no compression (fastest), 9 = max compression.
# Level 1 gives a good speed/size trade-off for streaming.
PNG_PARAMS: List[int] = [cv2.IMWRITE_PNG_COMPRESSION, 1]


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
            f"[STREAM] Transient capture error: {exc}",
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
    connection is never shared across threads.
    """
    print(f"[STREAM] Client connected: {addr}", flush=True)
    interval: float = 1.0 / TARGET_FPS

    try:
        with mss.mss(display=DISPLAY) as sct:
            monitor: dict = sct.monitors[0]
            print(
                f"[STREAM] Thread {threading.current_thread().name} "
                f"capturing monitor {monitor}",
                flush=True,
            )

            while True:
                t0: float = time.monotonic()

                png_data: Optional[bytes] = capture_png(sct, monitor)
                if png_data is None:
                    # Skip this frame; brief pause to avoid a tight error loop
                    time.sleep(interval)
                    continue

                header: bytes = struct.pack(HEADER_FMT, len(png_data))
                conn.sendall(header + png_data)

                elapsed: float = time.monotonic() - t0
                sleep_time: float = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
    except (BrokenPipeError, ConnectionResetError, OSError) as exc:
        print(f"[STREAM] Client {addr} disconnected: {exc}", flush=True)
    except Exception as exc:
        print(f"[STREAM] Unexpected error for {addr}: {exc}", flush=True)
    finally:
        conn.close()
        print(f"[STREAM] Socket closed for {addr}", flush=True)


# ── Server entry ─────────────────────────────────────────────────────────────

def serve() -> None:
    """Start the TCP streaming server.

    The accept loop runs without holding an mss handle; each client
    thread creates its own inside *handle_client*.
    """
    # Quick probe to log the monitor geometry, then release the handle.
    with mss.mss(display=DISPLAY) as probe:
        monitor: dict = probe.monitors[0]

    print(
        f"[STREAM] Serving PNG frames on {HOST}:{PORT}  "
        f"(display={DISPLAY}, monitor={monitor})",
        flush=True,
    )

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
    except KeyboardInterrupt:
        print("\n[STREAM] Shutting down.", flush=True)
    finally:
        srv.close()


# ── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    serve()
