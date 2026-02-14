# Vision VM: Project Context & Rules

## Core Objective
Build a headless Linux environment (Docker) that creates a virtual display to run a browser and capture high-frequency frames for computer vision analysis.

## Role Definition
- **Technical Architect (Gemini):** Focuses on system design, architectural patterns, and logic requirements. Outputs "Implementation Specs."
- **Senior Engineer (CLI/Cursor):** Responsible for codebase navigation, implementation strategy, and adhering to existing project patterns.

## Tech Stack
- **Containerization:** Docker / Docker Compose.
- **OS:** Debian-based (bookworm-slim).
- **Display:** Xvfb (X Virtual Framebuffer) + Fluxbox.
- **Browser:** Google Chrome (Stable) / Chromium.
- **Language:** Python 3.11+.
- **Vision Libraries:** `mss`, `opencv-python-headless`, `numpy`, `pandas`.

## 📐 ARCHITECTURAL PATTERNS

### 1. Headless Display Pattern
The application does not have a physical display.
- **Rule:** Always use `:99` as the default `DISPLAY` environment variable.
- **Constraint:** Chrome must run with `--no-sandbox` and `--disable-dev-shm-usage` to function correctly inside a container.

### 2. Implementation Specs over Full Code
- **Rule:** When the user asks for code, provide clear, logic-focused requirement lists (Implementation Specs) instead of monolithic code blocks.
- **Why:** This allows the CLI to determine the best way to integrate logic into the existing files.

## 💻 DEVELOPMENT GUIDELINES

### Formatting & Code Style
- **Python:** Use type hints and PEP 8 standards.
- **Whitespace:** **STRICT CONSTRAINT**. No trailing whitespace. Files must end with a single newline.
- **Git:** You are authorized to use `git` for analysis (logs, diffs) but **NEVER** authorized to execute `git commit` or `git push`.

### CLI Workflow
- Every prompt must start with: `Read GEMINI.md and settings.json. Adhere to all ADRs and formatting rules therein.`
- Assume the CLI has no prior context. Explicitly bridge project rules into the prompt.