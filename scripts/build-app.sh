#!/bin/bash
# Build "PII Guard.app" from source into ./build (ad-hoc signed, no Apple Developer account needed).
set -euo pipefail
cd "$(dirname "$0")/.."
swift build -c release --package-path app
APP="build/PII Guard.app"
mkdir -p "$APP/Contents/MacOS"
cp app/.build/release/PIIGuardMac "$APP/Contents/MacOS/PIIGuardMac"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>PII Guard</string>
  <key>CFBundleDisplayName</key><string>PII Guard</string>
  <key>CFBundleIdentifier</key><string>io.github.liyoungc.pii-guard-mac</string>
  <key>CFBundleExecutable</key><string>PIIGuardMac</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
codesign --force --sign - "$APP" >/dev/null 2>&1
echo "$APP"
