"""Verify Stream – PNG-over-TCP client with live preview.

Connects to the Vision VM streaming server on localhost:5555, decodes
each PNG frame, and displays it in an OpenCV window with an FPS overlay.

Usage (from the Mac host):
    python verify_stream.py [host] [port]

Press 'q' in the preview window to quit.
"""

import socket
import struct
import sys
import time
from collections import deque
from typing import Deque, Tuple

import cv2
import numpy as np

# ── Configuration ────────────────────────────────────────────────────────────

DEFAULT_HOST: str = "localhost"
DEFAULT_PORT: int = 5555

HEADER_FMT: str = "!Q"
HEADER_SIZE: int = struct.calcsize(HEADER_FMT)

WINDOW_NAME: str = "Vision VM Stream"

# Rolling window for FPS calculation (last N frame timestamps)
FPS_WINDOW: int = 60


# ── Network helpers ──────────────────────────────────────────────────────────

def recv_exact(sock: socket.socket, nbytes: int) -> bytes:
    """Read exactly *nbytes* from *sock*, or raise on disconnect."""
    chunks: list[bytes] = []
    remaining: int = nbytes
    while remaining > 0:
        chunk: bytes = sock.recv(min(remaining, 65536))
        if not chunk:
            raise ConnectionError("Server closed the connection")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_frame(sock: socket.socket) -> bytes:
    """Read one length-prefixed PNG frame from the stream."""
    header: bytes = recv_exact(sock, HEADER_SIZE)
    (length,) = struct.unpack(HEADER_FMT, header)
    return recv_exact(sock, length)


# ── Display ──────────────────────────────────────────────────────────────────

def overlay_fps(frame: np.ndarray, fps: float) -> np.ndarray:
    """Draw the current FPS value onto the top-left corner of *frame*."""
    text: str = f"FPS: {fps:.1f}"
    cv2.putText(
        frame,
        text,
        (10, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )
    return frame


# ── Main loop ────────────────────────────────────────────────────────────────

def run(host: str, port: int) -> None:
    """Connect to the streaming server and display frames."""
    print(f"[VERIFY] Connecting to {host}:{port} …", flush=True)

    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    print("[VERIFY] Connected. Receiving frames …", flush=True)

    timestamps: Deque[float] = deque(maxlen=FPS_WINDOW)

    try:
        while True:
            png_data: bytes = recv_frame(sock)
            now: float = time.monotonic()
            timestamps.append(now)

            # Decode PNG → BGR numpy array
            buf: np.ndarray = np.frombuffer(png_data, dtype=np.uint8)
            frame: np.ndarray = cv2.imdecode(buf, cv2.IMREAD_COLOR)

            if frame is None:
                print("[VERIFY] WARNING: failed to decode frame", flush=True)
                continue

            # Calculate rolling FPS
            fps: float = 0.0
            if len(timestamps) >= 2:
                elapsed: float = timestamps[-1] - timestamps[0]
                if elapsed > 0:
                    fps = (len(timestamps) - 1) / elapsed

            overlay_fps(frame, fps)
            cv2.imshow(WINDOW_NAME, frame)

            # 'q' to quit; waitKey(1) keeps the GUI responsive
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except (ConnectionError, KeyboardInterrupt):
        print("\n[VERIFY] Stream ended.", flush=True)
    finally:
        sock.close()
        cv2.destroyAllWindows()


# ── CLI entrypoint ───────────────────────────────────────────────────────────

def _parse_args() -> Tuple[str, int]:
    """Return (host, port) from positional CLI args."""
    host: str = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    port: int = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
    return host, port


if __name__ == "__main__":
    h, p = _parse_args()
    run(h, p)
