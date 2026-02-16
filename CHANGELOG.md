# Changelog

## [v0.2.0] - Current
### Added
- Introduced TCP command server for ROI management and VM telemetry, exposing port 5556 for external access.
- Enhanced YouTube video playback control, including autoplay suppression, player focus, and dynamic fullscreen (Theater Mode) activation.
- Streamlined headless display output by hiding Fluxbox and Chrome UI elements for pure content capture.
- Implemented dynamic Region-of-Interest (ROI) capture with change detection, persistence, and an explicit reset utility.
- Successfully achieved 16.5+ FPS with 980x551 cropped streaming performance.

### Fixed
- Resolved 'Fatal server error' in Xvfb by clearing X11 lock files in `reset-chrome.sh` during startup.

## [v0.2.0] - Current
### Added
- Implemented Chrome remote debugging on Port 9222.
- Added `socat` bridge to handle Chrome binding issues, allowing external access to the remote debugging port.
- Implemented Region-of-Interest (ROI) capture logic for targeted vision analysis.
- Successfully achieved 16.5+ FPS with 980x551 cropped streaming performance.

### Fixed
- Resolved 'Fatal server error' in Xvfb by clearing X11 lock files in `reset-chrome.sh` during startup.

## [v0.1.0]
### Added
- Initial project setup including Docker configuration and Xvfb environment.
- Basic Chrome installation and entrypoint script.
