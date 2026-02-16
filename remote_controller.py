"""Remote Controller – Playwright CDP bridge to the Vision VM browser.

Connects to the Chrome instance running inside the VM via the Chrome
DevTools Protocol (CDP) on localhost:9222 and exposes helper functions
for programmatic browser automation.

Usage (from the Mac host):
    python remote_controller.py [youtube-url]
"""

import argparse
import json
import socket
import sys
import time
from typing import Dict, Optional

from playwright.sync_api import Browser, Page, sync_playwright


# ── Configuration ────────────────────────────────────────────────────────────

CDP_ENDPOINT: str = "http://localhost:9222"
DEFAULT_URL: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
DEFAULT_WIDTH: int = 1280
DEFAULT_HEIGHT: int = 720

VM_HOST: str = "localhost"
ROI_PORT: int = 5556


# ── Core helpers ─────────────────────────────────────────────────────────────

def connect_browser() -> Browser:
    """Return a Playwright Browser connected over CDP."""
    pw = sync_playwright().start()
    browser: Browser = pw.chromium.connect_over_cdp(CDP_ENDPOINT)
    print(f"[CTRL] Connected to Chrome via CDP at {CDP_ENDPOINT}", flush=True)
    return browser


def resize_viewport(
    page: Page,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> None:
    """Set the browser viewport to the given dimensions.

    Ensures the rendered content fills the virtual display edge-to-edge
    regardless of the Xvfb resolution.
    """
    page.set_viewport_size({"width": width, "height": height})
    print(
        f"[CTRL] Viewport resized to {width}x{height}",
        flush=True,
    )


def wait_for_player_ready(page: Page, timeout: int = 15000) -> None:
    """Block until the YouTube HTML5 player element is present.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    timeout : int
        Maximum wait time in milliseconds.
    """
    page.wait_for_selector(".html5-video-player", timeout=timeout)
    print("[CTRL] YouTube player (.html5-video-player) is ready.", flush=True)


def load_video(url: str, browser: Optional[Browser] = None) -> Page:
    """Navigate to a YouTube URL and ensure the player starts.

    Parameters
    ----------
    url : str
        Full YouTube video URL.
    browser : Browser, optional
        Existing Playwright browser handle.  A new connection is
        created when *None*.

    Returns
    -------
    Page
        The Playwright page object with the video loaded.
    """
    if browser is None:
        browser = connect_browser()

    # Use the first available context or create one
    contexts = browser.contexts
    if contexts:
        context = contexts[0]
        page: Page = context.pages[0] if context.pages else context.new_page()
    else:
        context = browser.new_context()
        page = context.new_page()

    print(f"[CTRL] Navigating to {url}", flush=True)
    page.goto(url, wait_until="networkidle")

    # Wait for the YouTube player to be present
    page.wait_for_selector("video", timeout=15000)

    # Lock viewport to the target resolution
    resize_viewport(page)

    # Dismiss consent dialogs if they appear
    _dismiss_consent(page)

    # Attempt to start playback
    _ensure_playback(page)

    # Suppress autoplay to prevent unexpected redirects
    _suppress_autoplay(page)

    # Wait for the full YouTube player shell before sending keys
    wait_for_player_ready(page)

    # Focus the player container so keyboard shortcuts are received
    page.click(".html5-video-player", timeout=5000)
    time.sleep(0.5)

    # Start / resume playback with YouTube's universal toggle
    page.keyboard.press("k")
    time.sleep(0.5)
    print("[CTRL] Playback triggered via 'k' key.", flush=True)

    # Engage Theater Mode and verify via player width
    page.keyboard.press("t")
    time.sleep(1)

    player_width: int = page.evaluate(
        "document.querySelector('#movie_player').offsetWidth"
    )
    if player_width < 1000:
        print(
            f"[CTRL] Player width {player_width}px < 1000 – "
            "retrying Theater Mode.",
            flush=True,
        )
        page.keyboard.press("t")
        time.sleep(1)

    print("[CTRL] YouTube Theater Mode engaged via 't' key.", flush=True)

    # Inject CSS to suppress residual YouTube UI chrome
    _inject_ui_cleanup(page)

    print("[CTRL] Video playback confirmed.", flush=True)
    return page


# ── Internal helpers ─────────────────────────────────────────────────────────

def _dismiss_consent(page: Page) -> None:
    """Click through YouTube / Google consent modals when present."""
    try:
        accept_btn = page.locator(
            "button:has-text('Accept all'), "
            "button:has-text('Accept'), "
            "tp-yt-paper-button:has-text('Accept all')"
        )
        if accept_btn.count() > 0:
            accept_btn.first.click(timeout=3000)
            print("[CTRL] Dismissed consent dialog.", flush=True)
            time.sleep(1)
    except Exception:
        pass  # No dialog present – continue


def _ensure_playback(page: Page) -> None:
    """Make sure the <video> element is actually playing."""
    try:
        page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (v && v.paused) { v.play(); }
            }
        """)
    except Exception:
        pass

    # Brief wait then verify
    time.sleep(2)

    is_playing: bool = page.evaluate("""
        () => {
            const v = document.querySelector('video');
            return v ? (!v.paused && !v.ended && v.readyState > 2) : false;
        }
    """)

    if not is_playing:
        print(
            "[CTRL] WARNING: Video may not be playing. "
            "Check the VM display for consent dialogs.",
            flush=True,
        )


def _inject_ui_cleanup(page: Page) -> None:
    """Hide residual YouTube UI elements for a pseudo-fullscreen look."""
    page.add_style_tag(content=(
        ".ytp-chrome-top { display: none !important; } "
        ".ytp-gradient-top { display: none !important; } "
        "#masthead-container { display: none !important; }"
    ))
    print("[CTRL] CSS injected – YouTube UI chrome hidden.", flush=True)


def _suppress_autoplay(page: Page) -> None:
    """Disable YouTube's autoplay toggle if it is currently enabled."""
    try:
        toggled_off: bool = page.evaluate("""
            () => {
                const btn = document.querySelector(
                    'button.ytp-button[data-tooltip-target-id='
                    + '"ytp-autonav-toggle-button"]'
                );
                if (!btn) return false;
                const isOn = btn.getAttribute('aria-checked') === 'true'
                    || btn.classList.contains('ytp-autonav-toggle-button-active');
                if (isOn) { btn.click(); return true; }
                return false;
            }
        """)
        if toggled_off:
            print("[CTRL] Autoplay toggled OFF.", flush=True)
        else:
            print("[CTRL] Autoplay already off (or toggle not found).", flush=True)
    except Exception:
        print("[CTRL] Could not access autoplay toggle.", flush=True)


# ── ROI helpers ──────────────────────────────────────────────────────────────

def calculate_video_region(
    page: Page,
    *,
    quiet: bool = False,
) -> Optional[Dict[str, int]]:
    """Detect the bounding box of the YouTube video element.

    Uses Playwright's ``bounding_box()`` on the ``#movie_player video``
    locator to determine the exact pixel coordinates of the active video
    area within the virtual display.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    quiet : bool
        When *True*, suppress informational log lines.  Used by the
        periodic monitor loop to avoid log spam.

    Returns
    -------
    dict or None
        ``{"top": int, "left": int, "width": int, "height": int}`` on
        success, or *None* if the element cannot be located.
    """
    try:
        locator = page.locator("#movie_player video")
        locator.wait_for(state="visible", timeout=10000)
        box = locator.bounding_box()
        if box is None:
            if not quiet:
                print(
                    "[CTRL] Could not resolve video bounding box.",
                    flush=True,
                )
            return None

        region: Dict[str, int] = {
            "top": int(box["y"]),
            "left": int(box["x"]),
            "width": int(box["width"]),
            "height": int(box["height"]),
        }
        if not quiet:
            print(f"[CTRL] Detected video region: {region}", flush=True)
        return region
    except Exception as exc:
        if not quiet:
            print(
                f"[CTRL] Video region detection failed: {exc}",
                flush=True,
            )
        return None


def send_region_update(
    region: Dict[str, int],
    host: str = VM_HOST,
    port: int = ROI_PORT,
) -> None:
    """Send a region_update command to the VM's ROI listener via UDP.

    Parameters
    ----------
    region : dict
        Must contain ``top``, ``left``, ``width``, ``height`` keys.
    host : str
        VM hostname or IP address.
    port : int
        UDP port the ROI listener is bound to.
    """
    payload: dict = {"command": "region_update", **region}
    data: bytes = json.dumps(payload).encode("utf-8")

    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(data, (host, port))
        print(
            f"[CTRL] Sent region_update to {host}:{port} → {region}",
            flush=True,
        )
    finally:
        sock.close()


def _parse_crop(crop_str: str) -> Dict[str, int]:
    """Parse a ``X,Y,W,H`` crop string into an ROI dict.

    Parameters
    ----------
    crop_str : str
        Comma-separated values: ``left,top,width,height``.

    Returns
    -------
    dict
        ``{"top": int, "left": int, "width": int, "height": int}``
    """
    parts = [int(v.strip()) for v in crop_str.split(",")]
    if len(parts) != 4:
        raise ValueError(
            f"Expected 4 comma-separated integers (X,Y,W,H), got: {crop_str}"
        )
    return {
        "left": parts[0],
        "top": parts[1],
        "width": parts[2],
        "height": parts[3],
    }


# ── Playback introspection ───────────────────────────────────────────────────

def get_playback_state(page: Page) -> str:
    """Query the YouTube player for its current playback state.

    Returns
    -------
    str
        One of ``'playing'``, ``'paused'``, or ``'ad'``.
    """
    state: str = page.evaluate("""
        () => {
            const v = document.querySelector('video');
            if (!v) return 'paused';

            const adOverlay = document.querySelector('.ad-showing');
            if (adOverlay) return 'ad';

            if (!v.paused && !v.ended && v.readyState > 2) return 'playing';
            return 'paused';
        }
    """)
    return state


# ── Monitoring ───────────────────────────────────────────────────────────────

def monitor_playback(
    page: Page,
    interval: float = 5.0,
    *,
    vm_host: str = VM_HOST,
    roi_port: int = ROI_PORT,
    last_region: Optional[Dict[str, int]] = None,
) -> None:
    """Poll the page URL and video region, logging changes.

    Re-detects the video bounding box on every tick and sends an ROI
    update to the VM only when the region has actually changed.  This
    ensures the capture region persists across controller restarts
    (the server is never told to reset) while still tracking layout
    shifts during playback.

    Parameters
    ----------
    page : Page
        Active Playwright page to monitor.
    interval : float
        Seconds between each check (default 5).
    vm_host : str
        VM hostname for ROI updates.
    roi_port : int
        UDP port for ROI updates.
    last_region : dict or None
        The most recently sent region, used to suppress duplicate
        updates.  Typically passed from ``main()``.
    """
    last_url: str = page.url
    print(f"[MONITOR] Watching URL: {last_url}", flush=True)

    while True:
        time.sleep(interval)

        current_url: str = page.url
        if current_url != last_url:
            print(
                f"[AUTO-PLAY] Redirect detected! Adjusting... "
                f"{last_url} -> {current_url}",
                flush=True,
            )
            last_url = current_url

        current_region: Optional[Dict[str, int]] = (
            calculate_video_region(page, quiet=True)
        )
        if current_region is not None and current_region != last_region:
            print(
                f"[MONITOR] Video region changed: {current_region}",
                flush=True,
            )
            send_region_update(
                current_region, host=vm_host, port=roi_port,
            )
            last_region = current_region


# ── CLI entrypoint ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Remote Controller – Playwright CDP bridge to the Vision VM browser.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help="YouTube video URL (default: %(default)s)",
    )
    parser.add_argument(
        "--crop",
        type=str,
        default=None,
        metavar="X,Y,W,H",
        help=(
            "Manual ROI override as comma-separated integers: "
            "left,top,width,height. Overrides automatic video detection."
        ),
    )
    parser.add_argument(
        "--reset-roi",
        action="store_true",
        default=False,
        help=(
            "Send a full-display 1280x720 ROI reset to the VM and exit "
            "without loading a video."
        ),
    )
    parser.add_argument(
        "--vm-host",
        type=str,
        default=VM_HOST,
        help="VM hostname for ROI updates (default: %(default)s)",
    )
    parser.add_argument(
        "--roi-port",
        type=int,
        default=ROI_PORT,
        help="UDP port for ROI updates (default: %(default)s)",
    )
    return parser


def main() -> None:
    """Load a YouTube video and send the detected ROI to the VM."""
    args = _build_parser().parse_args()

    if args.reset_roi:
        reset_region: Dict[str, int] = {
            "top": 0,
            "left": 0,
            "width": DEFAULT_WIDTH,
            "height": DEFAULT_HEIGHT,
        }
        print(
            f"[CTRL] Resetting ROI to full display: {reset_region}",
            flush=True,
        )
        send_region_update(
            reset_region, host=args.vm_host, port=args.roi_port,
        )
        return

    print(f"[CTRL] Target: {args.url}", flush=True)
    page: Page = load_video(args.url)

    # Determine the capture region (manual crop takes priority).
    region: Optional[Dict[str, int]] = None
    if args.crop:
        region = _parse_crop(args.crop)
        print(f"[CTRL] Using manual crop override: {region}", flush=True)
    else:
        region = calculate_video_region(page)

    if region is not None:
        send_region_update(region, host=args.vm_host, port=args.roi_port)
    else:
        print(
            "[CTRL] No ROI detected – VM will capture the full display.",
            flush=True,
        )

    print("[CTRL] Controller active. Press Ctrl-C to exit.", flush=True)
    try:
        monitor_playback(
            page,
            vm_host=args.vm_host,
            roi_port=args.roi_port,
            last_region=region,
        )
    except KeyboardInterrupt:
        print("\n[CTRL] Exiting.", flush=True)


if __name__ == "__main__":
    main()
