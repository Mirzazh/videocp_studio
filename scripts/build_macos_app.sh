#!/bin/zsh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
APP="$ROOT/dist/VideocpScheduler.app"
RUNTIME_CACHE="$HOME/Library/Caches/videocp/runtime"

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
mkdir -p "$RUNTIME_CACHE"
rsync -a --delete "$ROOT/videocp/" "$RUNTIME_CACHE/videocp/"
rsync -a --delete "$ROOT/.venv/lib/python3.12/site-packages/" "$RUNTIME_CACHE/site-packages/"
readlink "$ROOT/.venv/bin/python3" > "$RUNTIME_CACHE/python-path"
"$ROOT/scripts/prepare_macos_runtime_bins.sh"
mkdir -p "$APP/Contents/Resources/runtime/bin"
rsync -a --delete "$ROOT/.build/runtime-bin-cache/bin/" "$APP/Contents/Resources/runtime/bin/"
rsync -a --delete \
  --exclude='.git/' \
  "$ROOT/.build/runtime-bin-cache/bgutil-ytdlp-pot-provider/server/" \
  "$APP/Contents/Resources/runtime/bgutil-server/"
if [[ -d "$APP/Contents/Resources/runtime/bgutil-deno-cache" ]]; then
  chmod -R u+w "$APP/Contents/Resources/runtime/bgutil-deno-cache"
fi
rm -rf "$APP/Contents/Resources/runtime/bgutil-deno-cache"
rsync -a \
  "$ROOT/.build/runtime-bin-cache/bgutil-deno-cache/" \
  "$APP/Contents/Resources/runtime/bgutil-deno-cache/"
cp "$ROOT/.build/runtime-bin-cache/bgutil-ytdlp-pot-provider/LICENSE" \
  "$APP/Contents/Resources/runtime/bgutil-server/LICENSE"
CLI_SOURCE="$(command -v tencent-channel-cli || true)"
if [[ -n "$CLI_SOURCE" && -f "$CLI_SOURCE" ]]; then
  cp -L "$CLI_SOURCE" "$APP/Contents/Resources/runtime/bin/tencent-channel-cli"
  chmod 755 "$APP/Contents/Resources/runtime/bin/tencent-channel-cli"
fi
rm -rf "$ROOT/.build/module-cache"
ICONSET="$ROOT/.build/VideocpStudio.iconset"
ICON="$APP/Contents/Resources/AppIcon.icns"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"

ICON_MAKER="$ROOT/.build/IconMaker.swift"
ICON_MAKER_BIN="$ROOT/.build/IconMaker"
cat > "$ICON_MAKER" <<'SWIFT'
import AppKit

let output = URL(fileURLWithPath: CommandLine.arguments[1])
let size = CGFloat(Int(CommandLine.arguments[2]) ?? 1024)
let image = NSImage(size: NSSize(width: size, height: size))
image.lockFocus()

let rect = NSRect(x: 0, y: 0, width: size, height: size)
NSColor.clear.setFill()
rect.fill()

let scale = size / 1024.0
func r(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> NSRect {
    NSRect(x: x * scale, y: y * scale, width: w * scale, height: h * scale)
}

let bg = NSBezierPath(roundedRect: r(88, 88, 848, 848), xRadius: 210 * scale, yRadius: 210 * scale)
let gradient = NSGradient(colors: [
    NSColor(calibratedRed: 0.08, green: 0.47, blue: 0.95, alpha: 1),
    NSColor(calibratedRed: 0.08, green: 0.72, blue: 0.62, alpha: 1)
])!
gradient.draw(in: bg, angle: -45)

NSColor.white.withAlphaComponent(0.96).setFill()
NSBezierPath(roundedRect: r(250, 292, 390, 284), xRadius: 54 * scale, yRadius: 54 * scale).fill()

let play = NSBezierPath()
play.move(to: NSPoint(x: 410 * scale, y: 362 * scale))
play.line(to: NSPoint(x: 410 * scale, y: 506 * scale))
play.line(to: NSPoint(x: 530 * scale, y: 434 * scale))
play.close()
NSColor(calibratedRed: 0.08, green: 0.47, blue: 0.95, alpha: 1).setFill()
play.fill()

NSColor.white.setFill()
NSBezierPath(ovalIn: r(572, 216, 236, 236)).fill()
let arrow = NSBezierPath()
arrow.lineWidth = 42 * scale
arrow.lineCapStyle = .round
arrow.lineJoinStyle = .round
arrow.move(to: NSPoint(x: 690 * scale, y: 408 * scale))
arrow.line(to: NSPoint(x: 690 * scale, y: 260 * scale))
arrow.move(to: NSPoint(x: 690 * scale, y: 260 * scale))
arrow.line(to: NSPoint(x: 635 * scale, y: 315 * scale))
arrow.move(to: NSPoint(x: 690 * scale, y: 260 * scale))
arrow.line(to: NSPoint(x: 745 * scale, y: 315 * scale))
NSColor(calibratedRed: 0.08, green: 0.66, blue: 0.56, alpha: 1).setStroke()
arrow.stroke()

NSColor.white.withAlphaComponent(0.72).setFill()
NSBezierPath(roundedRect: r(258, 650, 510, 58), xRadius: 29 * scale, yRadius: 29 * scale).fill()
NSColor.white.withAlphaComponent(0.45).setFill()
NSBezierPath(roundedRect: r(258, 744, 360, 46), xRadius: 23 * scale, yRadius: 23 * scale).fill()

image.unlockFocus()
let rep = NSBitmapImageRep(data: image.tiffRepresentation!)!
let data = rep.representation(using: .png, properties: [:])!
try! data.write(to: output)
SWIFT

xcrun swiftc "$ICON_MAKER" -o "$ICON_MAKER_BIN" -framework AppKit -target arm64-apple-macosx14.0
for size in 16 32 128 256 512; do
  "$ICON_MAKER_BIN" "$ICONSET/icon_${size}x${size}.png" "$size"
  double=$((size * 2))
  "$ICON_MAKER_BIN" "$ICONSET/icon_${size}x${size}@2x.png" "$double"
done
/usr/bin/iconutil -c icns "$ICONSET" -o "$ICON"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>zh_CN</string>
  <key>CFBundleExecutable</key>
  <string>VideocpScheduler</string>
  <key>CFBundleIdentifier</key>
  <string>local.videocp.scheduler</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Videocp Studio</string>
  <key>CFBundleDisplayName</key>
  <string>Videocp Studio</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.1.6</string>
  <key>CFBundleVersion</key>
  <string>116</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

xcrun swiftc -parse-as-library "$ROOT/macos_app/VideocpStudioAppV2.swift" \
  -o "$APP/Contents/MacOS/VideocpScheduler" \
  -framework SwiftUI \
  -framework AppKit \
  -module-cache-path "$ROOT/.build/module-cache" \
  -target arm64-apple-macosx14.0

plutil -lint "$APP/Contents/Info.plist"
echo "$APP"
