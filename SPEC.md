1. MVP Architectural Vision
The goal is a headless Linux container that tricks Chrome into thinking it has a physical 1080p monitor.

Host: Any Docker-capable machine (MacBook, Linux Server, or eventually Raspberry Pi).

Display Server: Xvfb (X Virtual Framebuffer) creates a virtual :99 display in RAM.

Browser: Chrome/Chromium running in "No Sandbox" mode, outputting to :99.

Capture Engine: Python + mss + OpenCV scraping the :99 buffer.

2. Phased Roadmap
Phase 1: The Headless Foundation
Goal: A Docker image that can launch Chrome in a virtual display and prove "sight" by saving a single .png of the YouTube homepage to a shared volume.

Key Tasks:

Setup Xvfb and a lightweight window manager (fluxbox).

Install Chrome and Python dependencies.

Create a "Heartbeat" script that captures 1 FPS and writes to /output.

Phase 2: Identity & Persistence
Goal: Successfully log into YouTube Premium and ensure the session survives a container restart.

Key Tasks:

Configure a VNC server (temporary) to allow you to manually log in through the virtual screen.

Map a Docker Volume to /root/.config/google-chrome (User Data Directory).

Test that the container can restart and immediately see the "Premium" logo without re-logging.

Phase 3: Performance & Benchmarking
Goal: Optimize the "Capture-to-Disk" pipeline to determine the maximum achievable FPS.

Key Tasks:

Implement a high-speed loop using mss and cv2.

Benchmark the overhead of writing to disk vs. keeping frames in a multiprocessing.Queue.

Refine the "Full Screen" logic to ensure the video player perfectly fills the virtual 1080p buffer.

Phase 4: Portability (ARM/Raspberry Pi)
Goal: Build and run the image on a Raspberry Pi.

Key Tasks:

Transition from google-chrome-stable to chromium-browser.

Create a Multi-Arch Docker build (buildx).

Optimize OpenCV for ARM NEON instructions to maintain FPS.

3. Initial Implementation Spec: Phase 1
When you are ready to start, here is the spec for the first CLI prompt. This focuses solely on the "Foundation."

Architectural Intent: Establish a headless Linux environment with a virtual display buffer and a basic Python capture loop.

Logic-Focused Requirements:

Dockerfile:

Base: python:3.11-slim-bookworm.

System Packages: xvfb, fluxbox, wget, gnupg, libnss3, libgconf-2-4, libxi6.

Chrome: Install google-chrome-stable from the official Google deb repository.

Python: Install mss, numpy, and opencv-python-headless.

Entrypoint Script (entrypoint.sh):

Start Xvfb :99 -screen 0 1920x1080x24 &.

Start fluxbox &.

Export DISPLAY=:99.

Launch Chrome in the background pointing to youtube.com.

Execute the Python capture script.

Python Capture Script (capture.py):

Initialize mss.mss() targeting monitor 1.

Run a loop that captures the screen once per second.

Save the frame as frame_{timestamp}.png to a /captures directory.

Include basic error handling if the display is not found.

4. Performance Expectations
1 FPS: Negligible overhead.

24–30 FPS: Achievable on most modern CPUs, provided the disk I/O (writing .png) isn't the bottleneck.

60 FPS: Likely requires writing raw arrays to a Shared Memory buffer (/dev/shm) or a specialized pipe rather than standard disk writes.