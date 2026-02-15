FROM python:3.11-slim-bookworm

# ── System dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        xvfb \
        fluxbox \
        dbus-x11 \
        x11vnc \
        net-tools \
        libnss3 \
        libgconf-2-4 \
        libxi6 \
        libxrandr2 \
        libxss1 \
        libxtst6 \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libgtk-3-0 \
        libvncserver-dev \
        socat \
    && rm -rf /var/lib/apt/lists/*

# ── Google Chrome (stable, official repo) ────────────────────────────────────
RUN wget -qO - https://dl.google.com/linux/linux_signing_key.pub \
        | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] \
        http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# ── Python packages (from shared requirements.txt) ─────────────────────────
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r /app/requirements.txt

# ── Playwright (OS deps + Chromium binary) ─────────────────────────────────
RUN playwright install-deps \
    && playwright install chromium

# ── Application layout ──────────────────────────────────────────────────────
COPY entrypoint.sh capture_heartbeat.py streaming_server.py reset-chrome.sh ./
RUN chmod +x entrypoint.sh reset-chrome.sh

# ── Fluxbox (no toolbar, no window decorations) ────────────────────────────
RUN mkdir -p ~/.fluxbox
COPY fluxbox-init /root/.fluxbox/init

RUN mkdir -p /captures

# ── VNC password file ────────────────────────────────────────────────────────
RUN mkdir -p ~/.vnc && x11vnc -storepasswd vision ~/.vnc/passwd

ENV DISPLAY=:99
ENV CHROME_USER_DATA=/chrome-data

ENTRYPOINT ["./entrypoint.sh"]
