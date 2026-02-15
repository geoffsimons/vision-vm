"""Lossless Streaming Sensor – PNG-over-TCP server.

Captures display :99 via mss, encodes each frame as lossless PNG,
and streams them to connected TCP clients on port 5555.

Wire protocol (per frame):
  [8 bytes] – payload length as unsigned 64-bit big-endian integer
  [N bytes] – raw PNG image data
"""

import os
import socket
import struct
import threading
import time

import mss
import mss.tools

# ── Configuration ────────────────────────────────────────────────────────────

HOST: str = "0.0.0.0"
PORT: int = int(os.environ.get("STREAM_PORT", "5555"))
DISPLAY: str = os.environ.get("DISPLAY", ":99")
TARGET_FPS: int = int(os.environ.get("STREAM_FPS", "30"))

HEADER_FMT: str = "!Q"  # 8-byte unsigned long long, big-endian
HEADER_SIZE: int = struct.calcsize(HEADER_FMT)


# ── Frame capture ────────────────────────────────────────────────────────────

def capture_png(sct: mss.mss, monitor: dict) -> bytes:
    """Grab a single frame and return it as PNG bytes."""
    frame = sct.grab(monitor)
    png_bytes: bytes = mss.tools.to_png(frame.rgb, frame.size)
    return png_bytes


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
