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
from typing import Dict, List, Optional

import cv2
import mss
import numpy as np

# ── Configuration ────────────────────────────────────────────────────────────

HOST: str = "0.0.0.0"
PORT: int = int(os.environ.get("STREAM_PORT", "5555"))
ROI_PORT: int = int(os.environ.get("ROI_PORT", "5556"))
DISPLAY: str = os.environ.get("DISPLAY", ":99")
TARGET_FPS: int = int(os.environ.get("STREAM_FPS", "30"))

HEADER_FMT: str = "!Q"  # 8-byte unsigned long long, big-endian
HEADER_SIZE: int = struct.calcsize(HEADER_FMT)

# OpenCV PNG compression: 0 = no compression (fastest), 9 = max compression.
# Level 1 gives a good speed/size trade-off for streaming.
PNG_PARAMS: List[int] = [cv2.IMWRITE_PNG_COMPRESSION, 1]

# ── Region-of-Interest (ROI) state ───────────────────────────────────────────

capture_region: Dict[str, int] = {
    "top": 0,
    "left": 0,
    "width": 1280,
    "height": 720,
}
_region_lock: threading.Lock = threading.Lock()


# ── ROI listener ─────────────────────────────────────────────────────────────

def _roi_listener() -> None:
    """Listen for region_update JSON commands on a UDP socket.

    Expected payload::

        {"command": "region_update",
         "top": int, "left": int, "width": int, "height": int}
    """
    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, ROI_PORT))
    print(
        f"[STREAM] ROI listener started on UDP {HOST}:{ROI_PORT}",
        flush=True,
    )

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            msg: dict = json.loads(data.decode("utf-8"))

            if msg.get("command") != "region_update":
                continue

            new_region: Dict[str, int] = {
                "top": int(msg["top"]),
                "left": int(msg["left"]),
                "width": int(msg["width"]),
                "height": int(msg["height"]),
            }

            if new_region["width"] <= 0 or new_region["height"] <= 0:
                print(
                    f"[STREAM] Ignoring invalid region from {addr}: "
                    f"{new_region}",
                    flush=True,
                )
                continue

            with _region_lock:
                if new_region == capture_region:
                    continue
                capture_region.update(new_region)

            print(
                f"[STREAM] Capture region updated to: {new_region}",
                flush=True,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            print(
                f"[STREAM] Bad ROI packet: {exc}",
                flush=True,
            )
        except Exception as exc:
            print(
                f"[STREAM] ROI listener error: {exc}",
                flush=True,
            )


def _get_capture_monitor() -> dict:
    """Return an mss-compatible monitor dict from the current ROI."""
    with _region_lock:
        return dict(capture_region)


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
    connection is never shared across threads.  The capture region is
    read fresh on every frame so ROI updates take effect immediately.
    """
    print(f"[STREAM] Client connected: {addr}", flush=True)
    interval: float = 1.0 / TARGET_FPS
    frame_count: int = 0

    try:
        with mss.mss(display=DISPLAY) as sct:
            print(
                f"[STREAM] Thread {threading.current_thread().name} "
                f"using ROI capture region",
                flush=True,
            )

            while True:
                monitor: dict = _get_capture_monitor()
                t0: float = time.monotonic()

                png_data: Optional[bytes] = capture_png(sct, monitor)
                if png_data is None:
                    time.sleep(interval)
                    continue

                header: bytes = struct.pack(HEADER_FMT, len(png_data))
                conn.sendall(header + png_data)

                frame_count += 1
                if frame_count % 300 == 0:
                    print(
                        f"[STREAM] [{addr}] Frame {frame_count}: "
                        f"ROI={monitor['width']}x{monitor['height']} "
                        f"at ({monitor['left']},{monitor['top']})",
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
        conn.close()
        print(f"[STREAM] Socket closed for {addr}", flush=True)


# ── Server entry ─────────────────────────────────────────────────────────────

def serve() -> None:
    """Start the TCP streaming server and the ROI UDP listener.

    The accept loop runs without holding an mss handle; each client
    thread creates its own inside *handle_client*.
    """
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

    expected_w: int = int(os.environ.get("WIDTH", "0"))
    expected_h: int = int(os.environ.get("HEIGHT", "0"))
    if expected_w and expected_h and (width != expected_w or height != expected_h):
        print(
            f"[STREAM] WARNING: Detected {width}x{height} but "
            f"expected {expected_w}x{expected_h} from env",
            flush=True,
        )

    print(
        f"[STREAM] Serving PNG frames on {HOST}:{PORT}  "
        f"(display={DISPLAY}, {width}x{height})",
        flush=True,
    )

    # Start the ROI listener in a background thread.
    roi_thread = threading.Thread(target=_roi_listener, daemon=True)
    roi_thread.start()

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
