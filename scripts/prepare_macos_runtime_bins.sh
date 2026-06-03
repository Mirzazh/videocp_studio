#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
CACHE="$ROOT/.build/runtime-bin-cache"
DOWNLOADS="$CACHE/downloads"
BIN="$CACHE/bin"
BGUTIL="$CACHE/bgutil-ytdlp-pot-provider"
DENO_CACHE="$CACHE/bgutil-deno-cache"
BGUTIL_USER_CACHE="$CACHE/bgutil-user-cache"
DENO_VERSION="2.8.1"
BGUTIL_VERSION="1.3.1"

mkdir -p "$DOWNLOADS" "$BIN"

download_zip_binary() {
  local name="$1"
  local url="$2"
  local archive="$DOWNLOADS/$name.zip"
  if [[ ! -x "$BIN/$name" ]]; then
    curl -fL --retry 3 -o "$archive" "$url"
    unzip -oq "$archive" -d "$BIN"
    chmod 755 "$BIN/$name"
  fi
}

download_zip_binary \
  ffmpeg \
  "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip"
download_zip_binary \
  ffprobe \
  "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffprobe.zip"
download_zip_binary \
  deno \
  "https://github.com/denoland/deno/releases/download/v$DENO_VERSION/deno-aarch64-apple-darwin.zip"

if [[ ! -f "$BGUTIL/server/src/generate_once.ts" ]]; then
  rm -rf "$BGUTIL"
  git clone --depth 1 --branch "$BGUTIL_VERSION" \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    "$BGUTIL"
fi

if [[ ! -e "$BGUTIL/server/node_modules/commander" ]]; then
  rm -rf "$BGUTIL/server/node_modules"
  (
    cd "$BGUTIL/server"
    PATH="$BIN:$PATH" deno install --prod --frozen
  )
fi

if [[ ! -f "$DENO_CACHE/npm/registry.npmjs.org/commander/registry.json" ]]; then
  rm -rf "$DENO_CACHE" "$BGUTIL_USER_CACHE"
  mkdir -p "$DENO_CACHE"
  XDG_CACHE_HOME="$BGUTIL_USER_CACHE" DENO_DIR="$DENO_CACHE" "$BIN/deno" run \
    --allow-env \
    --allow-net \
    --allow-ffi="$BGUTIL/server/node_modules" \
    --allow-write="$BGUTIL_USER_CACHE/bgutil-ytdlp-pot-provider" \
    --allow-read="$BGUTIL_USER_CACHE/bgutil-ytdlp-pot-provider,$BGUTIL/server/node_modules" \
    "$BGUTIL/server/src/generate_once.ts" \
    --version >/dev/null
  rm -rf "$BGUTIL_USER_CACHE"
fi

"$BIN/ffmpeg" -version >/dev/null
"$BIN/ffprobe" -version >/dev/null
"$BIN/deno" --version >/dev/null
