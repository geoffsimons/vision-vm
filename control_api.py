import asyncio
import math
import os
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright, Page, Browser, Error as PlaywrightError

import streaming_server

app = FastAPI(title="Vision VM Control API")

# ── Helpers ──────────────────────────────────────────────────────────────────

def sanitize_float(val: any) -> float:
    """Ensure a value is a JSON-compliant float (not NaN or Inf)."""
    try:
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            return 0.0
        return f_val
    except (TypeError, ValueError):
        return 0.0

# ── Models ───────────────────────────────────────────────────────────────────

class RegionUpdate(BaseModel):
    top: int
    left: int
    width: int
    height: int

class NavigationRequest(BaseModel):
    url: str
    time: Optional[float] = None
    mode: Optional[str] = "theater"

class TelemetryUpdate(BaseModel):
    current_time: float
    is_ended: bool
    video_status: Optional[str] = None
    duration: Optional[float] = None

class InteractionRequest(BaseModel):
    action: str
    params: Optional[dict] = None

class SeekRequest(BaseModel):
    time: float

# ── Chrome Controller ────────────────────────────────────────────────────────

class ChromeController:
    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.target_mode: Optional[str] = "theater"
        self._lock = asyncio.Lock()

    async def start(self):
        """Initialize Playwright and connect to the existing Chrome instance."""
        async with self._lock:
            if self.page and self.browser and self.browser.is_connected():
                return

            try:
                if not self.playwright:
                    self.playwright = await async_playwright().start()

                print(f"[CDP] Connecting to {self.cdp_url}...", flush=True)
                self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)

                # Attach to the first available context and page
                if self.browser.contexts:
                    context = self.browser.contexts[0]
                    self.page = context.pages[0] if context.pages else await context.new_page()
                else:
                    context = await self.browser.new_context()
                    self.page = await context.new_page()

                print("[CDP] Connected to Chrome via Playwright", flush=True)
            except Exception as e:
                print(f"[CDP] Connection failed: {e}", flush=True)
                self.page = None
                self.browser = None

    async def ensure_connected(self):
        if not self.page or not self.browser or not self.browser.is_connected():
            await self.start()

    async def evaluate(self, script: str):
        await self.ensure_connected()
        if not self.page:
            return None
        try:
            return await self.page.evaluate(script)
        except PlaywrightError as e:
            print(f"[CDP] Evaluate error: {e}", flush=True)
            return None
        except Exception:
            return None

    async def navigate(self, url: str):
        await self.ensure_connected()
        if not self.page:
            raise Exception("Browser not connected")
        try:
            await self.page.goto(url, wait_until="networkidle")
        except PlaywrightError as e:
            print(f"[CDP] Navigation error: {e}", flush=True)

    async def set_mode(self, mode: str):
        self.target_mode = mode
        if mode == "theater":
            script = """
            (function() {
                const theaterBtn = document.querySelector('.ytp-size-button');
                if (theaterBtn) {
                    theaterBtn.click();
                } else {
                    const player = document.querySelector('#movie_player');
                    if (player) {
                        const e = new KeyboardEvent('keydown', {
                            key: 't',
                            code: 'KeyT',
                            keyCode: 84,
                            which: 84,
                            bubbles: true
                        });
                        player.dispatchEvent(e);
                    }
                }
            })()
            """
            await self.evaluate(script)

    async def seek(self, timestamp: float):
        script = f"""
        (function(t) {{
            const v = document.querySelector('video');
            if (v) {{ v.currentTime = t; return true; }}
            return false;
        }})({timestamp})
        """
        return await self.evaluate(script)

chrome = ChromeController()

# ── Background Tasks ─────────────────────────────────────────────────────────

async def monitor_playback():
    """Background loop to poll video telemetry and enforce UI states."""
    print("[MONITOR] Starting background telemetry loop...")
    while True:
        try:
            # Combined telemetry, UI state, and ROI detection script
            script = """
            (function() {
                const v = document.querySelector('video');
                const watchFlexy = document.querySelector('ytd-watch-flexy');
                const isWatch = !!watchFlexy;

                const data = {
                    is_watch_page: isWatch,
                    theater: isWatch ? watchFlexy.hasAttribute('theater') : false,
                    player_ready: !!document.querySelector('.html5-video-player')
                };

                if (v) {
                    data.time = v.currentTime;
                    data.duration = v.duration;
                    data.paused = v.paused;
                    data.ended = v.ended;

                    const r = v.getBoundingClientRect();
                    data.rect = {
                        top: Math.round(r.top),
                        left: Math.round(r.left),
                        width: Math.round(r.width),
                        height: Math.round(r.height)
                    };
                }
                return data;
            })()
            """
            status = await chrome.evaluate(script)

            if status:
                # 1. Update Telemetry & ROI
                with streaming_server.region_lock:
                    if "time" in status:
                        streaming_server.video_telemetry["current_time"] = sanitize_float(status["time"])
                        streaming_server.video_telemetry["duration"] = sanitize_float(status.get("duration", 0.0))
                        streaming_server.video_telemetry["is_ended"] = status.get("ended", False)
                        
                        if status.get("ended"):
                            streaming_server.video_telemetry["status"] = "complete"
                        else:
                            streaming_server.video_telemetry["status"] = "paused" if status.get("paused") else "playing"

                    # Auto-detect ROI
                    rect = status.get("rect")
                    if rect and rect["width"] > 50 and rect["height"] > 50:
                        streaming_server.capture_region["top"] = rect["top"]
                        streaming_server.capture_region["left"] = rect["left"]
                        streaming_server.capture_region["width"] = rect["width"]
                        streaming_server.capture_region["height"] = rect["height"]

                # 2. Enforce Theater Mode

                if chrome.target_mode == "theater" and status.get("is_watch_page"):
                    if not status.get("theater") and status.get("player_ready"):
                        print("[MONITOR] Theater mode lost – re-triggering...")
                        await chrome.set_mode("theater")

        except PlaywrightError as e:
            print(f"[MONITOR] Playwright error: {e}")
            # Potential browser crash or disconnect – attempt to reconnect on next loop
            chrome.page = None
        except Exception as e:
            print(f"[MONITOR] Loop error: {e}")

        await asyncio.sleep(0.5)

@app.on_event("startup")
async def startup_event():
    await chrome.start()
    asyncio.create_task(monitor_playback())

# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/status")
async def get_status():
    with streaming_server.region_lock:
        region = dict(streaming_server.capture_region)
        video = dict(streaming_server.video_telemetry)
    with streaming_server.stats_lock:
        fps = sanitize_float(streaming_server.current_fps)
        clients = streaming_server.active_clients
    return {
        "status": "ok",
        "video": video,
        "capture_region": region,
        "fps": fps,
        "active_clients": clients
    }

@app.post("/browser/navigate")
async def navigate(req: NavigationRequest):
    try:
        final_url = req.url
        if req.time is not None and req.time > 0:
            separator = "&" if "?" in final_url else "?"
            final_url = f"{final_url}{separator}t={int(req.time)}"

        await chrome.navigate(final_url)
        if req.mode:
            # Wait a bit for page load
            await asyncio.sleep(2)
            await chrome.set_mode(req.mode)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/browser/seek")
async def seek(req: SeekRequest):
    success = await chrome.seek(req.time)
    if success:
        return {"status": "ok"}
    else:
        raise HTTPException(status_code=404, detail="No video found to seek")

@app.post("/sensor/region")
async def update_region(req: RegionUpdate):
    if req.width <= 0 or req.height <= 0:
        raise HTTPException(status_code=400, detail="Invalid dimensions")

    with streaming_server.region_lock:
        streaming_server.capture_region["top"] = req.top
        streaming_server.capture_region["left"] = req.left
        streaming_server.capture_region["width"] = req.width
        streaming_server.capture_region["height"] = req.height

    return {"status": "ok"}

@app.post("/sensor/telemetry")
async def update_telemetry(req: TelemetryUpdate):
    with streaming_server.region_lock:
        streaming_server.video_telemetry["current_time"] = sanitize_float(req.current_time)
        streaming_server.video_telemetry["is_ended"] = req.is_ended
        if req.video_status:
            streaming_server.video_telemetry["status"] = req.video_status
        if req.duration is not None:
            streaming_server.video_telemetry["duration"] = sanitize_float(req.duration)
    return {"status": "ok"}

@app.post("/browser/interact")
async def interact(req: InteractionRequest):
    # Stub for future interaction
    return {"status": "ok", "message": f"Action {req.action} received"}
