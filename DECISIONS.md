# Architecture Decisions

## State-Slave Architecture (Passive Sensor)
The streaming server utilizes a "State-Slave" architecture where the VM acts as a **Passive Sensor**. The server broadcast the current state (video frames and metadata), while the client manages the connection, requests, and processing logic. This prevents the server from being throttled by client-side latency.

## TCP over UDP for ROI Management
The ROI Management API (Port 5556) uses **TCP instead of UDP**. While UDP offers lower latency, the reliability issues (dropped packets leading to inconsistent ROI states) outweighed the speed benefits for management commands. TCP ensures all ROI updates are received and processed in order.

## PNG-over-TCP for Video Frames
Video frames are transmitted as PNG-encoded data over TCP on Port 5555. PNG provides lossless compression, critical for computer vision tasks where artifacts could interfere with feature detection. TCP guarantees frame delivery and ordering.

## Headless Display Configuration
The system uses Xvfb on Display :99 for headless Chrome rendering. This provides a stable virtual display environment within the Docker container without requiring a physical monitor or GPU.

## Dynamic Region-of-Interest (ROI) Persistence
The system supports dynamic, client-controlled ROI for frame capture. These coordinates are managed via the TCP Mgmt API (Port 5556) and are intended to be persistent or easily re-applied to maintain consistent CV targets.

## End-to-End Video Playback Telemetry
The system now incorporates comprehensive telemetry for video playback, including current playhead time, total duration, and playback status (playing/complete). This telemetry is synchronized from the `remote_controller.py` to the `streaming_server.py` and embedded in each streamed frame, enabling downstream computer vision analysis to precisely correlate visual events with the video timeline and react to playback lifecycle events. This also facilitates client-side features like auto-closing on video completion.
