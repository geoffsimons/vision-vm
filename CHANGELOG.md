# Changelog

## [v0.2.0] - Current
### Added
- **16.5 FPS ROI Milestone:** Successfully achieved stable 16.5+ FPS with 980x551 cropped streaming performance.
- Introduced FastAPI-based Control API for VM management (Port 8000), replacing the raw TCP command server.
- Refactored VM to be autonomous, handling continuous telemetry polling and UI state enforcement directly within the Control API.
- Added YouTube video start time control to the navigation API.
- Enhanced Chrome remote debugging accessibility via `socat` bridge (Port 9222).
- Implemented dynamic Region-of-Interest (ROI) capture with persistence.
- Streamlined headless display output by hiding Fluxbox and Chrome UI elements.
- Implemented end-to-end video duration and status management across controller, streamer, and client.
- Embedded video playhead telemetry directly into streaming frames.
- Enabled client-side display of video playhead telemetry in the stream verification tool.
- Improved video resume logging in `remote_controller.py`.
- Refactored Chrome controller to use Playwright's async API for improved robustness and maintainability.

### Fixed
- Resolved 'Fatal server error' in Xvfb by clearing X11 lock files in `reset-chrome.sh` during startup.

## [v0.2.0] - Current
### Added
- **16.5 FPS ROI Milestone:** Successfully achieved stable 16.5+ FPS with 980x551 cropped streaming performance.
- Implemented TCP command server for ROI management and VM telemetry (Port 5556).
- Enhanced Chrome remote debugging accessibility via `socat` bridge (Port 9222).
- Implemented dynamic Region-of-Interest (ROI) capture with persistence.
- Streamlined headless display output by hiding Fluxbox and Chrome UI elements.
- Implemented end-to-end video duration and status management across controller, streamer, and client.
- Embedded video playhead telemetry directly into streaming frames.
- Enabled client-side display of video playhead telemetry in the stream verification tool.
- Improved video resume logging in `remote_controller.py`.

### Fixed
- Resolved 'Fatal server error' in Xvfb by clearing X11 lock files in `reset-chrome.sh` during startup.

## [v0.2.0] - Current
### Added
- **16.5 FPS ROI Milestone:** Successfully achieved stable 16.5+ FPS with 980x551 cropped streaming performance.
- Implemented TCP command server for ROI management and VM telemetry (Port 5556).
- Enhanced Chrome remote debugging accessibility via `socat` bridge (Port 9222).
- Implemented dynamic Region-of-Interest (ROI) capture with persistence.
- Streamlined headless display output by hiding Fluxbox and Chrome UI elements.

### Fixed
- Resolved 'Fatal server error' in Xvfb by clearing X11 lock files in `reset-chrome.sh` during startup.

## [v0.1.0]
### Added
- Initial project setup including Docker configuration and Xvfb environment.
- Basic Chrome installation and entrypoint script.
