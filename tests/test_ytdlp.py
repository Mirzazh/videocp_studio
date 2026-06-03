from pathlib import Path
from types import SimpleNamespace

import pytest

import videocp.app as app
import videocp.ytdlp as ytdlp
from videocp.errors import DownloadError
from videocp.models import ParsedInput


def test_bilibili_space_is_playlist_url():
    assert ytdlp.is_ytdlp_playlist_url("https://space.bilibili.com/7612168")
    assert ytdlp.is_ytdlp_playlist_url("https://space.bilibili.com/7612168/video")


def test_bilibili_playlist_entry_builds_video_url():
    assert ytdlp._entry_url({"id": "BV1demo", "ie_key": "BiliBili"}) == "https://www.bilibili.com/video/BV1demo"


def test_download_with_ytdlp_prioritizes_resolution_before_codec(tmp_path: Path, monkeypatch):
    commands = []
    output_path = tmp_path / "video.mp4"

    class FakeResult:
        returncode = 0
        stderr = ""

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        output_path.write_bytes(b"video")
        return FakeResult()

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    ytdlp.download_with_ytdlp("https://www.youtube.com/watch?v=example", output_path, timeout_secs=10)

    assert "--ignore-config" in commands[0]
    format_arg = commands[0][commands[0].index("-f") + 1]
    assert "best" in format_arg
    sort_arg = commands[0][commands[0].index("-S") + 1]
    assert sort_arg.split(",")[:2] == ["res", "fps"]
    assert "vcodec:h264" in sort_arg


def test_app_youtube_download_uses_longer_subprocess_timeout(tmp_path: Path, monkeypatch):
    captured = {}
    parsed = ParsedInput(
        raw_input="https://www.youtube.com/watch?v=abc",
        extracted_url="https://www.youtube.com/watch?v=abc",
        canonical_url="https://www.youtube.com/watch?v=abc",
        provider_key="ytdlp",
    )
    monkeypatch.setattr(
        app,
        "fetch_ytdlp_metadata",
        lambda *args, **kwargs: ytdlp.YtdlpMetadata(
            id="abc",
            title="title",
            uploader="author",
            site="youtube",
            url=parsed.canonical_url,
            duration_secs=10,
            formats_count=3,
        ),
    )

    def fake_download_with_ytdlp(*, output_path: Path, timeout_secs: int, **kwargs):
        captured["timeout_secs"] = timeout_secs
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"video")

    monkeypatch.setattr(app, "download_with_ytdlp", fake_download_with_ytdlp)

    app._download_ytdlp_input(
        parsed=parsed,
        browser_config=SimpleNamespace(),
        output_dir=tmp_path,
        timeout_secs=30,
    )

    assert captured["timeout_secs"] == 300


def test_app_youtube_timeout_is_not_reported_as_cookie_setup_failure(tmp_path: Path, monkeypatch):
    parsed = ParsedInput(
        raw_input="https://www.youtube.com/watch?v=abc",
        extracted_url="https://www.youtube.com/watch?v=abc",
        canonical_url="https://www.youtube.com/watch?v=abc",
        provider_key="ytdlp",
    )
    monkeypatch.setattr(
        app,
        "fetch_ytdlp_metadata",
        lambda *args, **kwargs: ytdlp.YtdlpMetadata(
            id="abc",
            title="title",
            uploader="author",
            site="youtube",
            url=parsed.canonical_url,
            duration_secs=10,
            formats_count=3,
        ),
    )
    monkeypatch.setattr(
        app,
        "download_with_ytdlp",
        lambda **kwargs: (_ for _ in ()).throw(DownloadError("yt-dlp download timed out after 300 seconds")),
    )

    with pytest.raises(DownloadError) as exc:
        app._download_ytdlp_input(
            parsed=parsed,
            browser_config=SimpleNamespace(),
            output_dir=tmp_path,
            timeout_secs=30,
        )

    assert "YouTube 下载超时" in str(exc.value)
    assert "YouTube 需要 Cookie" not in str(exc.value)
    assert app._is_ytdlp_setup_error(str(exc.value)) is False


def test_fetch_ytdlp_metadata_ignores_empty_formats_and_accepts_extractor_args(monkeypatch):
    commands = []

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout='{"id":"abc","title":"标题","uploader":"作者","extractor_key":"Youtube","formats":[]}',
        )

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    meta = ytdlp.fetch_ytdlp_metadata(
        "https://www.youtube.com/shorts/abc",
        extractor_args="youtube:player_client=web",
    )

    assert "--ignore-no-formats-error" in commands[0]
    assert commands[0][commands[0].index("--extractor-args") + 1] == "youtube:player_client=web"
    assert meta.id == "abc"
    assert meta.formats_count == 0


def test_fetch_ytdlp_metadata_adds_bundled_youtube_helper(monkeypatch):
    commands = []

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout='{"id":"abc","title":"标题","uploader":"作者","extractor_key":"Youtube","formats":[]}',
        )

    monkeypatch.setenv("VIDEOCP_BUNDLED_BGUTIL_SERVER", "/Applications/Videocp Studio.app/runtime/bgutil-server")
    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    ytdlp.fetch_ytdlp_metadata("https://www.youtube.com/shorts/abc")

    assert "youtubepot-bgutilscript:server_home=/Applications/Videocp Studio.app/runtime/bgutil-server" in commands[0]


def test_expand_ytdlp_playlist_can_sort_by_popularity(monkeypatch):
    commands = []

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=(
                '{"id":"low","view_count":10,"channel":"c"}\n'
                '{"id":"high","view_count":100,"channel":"c"}\n'
                '{"id":"mid","view_count":50,"channel":"c"}\n'
            ),
        )

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    result = ytdlp.expand_ytdlp_playlist("https://www.youtube.com/@demo/videos", max_videos=2, order="popular")

    assert "--ignore-config" in commands[0]
    assert result.video_urls == [
        "https://www.youtube.com/watch?v=high",
        "https://www.youtube.com/watch?v=mid",
    ]


def test_expand_bilibili_playlist_requests_click_order_for_popular(monkeypatch):
    commands = []

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout='{"id":"BV1demo","ie_key":"BiliBili"}\n',
        )

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    result = ytdlp.expand_ytdlp_playlist("https://space.bilibili.com/7612168/video", max_videos=1, order="popular")

    assert commands[0][-1].endswith("?order=click")
    assert result.video_urls == ["https://www.bilibili.com/video/BV1demo"]


def test_expand_bilibili_playlist_requests_pubdate_order_for_latest(monkeypatch):
    commands = []

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout='{"id":"BV1demo","ie_key":"BiliBili"}\n',
        )

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    result = ytdlp.expand_ytdlp_playlist("https://space.bilibili.com/7612168/video", max_videos=1, order="latest")

    assert commands[0][-1].endswith("?order=pubdate")
    assert result.video_urls == ["https://www.bilibili.com/video/BV1demo"]
