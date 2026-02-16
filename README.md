# Vision VM

Vision VM is a headless Linux environment optimized for high-frequency frame capture and computer vision analysis. It runs Google Chrome in a virtual display, providing a lossless PNG stream and a robust control API.

---

## Architecture & API

Vision VM operates through a multi-port system to ensure isolation of concerns and high-performance telemetry.

### Port & Protocol Summary

| Port | Protocol | Component | Role |
| :--- | :--- | :--- | :--- |
| **9222** | TCP / CDP | Chrome | Navigation, duration retrieval, and playback control. |
| **5555** | TCP / Binary | Stream Server | High-speed, lossless PNG-over-TCP frame delivery. |
| **5556** | TCP / JSON | Mgmt Server | Command & Control API for telemetry and ROI management. |
| **5900** | TCP / RFB | VNC | Visual setup and debugging via Screen Sharing. |

### Binary Stream Protocol (Port 5555)

The stream server delivers frames using a length-prefixed binary protocol. Each message consists of a 16-byte header followed by the raw PNG payload.

**Header Format:**
```python
# struct format: !Qd
# !: Big-endian
# Q: 8-byte unsigned long long (Payload Length)
# d: 8-byte double (Timestamp/Playhead)
```

### Management API (Port 5556)

The management API accepts JSON commands and returns the current system and playback state.

**Common Commands:**
- `status`: Retrieve current ROI, telemetry, and performance metrics.
- `region_update`: Set the capture bounding box (`top`, `left`, `width`, `height`).
- `set_duration`: Push the video duration discovered via CDP.
- `update_telemetry`: Sync the current playhead and video status.

**Status Response Schema:**
```json
{
  "status": "ok",
  "capture_region": {
    "top": 0,
    "left": 0,
    "width": 1280,
    "height": 720,
    "current_time": 45.2,
    "duration": 300.5,
    "is_ended": false,
    "video_status": "playing"
  },
  "fps": 30.1,
  "active_clients": 1
}
```

---

## Playback Lifecycle

To ensure clean-exit transitions and accurate CV analysis, clients should adhere to the following lifecycle:

1.  **Load:** Navigate the browser to the target URL. Append `&t=0` (or a specific checkpoint) to ensure idempotent start times.
2.  **Sync:** Once the page is loaded, query `document.querySelector("video").duration` via CDP (Port 9222) and push the value to the Management API (Port 5556) using `set_duration`.
3.  **Monitor:** Ingest frames from the Binary Stream (Port 5555). Compare the frame's playhead timestamp against the total duration retrieved in step 2.
4.  **Exit:** When `currentTime >= (duration - 1.0)`, trigger a `pause()` command via CDP and update the VM status to `complete` via Port 5556. This allows orchestrators to transition safely before the video ends or redirects.

---

## Quick Start

### 1. Launch the VM
```bash
docker compose up --build
```

### 2. Health Check
Verify the management API is responsive:
```bash
python3 remote_controller.py --ping
```

### 3. Control Browser
Navigate to a specific URL and start the monitoring watchdog:
```bash
python3 remote_controller.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### 4. Verify Stream
Visualize the incoming frame stream with telemetry overlay:
```bash
python3 verify_stream.py --auto-close
```

---

## Operational Decisions

*   **State-Slave Model:** The VM acts as a **Passive Sensor**. It broadcasts state and frames, while the client (Slave) manages synchronization and processing intensity.
*   **ROI Persistence:** Region of Interest settings are handled via the Mgmt API and persist across sessions to ensure consistent CV analysis targets without re-calibration.

---

## Troubleshooting

### X11 Lock Errors
If you see `Fatal server error: Server is already active for display 99`, run the reset script:
```bash
./reset-chrome.sh
```

### Port 5556 Connection Refused
Ensure the `streaming_server.py` is fully initialized. Check logs:
```bash
docker compose logs streaming_server
```
If the issue persists, verify that the `socat` bridge or the Python process hasn't exited prematurely.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
