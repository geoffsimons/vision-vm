"""Capture heartbeat – grabs one frame per second from the Xvfb display."""

import os
import time
from datetime import datetime, timezone

import mss
import mss.tools
import numpy as np

CAPTURES_DIR: str = "/captures"
DISPLAY: str = os.environ.get("DISPLAY", ":99")


def ensure_captures_dir() -> None:
    """Create the captures directory if it does not exist."""
    os.makedirs(CAPTURES_DIR, exist_ok=True)


def capture_loop() -> None:
    """Run the 1-FPS screen-capture loop indefinitely."""
    ensure_captures_dir()

    with mss.mss(display=DISPLAY) as sct:
        monitor: dict = sct.monitors[0]  # Full virtual screen
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


if __name__ == "__main__":
    try:
        capture_loop()
    except KeyboardInterrupt:
        print("\nCapture stopped by user.", flush=True)
