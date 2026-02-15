"""Capture heartbeat – keeps the container alive.

When ENABLE_CAPTURE=1 is set, grabs one frame per second from the Xvfb
display.  Otherwise runs a lightweight 60-second heartbeat so the
container stays up for interactive VNC sessions.
"""

import os
import time
from datetime import datetime, timezone

CAPTURES_DIR: str = "/captures"
DISPLAY: str = os.environ.get("DISPLAY", ":99")
ENABLE_CAPTURE: bool = os.environ.get("ENABLE_CAPTURE", "0") == "1"
HEARTBEAT_INTERVAL: int = 60


def ensure_captures_dir() -> None:
    """Create the captures directory if it does not exist."""
    os.makedirs(CAPTURES_DIR, exist_ok=True)


def capture_loop() -> None:
    """Run the 1-FPS screen-capture loop indefinitely."""
    import mss
    import mss.tools
    import numpy as np

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


def heartbeat_loop() -> None:
    """Print a heartbeat message every 60 seconds to keep the container alive."""
    print("Heartbeat mode active (capture disabled).", flush=True)
    while True:
        timestamp: str = datetime.now(tz=timezone.utc).strftime(
            "%Y%m%dT%H%M%S"
        )
        print(f"{timestamp} | Heartbeat", flush=True)
        time.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    try:
        if ENABLE_CAPTURE:
            capture_loop()
        else:
            heartbeat_loop()
    except KeyboardInterrupt:
        print("\nStopped by user.", flush=True)
