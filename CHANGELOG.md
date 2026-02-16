# Changelog

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
