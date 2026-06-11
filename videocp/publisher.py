from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from subprocess import run as subprocess_run

from videocp.errors import PublishError
from videocp.runtime_log import log_info


# Tencent's slice initializer rejects files well below 4 GiB on some accounts.
# Keep the output below 2 GiB with enough room for container-size variance.
MAX_CHANNEL_VIDEO_BYTES = int(1.9 * 1024 * 1024 * 1024)
TARGET_CHANNEL_VIDEO_BYTES = int(1.75 * 1024 * 1024 * 1024)


@dataclass(slots=True)
class PublishResult:
    success: bool
    feed_id: str = ""
    share_url: str = ""
    error: str = ""


def _as_publish_scope_id(value: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        return 0
    return int(raw)


def _find_tencent_channel_cli() -> str:
    bundled_bin = os.environ.get("VIDEOCP_BUNDLED_BIN", "")
    candidates = [
        str(Path(bundled_bin) / "tencent-channel-cli") if bundled_bin else "",
        shutil.which("tencent-channel-cli"),
        str(Path.home() / ".local" / "bin" / "tencent-channel-cli"),
        "/opt/homebrew/bin/tencent-channel-cli",
        "/usr/local/bin/tencent-channel-cli",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def _find_ffmpeg() -> str:
    bundled_bin = os.environ.get("VIDEOCP_BUNDLED_BIN", "")
    candidates = [
        str(Path(bundled_bin) / "ffmpeg") if bundled_bin else "",
        shutil.which("ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def _find_ffprobe() -> str:
    bundled_bin = os.environ.get("VIDEOCP_BUNDLED_BIN", "")
    candidates = [
        str(Path(bundled_bin) / "ffprobe") if bundled_bin else "",
        shutil.which("ffprobe"),
        "/opt/homebrew/bin/ffprobe",
        "/usr/local/bin/ffprobe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def prepare_video_for_channel(video_path: Path) -> tuple[Path, bool]:
    """Return an upload-safe video, transcoding oversized files when needed."""
    video_path = video_path.resolve()
    size = video_path.stat().st_size
    if size <= MAX_CHANNEL_VIDEO_BYTES:
        return video_path, False

    ffmpeg = _find_ffmpeg()
    ffprobe = _find_ffprobe()
    if not ffmpeg or not ffprobe:
        raise PublishError(
            f"视频大小为 {size / 1024 ** 3:.2f} GB，超过频道上传安全上限；"
            "App 未找到内置 ffmpeg/ffprobe，无法自动压缩。"
        )
    probe = subprocess_run(
        [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=_publish_env(),
    )
    try:
        duration = float((probe.stdout or "").strip())
    except ValueError as exc:
        raise PublishError("无法读取超大视频时长，不能安全压缩后上传。") from exc
    if probe.returncode != 0 or duration <= 0:
        raise PublishError("无法读取超大视频时长，不能安全压缩后上传。")

    audio_bitrate = 128_000
    total_bitrate = int(TARGET_CHANNEL_VIDEO_BYTES * 8 / duration)
    video_bitrate = max(350_000, total_bitrate - audio_bitrate)
    temp_dir = Path(tempfile.gettempdir()) / "videocp-publish"
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / f"{video_path.stem}.upload.mp4"
    output_path.unlink(missing_ok=True)
    log_info(
        "publish.video.compress.start",
        input=str(video_path),
        output=str(output_path),
        input_bytes=size,
        target_bytes=TARGET_CHANNEL_VIDEO_BYTES,
        duration_secs=round(duration, 1),
    )
    proc = subprocess_run(
        [
            ffmpeg,
            "-y",
            "-loglevel", "error",
            "-i", str(video_path),
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", str(video_bitrate),
            "-maxrate", str(int(video_bitrate * 1.12)),
            "-bufsize", str(video_bitrate * 2),
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=max(1800, int(duration * 2)),
        env=_publish_env(),
    )
    if proc.returncode != 0 or not output_path.is_file():
        output_path.unlink(missing_ok=True)
        error = (proc.stderr or "").strip()[-600:]
        raise PublishError(f"超大视频自动压缩失败: {error or f'ffmpeg exit {proc.returncode}'}")
    output_size = output_path.stat().st_size
    if output_size > MAX_CHANNEL_VIDEO_BYTES:
        output_path.unlink(missing_ok=True)
        raise PublishError(
            f"自动压缩后文件仍有 {output_size / 1024 ** 3:.2f} GB，超过频道上传上限。"
        )
    log_info(
        "publish.video.compress.complete",
        output=str(output_path),
        output_bytes=output_size,
    )
    return output_path, True


def is_retryable_publish_error(error: str) -> bool:
    value = str(error or "").lower()
    permanent_markers = [
        "filesize is too big",
        "file size is too big",
        "文件过大",
        "超过频道上传",
        "格式无效",
        "invalid filesize",
    ]
    return not any(marker in value for marker in permanent_markers)


def _publish_env() -> dict[str, str]:
    env = {**os.environ}
    dotenv_path = str(env.get("QQ_AI_CONNECT_DOTENV", "") or "").strip()
    if dotenv_path:
        try:
            for raw_line in Path(dotenv_path).expanduser().read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "QQ_AI_CONNECT_TOKEN":
                    env["QQ_AI_CONNECT_TOKEN"] = value.strip().strip("\"'")
                    break
        except OSError:
            pass
    bundled_bin = env.get("VIDEOCP_BUNDLED_BIN", "")
    env["PATH"] = f"{bundled_bin}:/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    return env


def is_login_state_publish_error(error: str) -> bool:
    value = str(error or "").lower()
    markers = [
        "登录态",
        "login",
        "token",
        "151",
        "oidb",
        "apply_media_upload",
        "上传失败",
    ]
    return any(marker.lower() in value for marker in markers)


def check_tencent_login_status(timeout_secs: int = 30) -> PublishResult:
    cli = _find_tencent_channel_cli()
    if not cli:
        return PublishResult(success=False, error="tencent-channel-cli not found")
    try:
        proc = subprocess_run(
            [cli, "login", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout_secs,
            env=_publish_env(),
        )
    except Exception as exc:
        return PublishResult(success=False, error=f"Failed to check Tencent login status: {exc}")
    if proc.returncode != 0:
        return PublishResult(success=False, error=(proc.stderr or proc.stdout or "").strip())
    try:
        payload = json.loads((proc.stdout or "").strip())
    except json.JSONDecodeError:
        return PublishResult(success=False, error="Tencent login status returned invalid JSON")
    data = payload.get("data") if isinstance(payload, dict) else {}
    logged_in = bool(
        isinstance(data, dict)
        and payload.get("success")
        and (data.get("valid") is True or data.get("isLoggedIn") is True)
    )
    if not logged_in:
        return PublishResult(success=False, error="腾讯频道登录态未通过检查")
    return PublishResult(success=True)


def _legacy_publish_to_channel(
    skill_dir: Path,
    video_path: Path,
    guild_id: str,
    channel_id: str,
    title: str,
    content: str,
    feed_type: int,
    timeout_secs: int,
) -> PublishResult:
    script = skill_dir / "scripts" / "feed" / "write" / "publish_feed.py"
    if not script.is_file():
        raise PublishError(f"publish_feed.py not found at {script}. Ensure skill is installed.")

    # Short posts (feed_type=1) have no title; move title text to content.
    if feed_type == 1:
        if not content and title:
            content = title
        title = ""

    payload: dict = {
        "guild_id": _as_publish_scope_id(guild_id),
        "channel_id": _as_publish_scope_id(channel_id),
        "content": content,
        "feed_type": feed_type,
        "video_paths": [{"file_path": str(video_path.resolve())}],
    }
    if title:
        payload["title"] = title

    cwd = str(skill_dir)
    env = _publish_env()

    python = sys.executable

    try:
        proc = subprocess_run(
            [python, str(script)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=timeout_secs,
            cwd=cwd,
            env=env,
        )
    except Exception as exc:
        raise PublishError(f"Failed to run publish_feed.py: {exc}") from exc

    return _parse_publish_process_result(proc)


def _cli_publish_to_channel(
    video_path: Path,
    guild_id: str,
    channel_id: str,
    title: str,
    content: str,
    feed_type: int,
    timeout_secs: int,
) -> PublishResult:
    cli = _find_tencent_channel_cli()
    if not cli:
        raise PublishError("tencent-channel-cli not found. Install it before using publish_method: skill.")
    if not _find_ffmpeg():
        raise PublishError("ffmpeg not found. Install it with: brew install ffmpeg")

    if feed_type == 1:
        if not content and title:
            content = title
        title = ""

    command = [
        cli,
        "feed",
        "publish-feed",
        "--json",
        "--feed-type",
        str(feed_type),
        "--content",
        content,
        "--video",
        str(video_path.resolve()),
    ]
    if guild_id and channel_id:
        command.extend(["--guild-id", str(guild_id), "--channel-id", str(channel_id)])
    if title:
        command.extend(["--title", title])
    # Author global posting is a write action without guild/channel scope. The
    # official skill requires explicit confirmation; for unattended scheduled
    # jobs this confirmation is represented by the user's config choice.
    if not guild_id and not channel_id:
        command.append("--yes")

    try:
        proc = subprocess_run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_secs,
            env=_publish_env(),
        )
    except Exception as exc:
        raise PublishError(f"Failed to run tencent-channel-cli: {exc}") from exc

    return _parse_publish_process_result(proc)


def _parse_publish_process_result(proc) -> PublishResult:
    stdout = (proc.stdout or "").strip()
    if not stdout:
        stderr_hint = (proc.stderr or "").strip()[:500]
        raise PublishError(f"publish command returned no output (exit {proc.returncode}). stderr: {stderr_hint}")

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        raise PublishError(f"publish command returned invalid JSON: {stdout[:200]}")

    if not result.get("success"):
        error = result.get("error", {})
        if isinstance(error, dict):
            error_msg = error.get("message") or error.get("error") or json.dumps(error, ensure_ascii=False)
        else:
            error_msg = str(error or result.get("message") or "unknown error")
        needs_confirm = result.get("needs_confirm", False)
        if needs_confirm:
            raise PublishError(f"Upload requires confirmation: {error_msg}")
        return PublishResult(success=False, error=error_msg)

    data = result.get("data", {})
    if not isinstance(data, dict):
        data = {}
    feed_id = data.get("feed_id", "") or data.get("帖子ID", "")
    share_url = (
        data.get("share_url", "")
        or data.get("分享链接", "")
        or data.get("url", "")
    )
    if isinstance(share_url, str) and share_url.startswith("<") and share_url.endswith(">"):
        share_url = share_url[1:-1]

    return PublishResult(success=True, feed_id=str(feed_id or ""), share_url=str(share_url or ""))


def publish_to_channel(
    skill_dir: Path,
    video_path: Path,
    guild_id: str,
    channel_id: str,
    title: str,
    content: str,
    feed_type: int = 1,
    timeout_secs: int = 300,
) -> PublishResult:
    script = skill_dir / "scripts" / "feed" / "write" / "publish_feed.py"
    if script.is_file():
        return _legacy_publish_to_channel(
            skill_dir=skill_dir,
            video_path=video_path,
            guild_id=guild_id,
            channel_id=channel_id,
            title=title,
            content=content,
            feed_type=feed_type,
            timeout_secs=timeout_secs,
        )
    return _cli_publish_to_channel(
        video_path=video_path,
        guild_id=guild_id,
        channel_id=channel_id,
        title=title,
        content=content,
        feed_type=feed_type,
        timeout_secs=timeout_secs,
    )
