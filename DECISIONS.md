# Architecture Decisions

## State-Slave Architecture
The streaming server utilizes a "State-Slave" architecture. The server acts as a passive transmitter of the current state (video frames and metadata), while the client manages the connection and requests. This simplifies server logic and ensures that the server doesn't get overwhelmed by slow clients.

## Shift from UDP to TCP for ROI Management
The ROI Management API (Port 5556) was moved from UDP to TCP. While UDP offers lower latency, the reliability issues (dropped packets leading to inconsistent ROI states) outweighed the speed benefits for management commands. TCP ensures all ROI updates are received and processed in order.

## PNG-over-TCP for Video Frames
Video frames are transmitted as PNG-encoded data over TCP on Port 5555. PNG provides lossless compression, which is critical for computer vision tasks where compression artifacts could interfere with feature detection. TCP guarantees the delivery and ordering of frames.

## Headless Display Configuration
The system uses Xvfb on Display :99 for headless Chrome rendering. This provides a stable virtual display environment within the Docker container without requiring a physical monitor or GPU.

## TCP Command Server with Telemetry
The Vision VM now features a dedicated TCP command server (Port 5556) responsible for handling management commands (e.g., ROI updates) and providing real-time telemetry (FPS, active clients). This provides a robust, request-response communication channel for external controllers.

## Dynamic Region-of-Interest (ROI) for Capture
The system supports dynamic, client-controlled Region-of-Interest for frame capture. This allows precise targeting of specific content areas (e.g., a video player) on the virtual display, optimizing downstream computer vision processing by reducing irrelevant data.

## Streamlined Headless Display for Pure Content
The virtual display environment is meticulously configured to eliminate all extraneous UI elements from both the window manager (Fluxbox) and the browser (Chrome). This ensures that the captured frames contain only the intended web content, free from visual noise, which is critical for accurate computer vision analysis.
