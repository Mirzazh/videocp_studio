import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from videocp.errors import PublishError
from videocp.publisher import (
    MAX_CHANNEL_VIDEO_BYTES,
    _find_ffmpeg,
    _find_tencent_channel_cli,
    _publish_env,
    is_retryable_publish_error,
    prepare_video_for_channel,
    publish_to_channel,
)


def test_publish_env_uses_selected_account_dotenv_over_inherited_token(tmp_path: Path, monkeypatch):
    account_env = tmp_path / "account.env"
    account_env.write_text("QQ_AI_CONNECT_TOKEN=token-for-account-b\n", encoding="utf-8")
    monkeypatch.setenv("QQ_AI_CONNECT_TOKEN", "token-for-account-a")
    monkeypatch.setenv("QQ_AI_CONNECT_DOTENV", str(account_env))

    assert _publish_env()["QQ_AI_CONNECT_TOKEN"] == "token-for-account-b"


def test_publish_to_channel_uses_author_scope_when_ids_are_blank(tmp_path: Path, monkeypatch):
    skill_dir = tmp_path / "skill"
    script = skill_dir / "scripts" / "feed" / "write" / "publish_feed.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_subprocess_run(*args, **kwargs):
        captured["payload"] = json.loads(kwargs["input"])
        return SimpleNamespace(
            stdout=json.dumps({"success": True, "data": {"feed_id": "feed-1", "分享链接": ""}}, ensure_ascii=False),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr("videocp.publisher.subprocess_run", fake_subprocess_run)

    result = publish_to_channel(
        skill_dir=skill_dir,
        video_path=tmp_path / "video.mp4",
        guild_id="",
        channel_id="",
        title="title",
        content="content",
    )

    assert result.success is True
    # Default feed_type=1 (short post): title omitted, content kept as-is
    assert captured["payload"] == {
        "guild_id": 0,
        "channel_id": 0,
        "content": "content",
        "feed_type": 1,
        "video_paths": [{"file_path": str((tmp_path / "video.mp4").resolve())}],
    }


def test_publish_short_post_moves_title_to_content_when_content_empty(tmp_path: Path, monkeypatch):
    skill_dir = tmp_path / "skill"
    script = skill_dir / "scripts" / "feed" / "write" / "publish_feed.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_subprocess_run(*args, **kwargs):
        captured["payload"] = json.loads(kwargs["input"])
        return SimpleNamespace(
            stdout=json.dumps({"success": True, "data": {"feed_id": "feed-2", "分享链接": ""}}, ensure_ascii=False),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr("videocp.publisher.subprocess_run", fake_subprocess_run)

    result = publish_to_channel(
        skill_dir=skill_dir,
        video_path=tmp_path / "video.mp4",
        guild_id="",
        channel_id="",
        title="my video title",
        content="",
        feed_type=1,
    )

    assert result.success is True
    assert captured["payload"]["content"] == "my video title"
    assert "title" not in captured["payload"]
    assert captured["payload"]["feed_type"] == 1


def test_publish_long_post_keeps_title(tmp_path: Path, monkeypatch):
    skill_dir = tmp_path / "skill"
    script = skill_dir / "scripts" / "feed" / "write" / "publish_feed.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_subprocess_run(*args, **kwargs):
        captured["payload"] = json.loads(kwargs["input"])
        return SimpleNamespace(
            stdout=json.dumps({"success": True, "data": {"feed_id": "feed-3", "分享链接": ""}}, ensure_ascii=False),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr("videocp.publisher.subprocess_run", fake_subprocess_run)

    result = publish_to_channel(
        skill_dir=skill_dir,
        video_path=tmp_path / "video.mp4",
        guild_id="",
        channel_id="",
        title="long post title",
        content="body text",
        feed_type=2,
    )

    assert result.success is True
    assert captured["payload"]["title"] == "long post title"
    assert captured["payload"]["content"] == "body text"
    assert captured["payload"]["feed_type"] == 2


def test_publish_parses_feed_id_from_legacy_key(tmp_path: Path, monkeypatch):
    skill_dir = tmp_path / "skill"
    script = skill_dir / "scripts" / "feed" / "write" / "publish_feed.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub\n", encoding="utf-8")

    def fake_subprocess_run(*args, **kwargs):
        return SimpleNamespace(
            stdout=json.dumps({"success": True, "data": {"帖子ID": "legacy-id", "分享链接": "<https://example.com>"}}, ensure_ascii=False),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr("videocp.publisher.subprocess_run", fake_subprocess_run)

    result = publish_to_channel(
        skill_dir=skill_dir,
        video_path=tmp_path / "video.mp4",
        guild_id="",
        channel_id="",
        title="",
        content="text",
    )

    assert result.success is True
    assert result.feed_id == "legacy-id"
    assert result.share_url == "https://example.com"


def test_publish_uses_tencent_channel_cli_when_official_skill_has_no_script(tmp_path: Path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")
    captured: dict[str, object] = {}

    monkeypatch.setattr("videocp.publisher._find_tencent_channel_cli", lambda: "/bin/tencent-channel-cli")
    monkeypatch.setattr("videocp.publisher._find_ffmpeg", lambda: "/opt/homebrew/bin/ffmpeg")

    def fake_subprocess_run(command, **kwargs):
        captured["command"] = command
        captured["input"] = kwargs.get("input")
        return SimpleNamespace(
            stdout=json.dumps({"success": True, "data": {"feed_id": "feed-cli", "share_url": "<https://pd.qq.com/s/x>"}}, ensure_ascii=False),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr("videocp.publisher.subprocess_run", fake_subprocess_run)

    result = publish_to_channel(
        skill_dir=tmp_path / "official-skill",
        video_path=video_path,
        guild_id="123",
        channel_id="456",
        title="",
        content="hello",
    )

    assert result.success is True
    assert result.feed_id == "feed-cli"
    assert result.share_url == "https://pd.qq.com/s/x"
    assert captured["command"] == [
        "/bin/tencent-channel-cli",
        "feed",
        "publish-feed",
        "--json",
        "--feed-type",
        "1",
        "--content",
        "hello",
        "--video",
        str(video_path.resolve()),
        "--guild-id",
        "123",
        "--channel-id",
        "456",
    ]
    assert captured["input"] is None


def test_publish_author_global_cli_adds_yes(tmp_path: Path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")
    captured: dict[str, object] = {}

    monkeypatch.setattr("videocp.publisher._find_tencent_channel_cli", lambda: "/bin/tencent-channel-cli")
    monkeypatch.setattr("videocp.publisher._find_ffmpeg", lambda: "/opt/homebrew/bin/ffmpeg")

    def fake_subprocess_run(command, **kwargs):
        captured["command"] = command
        captured["input"] = kwargs.get("input")
        return SimpleNamespace(
            stdout=json.dumps({"success": True, "data": {"feed_id": "feed-global"}}, ensure_ascii=False),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr("videocp.publisher.subprocess_run", fake_subprocess_run)

    result = publish_to_channel(
        skill_dir=tmp_path / "official-skill",
        video_path=video_path,
        guild_id="",
        channel_id="",
        title="global title",
        content="",
    )

    assert result.success is True
    assert captured["command"] == [
        "/bin/tencent-channel-cli",
        "feed",
        "publish-feed",
        "--json",
        "--feed-type",
        "1",
        "--content",
        "global title",
        "--video",
        str(video_path.resolve()),
        "--yes",
    ]
    assert captured["input"] is None


def test_publish_cli_reports_missing_ffmpeg(tmp_path: Path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")

    monkeypatch.setattr("videocp.publisher._find_tencent_channel_cli", lambda: "/bin/tencent-channel-cli")
    monkeypatch.setattr("videocp.publisher._find_ffmpeg", lambda: "")

    with pytest.raises(PublishError, match="ffmpeg not found"):
        publish_to_channel(
            skill_dir=tmp_path / "official-skill",
            video_path=video_path,
            guild_id="",
            channel_id="",
            title="title",
            content="",
        )


def test_publish_finds_bundled_cli_and_ffmpeg_before_system_paths(tmp_path: Path, monkeypatch):
    bundled_bin = tmp_path / "bin"
    bundled_bin.mkdir()
    bundled_cli = bundled_bin / "tencent-channel-cli"
    bundled_ffmpeg = bundled_bin / "ffmpeg"
    bundled_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    bundled_ffmpeg.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("VIDEOCP_BUNDLED_BIN", str(bundled_bin))

    assert _find_tencent_channel_cli() == str(bundled_cli)
    assert _find_ffmpeg() == str(bundled_ffmpeg)


def test_prepare_video_for_channel_compresses_oversized_video(tmp_path: Path, monkeypatch):
    video_path = tmp_path / "large.mp4"
    with video_path.open("wb") as file:
        file.truncate(MAX_CHANNEL_VIDEO_BYTES + 1)

    monkeypatch.setattr("videocp.publisher._find_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr("videocp.publisher._find_ffprobe", lambda: "/bin/ffprobe")

    def fake_run(command, **kwargs):
        if command[0] == "/bin/ffprobe":
            return SimpleNamespace(returncode=0, stdout="1000\n", stderr="")
        output = Path(command[-1])
        output.write_bytes(b"compressed")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("videocp.publisher.subprocess_run", fake_run)

    prepared, temporary = prepare_video_for_channel(video_path)

    assert temporary is True
    assert prepared.name == "large.upload.mp4"
    assert prepared.read_bytes() == b"compressed"


def test_filesize_publish_error_is_not_retryable():
    assert is_retryable_publish_error("init slice failed: filesize is too big or invalid") is False
    assert is_retryable_publish_error("temporary network timeout") is True
