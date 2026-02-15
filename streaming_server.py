"""Lossless Streaming Sensor – PNG-over-TCP server.

Captures display :99 via mss, encodes each frame as lossless PNG
using OpenCV, and streams them to connected TCP clients on port 5555.

Wire protocol (per frame):
  [8 bytes] – payload length as unsigned 64-bit big-endian integer
  [N bytes] – raw PNG image data
"""

import os
import socket
import struct
import threading
import time
from typing import List

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

def capture_png(sct: mss.mss, monitor: dict) -> bytes:
    """Grab a single frame and return lossless PNG bytes via OpenCV."""
    frame = sct.grab(monitor)
    # mss returns BGRA; convert to a NumPy array and drop the alpha channel
    img: np.ndarray = np.array(frame, dtype=np.uint8)
    bgr: np.ndarray = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    success, png_buf = cv2.imencode(".png", bgr, PNG_PARAMS)
    if not success:
        raise RuntimeError("cv2.imencode failed to produce PNG")
    return png_buf.tobytes()


# ── Client handler ───────────────────────────────────────────────────────────

def handle_client(
    conn: socket.socket,
    addr: tuple,
    sct: mss.mss,
    monitor: dict,
) -> None:
    """Stream PNG frames to a single client until disconnect."""
    print(f"[STREAM] Client connected: {addr}", flush=True)
    interval: float = 1.0 / TARGET_FPS

    try:
        while True:
            t0: float = time.monotonic()

            png_data: bytes = capture_png(sct, monitor)
            header: bytes = struct.pack(HEADER_FMT, len(png_data))
            conn.sendall(header + png_data)

            elapsed: float = time.monotonic() - t0
            sleep_time: float = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    except (BrokenPipeError, ConnectionResetError, OSError):
        print(f"[STREAM] Client disconnected: {addr}", flush=True)
    finally:
        conn.close()


# ── Server entry ─────────────────────────────────────────────────────────────

def serve() -> None:
    """Start the TCP streaming server."""
    with mss.mss(display=DISPLAY) as sct:
        monitor: dict = sct.monitors[0]
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
                    args=(conn, addr, sct, monitor),
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
