#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR/data"

cp "$ROOT_DIR/codex-reset-radar.html" "$DIST_DIR/index.html"
cp "$ROOT_DIR/data/latest.json" "$DIST_DIR/data/latest.json"

echo "Packaged site into $DIST_DIR"
