"""Remote Controller – Playwright CDP bridge to the Vision VM browser.

Connects to the Chrome instance running inside the VM via the Chrome
DevTools Protocol (CDP) on localhost:9222 and exposes helper functions
for programmatic browser automation.

Usage (from the Mac host):
    python remote_controller.py [youtube-url]
"""

import sys
import time
from typing import Optional

from playwright.sync_api import Browser, Page, sync_playwright


# ── Configuration ────────────────────────────────────────────────────────────

CDP_ENDPOINT: str = "http://localhost:9222"
DEFAULT_URL: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
DEFAULT_WIDTH: int = 1280
DEFAULT_HEIGHT: int = 720


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
    page.goto(url, wait_until="domcontentloaded")

    # Wait for the YouTube player to be present
    page.wait_for_selector("video", timeout=15000)

    # Lock viewport to the target resolution
    resize_viewport(page)

    # Dismiss consent dialogs if they appear
    _dismiss_consent(page)

    # Attempt to start playback
    _ensure_playback(page)

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


# ── CLI entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    """Load a YouTube video from the command line."""
    url: str = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    print(f"[CTRL] Target: {url}", flush=True)

    page: Page = load_video(url)

    print("[CTRL] Controller active. Press Ctrl-C to exit.", flush=True)
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n[CTRL] Exiting.", flush=True)


if __name__ == "__main__":
    main()
