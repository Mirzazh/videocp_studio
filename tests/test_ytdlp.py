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


def test_download_with_ytdlp_uses_quicktime_compatible_youtube_format(tmp_path: Path, monkeypatch):
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
    assert "vcodec^=avc1" in format_arg
    assert "ba[ext=m4a]" in format_arg
    sort_arg = commands[0][commands[0].index("-S") + 1]
    assert sort_arg.split(",")[:2] == ["res", "fps"]
    assert "vcodec:h264" in sort_arg


def test_download_with_ytdlp_keeps_generic_format_for_non_youtube(tmp_path: Path, monkeypatch):
    commands = []
    output_path = tmp_path / "video.mp4"

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        output_path.write_bytes(b"video")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    ytdlp.download_with_ytdlp("https://example.com/video", output_path, timeout_secs=10)

    format_arg = commands[0][commands[0].index("-f") + 1]
    assert format_arg == "bv+ba/b"


def test_download_with_ytdlp_caps_requested_quality(tmp_path: Path, monkeypatch):
    commands = []
    output_path = tmp_path / "video.mp4"

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        output_path.write_bytes(b"video")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    ytdlp.download_with_ytdlp(
        "https://www.youtube.com/watch?v=example",
        output_path,
        timeout_secs=10,
        quality="720",
    )

    format_arg = commands[0][commands[0].index("-f") + 1]
    sort_arg = commands[0][commands[0].index("-S") + 1]
    assert "vcodec^=avc1" in format_arg
    assert sort_arg.startswith("res:720,")


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
        captured["quality"] = kwargs.get("quality")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"video")

    monkeypatch.setattr(app, "download_with_ytdlp", fake_download_with_ytdlp)

    app._download_ytdlp_input(
        parsed=parsed,
        browser_config=SimpleNamespace(),
        output_dir=tmp_path,
        timeout_secs=30,
        quality="1080",
    )

    assert captured["timeout_secs"] == 300
    assert captured["quality"] == "1080"


def test_app_force_redownload_replaces_existing_file(tmp_path: Path, monkeypatch):
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
            formats_count=3,
        ),
    )
    target = tmp_path / "youtube-author" / "abc.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")

    def fake_download_with_ytdlp(*, output_path: Path, **kwargs):
        assert output_path.name == "abc.redownload.mp4"
        output_path.write_bytes(b"new")

    monkeypatch.setattr(app, "download_with_ytdlp", fake_download_with_ytdlp)
    monkeypatch.setattr(app, "probe_video_dimensions", lambda path: (1080, 1920))

    _, artifact = app._download_ytdlp_input(
        parsed=parsed,
        browser_config=SimpleNamespace(),
        output_dir=tmp_path,
        timeout_secs=30,
        force_redownload=True,
    )

    assert artifact.output_path == target
    assert target.read_bytes() == b"new"


def test_app_ytdlp_profile_download_uses_profile_author_for_output_dir(tmp_path: Path, monkeypatch):
    parsed = ParsedInput(
        raw_input="https://www.xiaohongshu.com/explore/abc",
        extracted_url="https://www.xiaohongshu.com/explore/abc",
        canonical_url="https://www.xiaohongshu.com/explore/abc",
        provider_key="ytdlp",
        author_hint="章鱼科普1号",
    )
    monkeypatch.setattr(
        app,
        "fetch_ytdlp_metadata",
        lambda *args, **kwargs: ytdlp.YtdlpMetadata(
            id="abc",
            title="测试视频",
            uploader="6229bfb0000000001000693b",
            site="xiaohongshu",
            url=parsed.canonical_url,
            formats_count=3,
        ),
    )

    def fake_download_with_ytdlp(*, output_path: Path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"video")

    monkeypatch.setattr(app, "download_with_ytdlp", fake_download_with_ytdlp)
    monkeypatch.setattr(app, "probe_video_dimensions", lambda path: (720, 1280))

    extraction, artifact = app._download_ytdlp_input(
        parsed=parsed,
        browser_config=SimpleNamespace(),
        output_dir=tmp_path,
        timeout_secs=30,
    )

    assert extraction.metadata.author == "章鱼科普1号"
    assert artifact.output_path.parent.name == "xiaohongshu-章鱼科普1号"
    assert '"author": "章鱼科普1号"' in artifact.sidecar_path.read_text(encoding="utf-8")


def test_app_retries_low_quality_youtube_metadata_with_web_safari(tmp_path: Path, monkeypatch):
    parsed = ParsedInput(
        raw_input="https://www.youtube.com/watch?v=abc",
        extracted_url="https://www.youtube.com/watch?v=abc",
        canonical_url="https://www.youtube.com/watch?v=abc",
        provider_key="ytdlp",
    )
    metadata_calls = []

    def fake_metadata(url, cookies_file, extractor_args="", remote_components=False):
        metadata_calls.append(extractor_args)
        return ytdlp.YtdlpMetadata(
            id="abc",
            title="title",
            uploader="author",
            site="youtube",
            url=url,
            formats_count=5 if len(metadata_calls) == 1 else 42,
            max_resolution=360 if len(metadata_calls) == 1 else 1080,
        )

    captured = {}

    def fake_download_with_ytdlp(*, output_path: Path, extractor_args: str, **kwargs):
        captured["extractor_args"] = extractor_args
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"video")

    monkeypatch.setattr(app, "fetch_ytdlp_metadata", fake_metadata)
    monkeypatch.setattr(app, "download_with_ytdlp", fake_download_with_ytdlp)
    monkeypatch.setattr(app, "probe_video_dimensions", lambda path: (1080, 1920))

    app._download_ytdlp_input(
        parsed=parsed,
        browser_config=SimpleNamespace(),
        output_dir=tmp_path,
        timeout_secs=30,
        extractor_args="youtube:player_client=mweb;fetch_pot=always",
    )

    assert metadata_calls == [
        "youtube:player_client=mweb;fetch_pot=always",
        "youtube:player_client=web_safari",
    ]
    assert captured["extractor_args"] == "youtube:player_client=web_safari"


def test_app_retries_youtube_403_download_with_alternate_client(tmp_path: Path, monkeypatch):
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
            formats_count=42,
            max_resolution=1080,
        ),
    )
    attempts = []

    def fake_download_with_ytdlp(*, output_path: Path, extractor_args: str, **kwargs):
        attempts.append(extractor_args)
        if len(attempts) == 1:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.with_suffix(".part").write_bytes(b"partial")
            raise DownloadError("yt-dlp download failed: ERROR: unable to download video data: HTTP Error 403: Forbidden")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"video")

    monkeypatch.setattr(app, "download_with_ytdlp", fake_download_with_ytdlp)
    monkeypatch.setattr(app, "probe_video_dimensions", lambda path: (1080, 1920))

    app._download_ytdlp_input(
        parsed=parsed,
        browser_config=SimpleNamespace(),
        output_dir=tmp_path,
        timeout_secs=30,
        extractor_args="youtube:player_client=mweb;fetch_pot=always",
    )

    assert attempts == [
        "youtube:player_client=mweb;fetch_pot=always",
        "youtube:player_client=web_safari",
    ]
    assert not list(tmp_path.rglob("*.part"))


def test_youtube_403_error_message_does_not_claim_cookie_required():
    message = app._youtube_error_message(
        DownloadError("yt-dlp download failed: ERROR: unable to download video data: HTTP Error 403: Forbidden")
    )

    assert "YouTube 临时拒绝" in message
    assert "YouTube 需要 Cookie" not in message


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
    assert meta.max_resolution == 0


def test_fetch_ytdlp_metadata_reports_highest_short_edge(monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=(
                '{"id":"abc","title":"标题","uploader":"作者","extractor_key":"Youtube",'
                '"formats":['
                '{"format_id":"18","width":360,"height":640,"vcodec":"h264"},'
                '{"format_id":"137","width":1080,"height":1920,"vcodec":"h264"},'
                '{"format_id":"140","vcodec":"none","acodec":"m4a"}]}'
            ),
        )

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    meta = ytdlp.fetch_ytdlp_metadata("https://www.youtube.com/shorts/abc")

    assert meta.formats_count == 3
    assert meta.max_resolution == 1080


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
    monkeypatch.setattr(
        ytdlp,
        "_expand_youtube_popular_playlist",
        lambda *args, **kwargs: (_ for _ in ()).throw(ytdlp.DownloadError("temporary failure")),
    )

    result = ytdlp.expand_ytdlp_playlist("https://www.youtube.com/@demo/videos", max_videos=2, order="popular")

    assert "--ignore-config" in commands[0]
    assert result.video_urls == [
        "https://www.youtube.com/watch?v=high",
        "https://www.youtube.com/watch?v=mid",
    ]


def test_expand_ytdlp_playlist_uses_youtube_popular_filter(monkeypatch):
    calls = []

    def fake_popular(url, max_videos, cookies_file):
        calls.append((url, max_videos, cookies_file))
        return ytdlp.YtdlpPlaylistResult(
            video_urls=["https://www.youtube.com/watch?v=popular"],
            uploader="demo",
        )

    monkeypatch.setattr(ytdlp, "_expand_youtube_popular_playlist", fake_popular)
    monkeypatch.setattr(
        ytdlp.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("yt-dlp fallback should not run")),
    )

    result = ytdlp.expand_ytdlp_playlist(
        "https://www.youtube.com/@demo/videos",
        max_videos=2,
        order="popular",
    )

    assert calls == [("https://www.youtube.com/@demo/videos", 2, None)]
    assert result.video_urls == ["https://www.youtube.com/watch?v=popular"]


def test_youtube_popular_filter_accepts_localized_label():
    data = {
        "chipViewModel": {
            "text": "最热门",
            "accessibilityLabel": "最热门",
            "tapCommand": {
                "innertubeCommand": {
                    "continuationCommand": {"token": "popular-token"},
                },
            },
        },
    }

    assert ytdlp._youtube_continuation_token(data, popular_chip=True) == "popular-token"


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


def test_expand_bilibili_playlist_fetches_ranges_beyond_first_25(monkeypatch):
    requested_ranges = []

    def fake_run(cmd, capture_output, text, timeout):
        playlist_range = cmd[cmd.index("--playlist-items") + 1]
        requested_ranges.append(playlist_range)
        start, end = (int(value) for value in playlist_range.split(":"))
        stdout = "\n".join(
            f'{{"id":"BV{index:03d}","ie_key":"BiliBili","channel":"demo"}}'
            for index in range(start, end + 1)
        )
        return SimpleNamespace(returncode=0, stderr="", stdout=stdout)

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    result = ytdlp.expand_ytdlp_playlist(
        "https://space.bilibili.com/7612168/video",
        max_videos=60,
        order="latest",
    )

    assert requested_ranges == ["1:25", "26:50", "51:60"]
    assert len(result.video_urls) == 60
    assert result.video_urls[25] == "https://www.bilibili.com/video/BV026"
    assert result.video_urls[-1] == "https://www.bilibili.com/video/BV060"


def test_expand_bilibili_playlist_stops_when_next_range_is_empty(monkeypatch):
    requested_ranges = []

    def fake_run(cmd, capture_output, text, timeout):
        playlist_range = cmd[cmd.index("--playlist-items") + 1]
        requested_ranges.append(playlist_range)
        stdout = (
            "\n".join(
                f'{{"id":"BV{index:03d}","ie_key":"BiliBili"}}'
                for index in range(1, 26)
            )
            if playlist_range == "1:25"
            else ""
        )
        return SimpleNamespace(returncode=0, stderr="", stdout=stdout)

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)

    result = ytdlp.expand_ytdlp_playlist(
        "https://space.bilibili.com/7612168/video",
        max_videos=80,
        order="latest",
    )

    assert requested_ranges == ["1:25", "26:50"]
    assert len(result.video_urls) == 25


def test_expand_bilibili_playlist_retries_server_block(monkeypatch):
    attempts = []
    sleeps = []

    def fake_run(cmd, capture_output, text, timeout):
        playlist_range = cmd[cmd.index("--playlist-items") + 1]
        attempts.append(playlist_range)
        if playlist_range == "26:50" and attempts.count(playlist_range) == 1:
            return SimpleNamespace(
                returncode=1,
                stderr="Request is blocked by server (412), please wait and try later.",
                stdout="",
            )
        start, end = (int(value) for value in playlist_range.split(":"))
        stdout = "\n".join(
            f'{{"id":"BV{index:03d}","ie_key":"BiliBili"}}'
            for index in range(start, end + 1)
        )
        return SimpleNamespace(returncode=0, stderr="", stdout=stdout)

    monkeypatch.setattr(ytdlp.subprocess, "run", fake_run)
    monkeypatch.setattr(ytdlp.time, "sleep", sleeps.append)

    result = ytdlp.expand_ytdlp_playlist(
        "https://space.bilibili.com/7612168/video",
        max_videos=50,
        order="latest",
    )

    assert attempts == ["1:25", "26:50", "26:50"]
    assert sleeps == [5]
    assert len(result.video_urls) == 50


def test_app_bilibili_short_playlist_result_is_filled_by_browser(monkeypatch):
    profile = ParsedInput(
        raw_input="https://space.bilibili.com/7612168/video",
        extracted_url="https://space.bilibili.com/7612168/video",
        canonical_url="https://space.bilibili.com/7612168/video",
        provider_key="ytdlp",
        is_profile=True,
    )
    monkeypatch.setattr(
        app,
        "expand_ytdlp_playlist",
        lambda **kwargs: ytdlp.YtdlpPlaylistResult(
            video_urls=[
                f"https://www.bilibili.com/video/BV{index:03d}"
                for index in range(1, 26)
            ],
            uploader="测试UP主",
        ),
    )
    monkeypatch.setattr(
        app,
        "expand_profile",
        lambda **kwargs: SimpleNamespace(
            video_urls=[
                f"https://www.bilibili.com/video/BV{index:03d}"
                for index in range(1, 41)
            ],
            pinned_urls=[],
            author="测试UP主",
        ),
    )

    class FakePage:
        def close(self):
            pass

    class FakeBrowser:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def new_page(self):
            return FakePage()

    monkeypatch.setattr(app, "open_download_browser_session", lambda config: FakeBrowser())

    result = app._expand_profile_inputs(
        [profile],
        browser_config=SimpleNamespace(),
        profile_videos_count=40,
        timeout_secs=30,
    )

    assert len(result) == 40
    assert result[25].canonical_url == "https://www.bilibili.com/video/BV026"
    assert result[-1].canonical_url == "https://www.bilibili.com/video/BV040"


def test_app_xiaohongshu_profile_videos_use_single_video_ytdlp_path(monkeypatch):
    profile = ParsedInput(
        raw_input="https://www.xiaohongshu.com/user/profile/demo",
        extracted_url="https://www.xiaohongshu.com/user/profile/demo",
        canonical_url="https://www.xiaohongshu.com/user/profile/demo",
        provider_key="xiaohongshu",
        is_profile=True,
    )
    note_url = (
        "https://www.xiaohongshu.com/explore/69be081c0000000021010b12"
        "?xsec_token=token-demo&xsec_source=pc_user"
    )
    monkeypatch.setattr(
        app,
        "expand_profile",
        lambda **kwargs: SimpleNamespace(
            video_urls=[note_url],
            pinned_urls=[],
            author="章鱼科普1号",
        ),
    )

    class FakePage:
        def close(self):
            pass

    class FakeBrowser:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def new_page(self):
            return FakePage()

    monkeypatch.setattr(app, "open_download_browser_session", lambda config: FakeBrowser())

    result = app._expand_profile_inputs(
        [profile],
        browser_config=SimpleNamespace(),
        profile_videos_count=30,
        timeout_secs=30,
    )

    assert result[0].provider_key == "ytdlp"
    assert result[0].fallback_provider_key == "xiaohongshu"
    assert result[0].canonical_url == note_url
    assert result[0].author_hint == "章鱼科普1号"
