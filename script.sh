#!/usr/bin/env bash

set -euo pipefail

.venv/bin/python src/main.py \
  --backend picamera2 \
  --host 0.0.0.0 \
  --port 8000 \
  --width 1280 \
  --height 720 \
  --confidence 0.35 \
  --detect-every-n-frames 2 &

APP_PID=$!

cleanup() {
  if kill -0 "$APP_PID" 2>/dev/null; then
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority chromium "http://0.0.0.0:8000" \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --start-maximized \
  --kiosk
