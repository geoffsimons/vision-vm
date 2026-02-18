"""Verify Stream – PNG-over-TCP client with live preview.

Connects to the Vision VM streaming server on localhost:5555, decodes
each PNG frame, and displays it in an OpenCV window with an FPS overlay.

Usage (from the Mac host):
    python verify_stream.py [host] [port]

Press 'q' in the preview window to quit.
"""

import argparse
import json
import socket
import struct
import sys
import threading
import time
from collections import deque
from typing import Deque, Optional, Tuple

import cv2
import numpy as np

import requests

# ── Configuration ────────────────────────────────────────────────────────────

DEFAULT_HOST: str = "localhost"
DEFAULT_PORT: int = 5555
DEFAULT_CONTROL_PORT: int = 8001

HEADER_FMT: str = "!Qd"  # 8-byte length (Q) + 8-byte double (d) for timestamp
HEADER_SIZE: int = struct.calcsize(HEADER_FMT)

WINDOW_BASE_NAME: str = "Vision VM Stream"


# Rolling window for FPS calculation (last N frame timestamps)
FPS_WINDOW: int = 60

# Global state for status updates
video_duration: float = 0.0
video_status: str = "unknown"
_status_lock: threading.Lock = threading.Lock()


# ── Status Polling ───────────────────────────────────────────────────────────

def poll_status(host: str, port: int) -> None:
    """Periodically query the VM Control API for status."""
    global video_duration, video_status
    while True:
        try:
            url = f"http://{host}:{port}/status"
            resp = requests.get(url, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                video = data.get("video", {})
                with _status_lock:
                    video_duration = float(video.get("duration", 0.0))
                    video_status = video.get("status", "playing")
        except Exception:
            pass
        time.sleep(1.0)


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


def recv_frame(sock: socket.socket) -> Tuple[bytes, float]:
    """Read one length-prefixed PNG frame and its timestamp from the stream."""
    header: bytes = recv_exact(sock, HEADER_SIZE)
    length, timestamp = struct.unpack(HEADER_FMT, header)
    png_data = recv_exact(sock, length)
    return png_data, timestamp


# ── Display ──────────────────────────────────────────────────────────────────

def overlay_diagnostics(
    frame: np.ndarray,
    fps: float,
    size_bytes: int,
    timestamp: float,
) -> np.ndarray:
    """Draw resolution, data size, FPS, and playhead onto *frame*."""
    h: int = frame.shape[0]
    w: int = frame.shape[1]
    size_mb: float = size_bytes / (1024.0 * 1024.0)

    with _status_lock:
        duration = video_duration
        status = video_status

    progress_text = ""
    if duration > 0:
        pct = (timestamp / duration) * 100
        progress_text = f" | Progress: {timestamp:.1f}/{duration:.1f}s ({pct:.1f}%)"

    text: str = (
        f"Res: {w}x{h} | {size_mb:.2f}MB | {fps:.1f} FPS | "
        f"Status: {status}{progress_text}"
    )
    # Black outline for contrast
    cv2.putText(
        frame, text, (10, 36),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA,
    )
    # Green foreground
    cv2.putText(
        frame, text, (10, 36),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA,
    )
    return frame


# ── Main loop ────────────────────────────────────────────────────────────────

def run(host: str, port: int, mgmt_port: int, auto_close: bool) -> None:
    """Connect to the streaming server and display frames."""
    print(f"[VERIFY] Connecting to {host}:{port} …", flush=True)

    # Start status polling thread
    poll_thread = threading.Thread(target=poll_status, args=(host, mgmt_port), daemon=True)
    poll_thread.start()

    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    print("[VERIFY] Connected. Receiving frames …", flush=True)

    timestamps: Deque[float] = deque(maxlen=FPS_WINDOW)
    last_res: str = ""

    try:
        while True:
            png_data, v_time = recv_frame(sock)
            now: float = time.monotonic()
            timestamps.append(now)

            # Decode PNG → BGR numpy array
            buf: np.ndarray = np.frombuffer(png_data, dtype=np.uint8)
            frame: np.ndarray = cv2.imdecode(buf, cv2.IMREAD_COLOR)

            if frame is None:
                print("[VERIFY] WARNING: failed to decode frame", flush=True)
                continue

            # Check for auto-close
            if auto_close:
                with _status_lock:
                    if video_status == "complete":
                        print("[VERIFY] Video complete. Auto-closing...", flush=True)
                        break

            # Calculate rolling FPS
            fps: float = 0.0
            if len(timestamps) >= 2:
                elapsed: float = timestamps[-1] - timestamps[0]
                if elapsed > 0:
                    fps = (len(timestamps) - 1) / elapsed

            # Update window title when the capture resolution changes.
            h: int = frame.shape[0]
            w: int = frame.shape[1]
            current_res: str = f"{w}x{h}"
            if current_res != last_res:
                last_res = current_res
                window_title: str = (
                    f"{WINDOW_BASE_NAME} — Resolution: {current_res}"
                )
                cv2.setWindowTitle(WINDOW_BASE_NAME, window_title)
                print(
                    f"[VERIFY] Capture resolution changed: {current_res}",
                    flush=True,
                )

            overlay_diagnostics(frame, fps, len(png_data), v_time)
            cv2.imshow(WINDOW_BASE_NAME, frame)

            # 'q' to quit; waitKey(1) keeps the GUI responsive
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except (ConnectionError, KeyboardInterrupt):
        print("\n[VERIFY] Stream ended.", flush=True)
    finally:
        sock.close()
        cv2.destroyAllWindows()


# ── CLI entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    """Parse args and run the verification client."""
    parser = argparse.ArgumentParser(
        description="Verify Stream – PNG-over-TCP client with live preview.",
    )
    parser.add_argument(
        "host",
        nargs="?",
        default=DEFAULT_HOST,
        help="Streaming server host (default: %(default)s)",
    )
    parser.add_argument(
        "port",
        type=int,
        nargs="?",
        default=DEFAULT_PORT,
        help="Streaming server port (default: %(default)s)",
    )
    parser.add_argument(
        "--control-port",
        type=int,
        default=DEFAULT_CONTROL_PORT,
        help="Control API port for status queries (default: %(default)s)",
    )
    parser.add_argument(
        "--auto-close",
        action="store_true",
        help="Automatically close the window when video_status is 'complete'",
    )
    args = parser.parse_args()

    run(args.host, args.port, args.control_port, args.auto_close)


if __name__ == "__main__":
    main()
