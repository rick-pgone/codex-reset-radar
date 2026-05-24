#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.11}"
PROJECT_NAME="${PROJECT_NAME:-codex-reset-radar}"

cd "$ROOT_DIR"

"$PYTHON_BIN" "$ROOT_DIR/scripts/update_reset_radar.py" --cadence-hours 12
"$ROOT_DIR/scripts/package_site.sh"

if command -v npx >/dev/null 2>&1; then
  npx wrangler pages deploy "$ROOT_DIR/dist" \
    --project-name "$PROJECT_NAME" \
    --branch main \
    --commit-dirty=true
else
  echo "npx is not available; skipped Cloudflare Pages deploy." >&2
  exit 1
fi

if [[ "${PUSH_TO_GIT:-0}" == "1" ]] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add data/latest.json
  if git diff --cached --quiet; then
    echo "No data changes to commit."
  else
    git commit -m "Update reset radar data"
    git push
  fi
fi
