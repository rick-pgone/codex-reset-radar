#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.11}"
PORT="${PORT:-9222}"

echo "Closing Google Chrome so it can restart with remote debugging enabled..."
osascript -e 'tell application "Google Chrome" to quit' >/dev/null 2>&1 || true
sleep 3

echo "Opening kobe Google Chrome with remote debugging on port $PORT..."
open -na "Google Chrome" --args \
  --remote-debugging-port="$PORT" \
  --profile-directory="Default" \
  "https://x.com/thsottiaux"

echo "Waiting for Chrome CDP..."
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

cd "$ROOT_DIR"
"$PYTHON_BIN" "$ROOT_DIR/scripts/update_reset_radar.py" \
  --import-chrome-cdp \
  --chrome-cdp-url "http://127.0.0.1:$PORT" \
  --cadence-hours 12

echo "Imported kobe Chrome X session and refreshed data/latest.json."
