import asyncio
import json
import os
import threading
from typing import Dict, Optional

import requests
import websockets
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import streaming_server

app = FastAPI(title="Vision VM Control API")

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

# ── Chrome Controller ────────────────────────────────────────────────────────

class ChromeController:
    def __init__(self, cdp_host: str = "localhost", cdp_port: int = 9223):
        self.base_url = f"http://{cdp_host}:{cdp_port}"
        self.cdp_host = cdp_host
        self.cdp_port = cdp_port
        self.target_mode: Optional[str] = "theater"

    def _get_tabs(self):
        try:
            resp = requests.get(f"{self.base_url}/json/list")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[CDP] Error listing tabs: {e}")
            return []

    async def _send_cdp_command(self, tab_id: str, method: str, params: dict):
        ws_url = f"ws://{self.cdp_host}:{self.cdp_port}/devtools/page/{tab_id}"
        async with websockets.connect(ws_url) as ws:
            command = {
                "id": 1,
                "method": method,
                "params": params
            }
            await ws.send(json.dumps(command))
            resp = await ws.recv()
            return json.loads(resp)

    async def navigate(self, url: str):
        tabs = self._get_tabs()
        if not tabs:
            # Create new tab
            resp = requests.get(f"{self.base_url}/json/new?url={url}")
            return resp.json()

        # Navigate first tab
        tab_id = tabs[0]["id"]
        return await self._send_cdp_command(tab_id, "Page.navigate", {"url": url})

    async def inject_js(self, script: str):
        tabs = self._get_tabs()
        if not tabs:
            return None
        tab_id = tabs[0]["id"]
        return await self._send_cdp_command(tab_id, "Runtime.evaluate", {"expression": script})

    async def evaluate(self, script: str):
        tabs = self._get_tabs()
        if not tabs:
            return None
        tab_id = tabs[0]["id"]
        resp = await self._send_cdp_command(tab_id, "Runtime.evaluate", {
            "expression": script,
            "returnByValue": True
        })
        if "result" in resp and "result" in resp["result"]:
            return resp["result"]["result"].get("value")
        return None

    async def set_mode(self, mode: str):
        self.target_mode = mode
        if mode == "theater":
            # Press 't' key or click theater button
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
            await self.inject_js(script)

chrome = ChromeController()

# ── Background Tasks ─────────────────────────────────────────────────────────

async def monitor_playback():
    """Background loop to poll video telemetry and enforce UI states."""
    print("[MONITOR] Starting background telemetry loop...")
    while True:
        try:
            # Combined telemetry and UI state script
            script = """
            (function() {
                const v = document.querySelector('video');
                const watchFlexy = document.querySelector('ytd-watch-flexy');
                const isWatch = !!watchFlexy;

                const data = {
                    is_watch_page: is_watch,
                    theater: isWatch ? watchFlexy.hasAttribute('theater') : false,
                    player_ready: !!document.querySelector('.html5-video-player')
                };

                if (v) {
                    data.time = v.currentTime;
                    data.duration = v.duration;
                    data.paused = v.paused;
                    data.ended = v.ended;
                }
                return data;
            })()
            """
            status = await chrome.evaluate(script)

            if status:
                # 1. Update Telemetry
                if "time" in status:
                    with streaming_server.region_lock:
                        streaming_server.capture_region["current_time"] = status["time"]
                        streaming_server.capture_region["duration"] = status.get("duration", 0.0)
                        streaming_server.capture_region["is_ended"] = status.get("ended", False)
                        streaming_server.capture_region["video_status"] = "paused" if status.get("paused") else "playing"

                # 2. Enforce Theater Mode
                if chrome.target_mode == "theater" and status.get("is_watch_page"):
                    if not status.get("theater") and status.get("player_ready"):
                        print("[MONITOR] Theater mode lost – re-triggering...")
                        await chrome.set_mode("theater")

        except Exception as e:
            # Don't spam logs if it's just a transient connection error during startup/refresh
            if "websockets" not in str(e).lower():
                print(f"[MONITOR] Loop error: {e}")

        await asyncio.sleep(0.5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_playback())

# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/status")
async def get_status():
    with streaming_server.region_lock:
        region = dict(streaming_server.capture_region)
    with streaming_server.stats_lock:
        fps = streaming_server.current_fps
        clients = streaming_server.active_clients
    return {
        "status": "ok",
        "capture_region": region,
        "fps": fps,
        "active_clients": clients
    }

@app.post("/browser/navigate")
async def navigate(req: NavigationRequest):
    try:
        final_url = req.url
        if req.time is not None and req.time > 0:
            # Check if URL already has query parameters
            separator = "&" if "?" in final_url else "?"
            # Append YouTube style timestamp (t=X)
            final_url = f"{final_url}{separator}t={int(req.time)}"

        await chrome.navigate(final_url)
        if req.mode:
            # Wait a bit for page load
            await asyncio.sleep(2)
            await chrome.set_mode(req.mode)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        streaming_server.capture_region["current_time"] = req.current_time
        streaming_server.capture_region["is_ended"] = req.is_ended
        if req.video_status:
            streaming_server.capture_region["video_status"] = req.video_status
        if req.duration is not None:
            streaming_server.capture_region["duration"] = req.duration
    return {"status": "ok"}

@app.post("/browser/interact")
async def interact(req: InteractionRequest):
    # Stub for future interaction
    return {"status": "ok", "message": f"Action {req.action} received"}
