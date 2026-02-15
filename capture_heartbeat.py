"""Capture heartbeat – benchmark and keep-alive for the Vision VM.

Default behaviour:
  1. Run a 15-second in-memory capture benchmark (no disk I/O).
  2. Log a results summary (Avg FPS, Min/Max frame time).
  3. Transition to a 30-second production heartbeat.

Set ENABLE_CAPTURE=1 to use the legacy 1-FPS disk-capture loop instead.
"""

import os
import time
from datetime import datetime, timezone
from typing import List

CAPTURES_DIR: str = "/captures"
DISPLAY: str = os.environ.get("DISPLAY", ":99")
ENABLE_CAPTURE: bool = os.environ.get("ENABLE_CAPTURE", "0") == "1"

BENCHMARK_DURATION: int = 15  # seconds
HEARTBEAT_INTERVAL: int = 30  # seconds


# ── Helpers ───────────────────────────────────────────────────────────────────

def ensure_captures_dir() -> None:
    """Create the captures directory if it does not exist."""
    os.makedirs(CAPTURES_DIR, exist_ok=True)


def _utc_stamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")


# ── Benchmark Mode ────────────────────────────────────────────────────────────

def benchmark() -> None:
    """Capture frames in-memory for BENCHMARK_DURATION seconds.

    Each frame is converted to a NumPy array to simulate real CV
    processing overhead.  No images are written to disk.
    """
    import mss
    import numpy as np

    print(
        f"[BENCHMARK] Starting {BENCHMARK_DURATION}s in-memory capture …",
        flush=True,
    )

    frame_times: List[float] = []

    with mss.mss(display=DISPLAY) as sct:
        monitor: dict = sct.monitors[0]
        print(f"[BENCHMARK] Monitor: {monitor}", flush=True)

        deadline: float = time.monotonic() + BENCHMARK_DURATION
        while time.monotonic() < deadline:
            t0: float = time.monotonic()

            frame = sct.grab(monitor)
            _: np.ndarray = np.array(frame)  # simulate CV overhead

            elapsed: float = time.monotonic() - t0
            frame_times.append(elapsed)

    _print_results(frame_times)


def _print_results(frame_times: List[float]) -> None:
    """Log a summary table of benchmark metrics."""
    total_frames: int = len(frame_times)
    total_time: float = sum(frame_times)

    if total_frames == 0:
        print("[BENCHMARK] No frames captured – display may not be ready.",
              flush=True)
        return

    avg_fps: float = total_frames / total_time
    min_ft: float = min(frame_times) * 1000  # ms
    max_ft: float = max(frame_times) * 1000  # ms

    print("", flush=True)
    print("=" * 50, flush=True)
    print("  BENCHMARK RESULTS", flush=True)
    print("=" * 50, flush=True)
    print(f"  Duration      : {BENCHMARK_DURATION} s", flush=True)
    print(f"  Total Frames  : {total_frames}", flush=True)
    print(f"  Avg FPS       : {avg_fps:.2f}", flush=True)
    print(f"  Min Frame Time: {min_ft:.2f} ms", flush=True)
    print(f"  Max Frame Time: {max_ft:.2f} ms", flush=True)
    print("=" * 50, flush=True)
    print("", flush=True)


# ── Production Heartbeat ─────────────────────────────────────────────────────

def production_heartbeat() -> None:
    """Print a heartbeat every HEARTBEAT_INTERVAL seconds."""
    print("[PRODUCTION] Entering heartbeat mode.", flush=True)
    while True:
        print(f"{_utc_stamp()} | Heartbeat", flush=True)
        time.sleep(HEARTBEAT_INTERVAL)


# ── Legacy Capture Loop ──────────────────────────────────────────────────────

def capture_loop() -> None:
    """Run the 1-FPS screen-capture loop indefinitely (ENABLE_CAPTURE=1)."""
    import mss
    import mss.tools
    import numpy as np

    ensure_captures_dir()

    with mss.mss(display=DISPLAY) as sct:
        monitor: dict = sct.monitors[0]
        print(f"Targeting monitor: {monitor}", flush=True)

        while True:
            timestamp: str = datetime.now(tz=timezone.utc).strftime(
                "%Y%m%dT%H%M%S_%f"
            )
            filename: str = os.path.join(
                CAPTURES_DIR, f"frame_{timestamp}.png"
            )

            frame = sct.grab(monitor)
            img: np.ndarray = np.array(frame)

            if img.size == 0:
                print(
                    f"{timestamp} | WARNING: empty frame, display may not "
                    "be ready",
                    flush=True,
                )
            else:
                mss.tools.to_png(frame.rgb, frame.size, output=filename)
                print(f"{timestamp} | Frame captured", flush=True)

            time.sleep(1)


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        if ENABLE_CAPTURE:
            capture_loop()
        else:
            benchmark()
            production_heartbeat()
    except KeyboardInterrupt:
        print("\nStopped by user.", flush=True)
