# Architecture Decisions

## State-Slave Architecture
The streaming server utilizes a "State-Slave" architecture. The server acts as a passive transmitter of the current state (video frames and metadata), while the client manages the connection and requests. This simplifies server logic and ensures that the server doesn't get overwhelmed by slow clients.

## Shift from UDP to TCP for ROI Management
The ROI Management API (Port 5556) was moved from UDP to TCP. While UDP offers lower latency, the reliability issues (dropped packets leading to inconsistent ROI states) outweighed the speed benefits for management commands. TCP ensures all ROI updates are received and processed in order.

## PNG-over-TCP for Video Frames
Video frames are transmitted as PNG-encoded data over TCP on Port 5555. PNG provides lossless compression, which is critical for computer vision tasks where compression artifacts could interfere with feature detection. TCP guarantees the delivery and ordering of frames.

## Headless Display Configuration
The system uses Xvfb on Display :99 for headless Chrome rendering. This provides a stable virtual display environment within the Docker container without requiring a physical monitor or GPU.
