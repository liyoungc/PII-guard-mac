#!/bin/bash
# Install PII Guard for Mac from source. Safe to re-run (idempotent).
#   1. Python engine + Rapid-MLX into an isolated venv (does not touch any other Rapid-MLX install)
#   2. Menu bar app built with Swift and copied to ~/Applications
set -euo pipefail
cd "$(dirname "$0")/.."

fail() { echo "ERROR: $*" >&2; exit 1; }
[ "$(uname -s)" = "Darwin" ] || fail "macOS only."
[ "$(uname -m)" = "arm64" ] || fail "Apple Silicon (arm64) is required: MLX does not run on Intel Macs."
[ "$(sw_vers -productVersion | cut -d. -f1)" -ge 14 ] || fail "macOS 14 or later is required."
command -v swift >/dev/null || fail "Swift not found. Install the Xcode Command Line Tools: xcode-select --install"
command -v uv >/dev/null || fail "uv not found. Install it with: brew install uv   (or see https://docs.astral.sh/uv/)"

HOME_DIR="$HOME/Library/Application Support/PII-guard-mac"
mkdir -p "$HOME_DIR"
echo "==> Python engine → $HOME_DIR/venv"
uv venv --quiet --allow-existing --python 3.12 "$HOME_DIR/venv"
uv pip install --quiet --python "$HOME_DIR/venv/bin/python" --reinstall-package piiguard-mac ./engine
"$HOME_DIR/venv/bin/piiguard" info >/dev/null || fail "engine self-check failed"

echo "==> Menu bar app"
APP="$(scripts/build-app.sh | tail -1)"
mkdir -p "$HOME/Applications"
pkill -x PIIGuardMac 2>/dev/null || true
ditto "$APP" "$HOME/Applications/PII Guard.app"

echo "==> Done."
"$HOME_DIR/venv/bin/piiguard" models | /usr/bin/python3 -c '
import json,sys
d=json.load(sys.stdin)
print("This Mac: %s GB RAM. Recommended model: %s" % (d["ram_gb"], d["recommended"] or "(see Settings > Model)"))'
echo "Open it with:  open \"$HOME/Applications/PII Guard.app\"   (look for the eye icon in the menu bar)"
