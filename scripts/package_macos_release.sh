#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
APP_NAME="Videocp Studio"
SOURCE_APP="$ROOT/dist/VideocpScheduler.app"
RELEASE_ROOT="$ROOT/release"
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/videocp-release.XXXXXX")"
cleanup() {
  chmod -R u+w "$TEMP_ROOT" 2>/dev/null || true
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT
STAGING="$TEMP_ROOT/$APP_NAME"
APP="$STAGING/$APP_NAME.app"
RUNTIME="$APP/Contents/Resources/runtime"
PYTHON_SOURCE="$(dirname "$(dirname "$(readlink "$ROOT/.venv/bin/python3")")")"
SITE_PACKAGES="$ROOT/.venv/lib/python3.12/site-packages"
ZIP="$RELEASE_ROOT/Videocp-Studio-1.0.6-macOS-arm64.zip"
CLI_SOURCE="$(command -v tencent-channel-cli || true)"

if [[ -z "$CLI_SOURCE" || ! -f "$CLI_SOURCE" ]]; then
  echo "tencent-channel-cli is required to build the distributable app." >&2
  exit 1
fi

"$ROOT/scripts/build_macos_app.sh"
rm -f "$ZIP"
mkdir -p "$STAGING"
ditto "$SOURCE_APP" "$APP"
mkdir -p "$RUNTIME"
RUNTIME="$(cd "$RUNTIME" && pwd -P)"
mkdir -p "$RUNTIME/bin"
cp -L "$CLI_SOURCE" "$RUNTIME/bin/tencent-channel-cli"
chmod 755 "$RUNTIME/bin/tencent-channel-cli"
for dependency in ffmpeg ffprobe deno; do
  if [[ ! -x "$RUNTIME/bin/$dependency" ]]; then
    echo "Bundled runtime dependency is missing: $dependency" >&2
    exit 1
  fi
done
if [[ ! -f "$RUNTIME/bgutil-server/src/generate_once.ts" ]]; then
  echo "Bundled YouTube helper runtime is missing." >&2
  exit 1
fi
if [[ ! -e "$RUNTIME/bgutil-server/node_modules/commander" ]]; then
  echo "Bundled YouTube helper dependencies are incomplete." >&2
  exit 1
fi
if [[ ! -f "$RUNTIME/bgutil-deno-cache/npm/registry.npmjs.org/commander/registry.json" ]]; then
  echo "Bundled YouTube helper Deno cache is missing." >&2
  exit 1
fi
rsync -a --delete \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  "$ROOT/videocp/" "$RUNTIME/videocp/"
rsync -a --delete \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='_pytest/' \
  --exclude='pytest/' \
  --exclude='pytest-*.dist-info/' \
  --exclude='pip/' \
  --exclude='pip-*.dist-info/' \
  --exclude='__editable__*' \
  --exclude='videocp-*.dist-info/' \
  "$SITE_PACKAGES/" "$RUNTIME/site-packages/"
rsync -a --delete \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='include/' \
  --exclude='share/' \
  --exclude='lib/pkgconfig/' \
  --exclude='lib/python3.12/site-packages/' \
  --exclude='test/' \
  --exclude='tests/' \
  --exclude='idlelib/' \
  --exclude='tkinter/' \
  --exclude='tcl*' \
  "$PYTHON_SOURCE/" "$RUNTIME/python/"

PATH="$RUNTIME/bin:/usr/bin:/bin" \
PYTHONPATH="$RUNTIME:$RUNTIME/site-packages" \
PYTHONDONTWRITEBYTECODE=1 \
VIDEOCP_BUNDLED_BIN="$RUNTIME/bin" \
"$RUNTIME/python/bin/python3" - <<'PY'
import dotenv
import httpx
import playwright
import qrcode
import requests
import yaml
import yt_dlp
from videocp.cli import main
from videocp.publisher import _find_ffmpeg, _find_tencent_channel_cli

assert callable(main)
assert _find_ffmpeg()
assert _find_tencent_channel_cli()
PY

BGUTIL_USER_CACHE="$TEMP_ROOT/bgutil-user-cache"
mkdir -p "$BGUTIL_USER_CACHE"
BGUTIL_USER_CACHE="$(cd "$BGUTIL_USER_CACHE" && pwd -P)"
BGUTIL_VERSION="$(
  cd "$RUNTIME/bgutil-server"
  XDG_CACHE_HOME="$BGUTIL_USER_CACHE" \
  DENO_DIR="$RUNTIME/bgutil-deno-cache" \
  DENO_NO_PROMPT=1 \
  DENO_NO_UPDATE_CHECK=1 \
  "$RUNTIME/bin/deno" run \
    --cached-only \
    --allow-env \
    --allow-net \
    --allow-ffi="$RUNTIME/bgutil-server/node_modules" \
    --allow-write="$BGUTIL_USER_CACHE" \
    --allow-read="$BGUTIL_USER_CACHE,$RUNTIME/bgutil-server/node_modules" \
    "$RUNTIME/bgutil-server/src/generate_once.ts" \
    --version
)"
if [[ "$BGUTIL_VERSION" != "1.3.1" ]]; then
  echo "Bundled YouTube helper failed its offline runtime check." >&2
  exit 1
fi

cat > "$STAGING/README.txt" <<'TXT'
Videocp Studio

系统要求：
- Apple Silicon Mac（M1、M2、M3、M4 或更新型号）
- macOS 14 或更新版本
- Google Chrome

安装：
1. 将 “Videocp Studio.app” 拖入“应用程序”目录。
2. 首次打开时，如果 macOS 提示无法验证开发者，请在“系统设置 > 隐私与安全性”中允许打开。
3. 打开 App，在下载页配置 YouTube Cookie，在发布页配置腾讯频道 Token。

说明：
- App 不包含打包者的 Cookie、Token、下载记录或发布记录。
- 每位用户的配置保存在自己的 ~/Library/Application Support/Videocp Studio/ 目录中。
- App 已内置 yt-dlp、ffmpeg、ffprobe、Deno、YouTube 辅助运行时、预热缓存和腾讯频道 CLI。
- 填入腾讯频道 Token 后，使用发布页的“检查登录”确认账号状态。
TXT

cat > "$STAGING/THIRD_PARTY_NOTICES.txt" <<'TXT'
Videocp Studio third-party runtime notices

This package bundles third-party runtime components for convenience:

- FFmpeg and FFprobe 8.1.1 static builds
  Project: https://ffmpeg.org/
  macOS arm64 builds: https://ffmpeg.martin-riedl.de/
  License information: https://ffmpeg.org/legal.html

- Deno 2.8.1
  Project: https://github.com/denoland/deno
  License: MIT

- bgutil-ytdlp-pot-provider 1.3.1
  Project: https://github.com/Brainicism/bgutil-ytdlp-pot-provider
  License: GPL-3.0-only

- tencent-channel-cli 1.0.7
  Distributed with the Tencent channel community skill:
  https://connect.qq.com/skills/tencent-channel-community.zip
TXT

find -L "$APP" -type l -print0 | xargs -0 rm -f
/usr/bin/xattr -cr "$APP" 2>/dev/null || true
/usr/bin/codesign --force --deep --sign - "$APP"
/usr/bin/codesign --verify --deep --strict "$APP"
(
  cd "$TEMP_ROOT"
  /usr/bin/zip -qry -X -y "$ZIP" "$(basename "$STAGING")"
)

echo "$ZIP"
