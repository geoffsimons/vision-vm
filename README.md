# Vision VM

Vision VM is a headless Linux environment optimized for high-frequency frame capture and computer vision analysis. It runs Google Chrome in a virtual display, providing a lossless PNG stream and a robust control API.

---

## Project Overview

The core intent of Vision VM is to create a seamless pipeline:
**Headless Chrome** (Rendering) -> **PNG Stream** (Capture) -> **CV Analyzer** (Processing).

By leveraging Xvfb and Fluxbox, it provides a stable environment for complex web interactions while exposing low-level control and high-performance streaming interfaces.

---

## System Architecture

Vision VM operates through a **3-port bridge** strategy to ensure isolation of concerns:

*   **Port 9222 (CDP):** Chrome DevTools Protocol. Used for direct browser automation and inspection via a `socat` bridge.
*   **Port 5555 (Stream):** High-speed, lossless PNG-over-TCP frame delivery.
*   **Port 5556 (Mgmt):** Command & Control API for telemetry and ROI (Region of Interest) management.

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
Navigate to a specific URL:
```bash
python3 remote_controller.py https://example.com
```

### 4. Verify Stream
Visualize the incoming frame stream:
```bash
python3 verify_stream.py
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
