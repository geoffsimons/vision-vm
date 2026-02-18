# Vision VM

Vision VM is a specialized, headless Linux "sensor" optimized for high-frequency frame capture and real-time computer vision (CV) telemetry. It encapsulates a virtual display, an automated browser, and a high-performance streaming engine into a single, autonomous unit.

Designed to function as a decoupled actuator within a "Vision-VM + Orchestrator" pattern, it handles the complexities of browser automation and environment stabilization while broadcasting high-fidelity telemetry to a centralized "brain" (such as a Slot Engine).

---

## Key Features

- **Autonomous ROI Detection & Stabilization:** Automatically detects video players and enforces "theater-mode" regions to ensure consistent frame alignment without external calibration or manual ROI management.
- **Dual-Protocol Broadcast:**
  - **Binary Stream (Port 5555):** Real-time, lossless PNG-over-TCP broadcasting. Each frame includes a custom `[!Qd]` header (8-byte length + 8-byte playhead double) for low-latency ingestion.
  - **JSON Control API (Port 8001):** A modern FastAPI interface for browser orchestration, playback control, and access to "flattened" telemetry.
- **NaN-Guarded Telemetry:** Resilient telemetry processing that filters out browser-side `NaN` or `Inf` fluctuations, ensuring downstream pipeline stability.
- **Self-Healing Environment:** Actively monitors and re-triggers UI states (like YouTube theater mode) and handles X11 lock recovery to maintain a persistent capture environment.

---

## Architecture & API

Vision VM operates through a multi-port system to ensure isolation of concerns and high-performance telemetry delivery.

### Port & Protocol Summary

| Port | Protocol | Component | Role |
| :--- | :--- | :--- | :--- |
| **8001** | HTTP / JSON | Control API | Orchestration, ROI management, and status retrieval. |
| **5555** | TCP / Binary | Stream Server | High-speed, lossless PNG-over-TCP frame delivery. |
| **9222** | TCP / CDP | Chrome | Direct DevTools access (via `socat` bridge). |
| **5900** | TCP / RFB | VNC | Visual setup and debugging via Screen Sharing. |

### Control API (Port 8001)

The Control API provides a RESTful interface for interacting with the autonomous VM.

#### `GET /status`
Returns the current stabilized telemetry, capture region, and performance metrics.

**Response Schema:**
```json
{
  "status": "ok",
  "video": {
    "current_time": 45.2,
    "duration": 300.5,
    "is_ended": false,
    "status": "playing"
  },
  "capture_region": {
    "top": 48,
    "left": 0,
    "width": 1280,
    "height": 720
  },
  "fps": 16.5,
  "active_clients": 1
}
```

#### `POST /browser/navigate`
Navigates the sensor to a target URL with optional seek time and UI enforcement.

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `url` | string | The target URL to load. |
| `time` | float | (Optional) Seek to this timestamp immediately after load. |
| `mode` | string | (Optional) UI enforcement mode (default: `theater`). |

#### `POST /browser/interact`
Executes playback actuation commands within the browser.

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `action` | string | The interaction to perform (`play` or `pause`). |

#### `POST /browser/seek`
Programmatically jumps to a specific timestamp in the active video.

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `time` | float | Target playhead timestamp in seconds. |

### Binary Stream Protocol (Port 5555)

The stream server delivers frames using a length-prefixed binary protocol. Each message consists of a 16-byte header followed by the raw PNG payload.

**Header Format (`!Qd`):**
1. **Payload Length (8 bytes):** Unsigned 64-bit big-endian integer.
2. **Playhead Timestamp (8 bytes):** 64-bit big-endian double representing the current video time.

---

## Technical Rationale (The "Why")

Capturing frame-accurate telemetry from dynamic web content is notoriously difficult. Standard headless browsers suffer from inconsistent frame rates, UI shifts, and heavy resource overhead.

Vision VM solves this by:
1. **Isolating the Browser:** Running in a dedicated Xvfb environment ensures no host-side UI interference or display contention.
2. **Flattening Telemetry:** Normalizing volatile browser metadata into a stable, NaN-guarded JSON schema.
3. **Optimizing Transport:** Using a raw TCP binary stream for frames to bypass the overhead of HTTP/WebSocket, enabling stable **16.5+ FPS** ingestion for CV pipelines.

---

## Quick Start

### 1. Launch the Sensor
```bash
docker compose up --build
```

### 2. Orchestrate Navigation
Direct the sensor to a target stream:
```bash
# Using the thin client
python3 remote_controller.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### 3. Verify the Stream
Verify the high-frequency stream and telemetry overlay:
```bash
python3 verify_stream.py
```

---

## Troubleshooting

### X11 Lock Errors
If the virtual display fails to initialize, clear the X11 lock files:
```bash
./reset-chrome.sh
```

### Resource Constraints
Vision VM is CPU-bound due to real-time PNG encoding. Ensure the container has sufficient resources to maintain target FPS.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
