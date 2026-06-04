import json
from pathlib import Path
from types import SimpleNamespace

from videocp.mac_workflow import _clean_title, parse_profile_from_app_config, run_download_from_app_config, run_publish_from_app_config
from videocp.publisher import PublishResult
from videocp.ytdlp import YtdlpPlaylistResult


def test_clean_title_strips_tags_and_mentions():
    assert _clean_title("原始标题 #热点 @某人  结尾", True) == "原始标题 结尾"
    assert _clean_title("原始标题#热点 @某人", True) == "原始标题"
    assert _clean_title("原始标题 #热点", False) == "原始标题 #热点"


def test_download_from_app_config_writes_cookie_text_and_uses_youtube_defaults(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(
        json.dumps(
            {
                "download": {
                    "inputs_text": "https://www.youtube.com/shorts/demo",
                    "output_dir": str(tmp_path / "downloads"),
                    "youtube_cookies_text": ".youtube.com\tTRUE\t/\tTRUE\t0\tYSC\tdemo",
                }
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_download_jobs(options):
        captured["options"] = options
        return []

    monkeypatch.setattr("videocp.mac_workflow.download_jobs", fake_download_jobs)

    assert run_download_from_app_config(config_path) == []
    options = captured["options"]
    assert options.ytdlp_extractor_args == "youtube:player_client=mweb;fetch_pot=always"
    assert options.ytdlp_remote_components is True
    assert options.ytdlp_cookies_file is not None
    cookie_text = options.ytdlp_cookies_file.read_text(encoding="utf-8")
    assert "# Netscape HTTP Cookie File" in cookie_text
    assert "YSC\tdemo" in cookie_text


def test_download_requires_explicit_output_dir(tmp_path: Path):
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(
        json.dumps({"download": {"inputs_text": "https://www.youtube.com/shorts/demo", "output_dir": ""}}),
        encoding="utf-8",
    )

    result = run_download_from_app_config(config_path)

    assert result == [
        {
            "ok": False,
            "action": "failed",
            "path": "",
            "content_id": "",
            "title": "",
            "feed_id": "",
            "share_url": "",
            "error": "请先选择视频保存位置",
        }
    ]
    assert not (tmp_path / "downloads").exists()


def test_download_from_app_config_records_history_and_reuses_it_after_file_removal(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    history_path = tmp_path / "download-history.json"
    config_path.write_text(
        json.dumps(
            {
                "download": {
                    "inputs_text": "https://www.youtube.com/shorts/cid-1",
                    "output_dir": str(tmp_path / "downloads"),
                    "history_file": str(history_path),
                }
            }
        ),
        encoding="utf-8",
    )
    video_path = tmp_path / "downloads" / "cid-1.mp4"
    captured = []

    def fake_download_jobs(options):
        captured.append(options.skip_content_ids)
        if options.skip_content_ids:
            return []
        return [
            SimpleNamespace(
                ok=True,
                extraction=SimpleNamespace(
                    metadata=SimpleNamespace(
                        content_id="cid-1",
                        title="title",
                        desc="desc",
                        site="youtube",
                        author="author",
                    )
                ),
                artifact=SimpleNamespace(output_path=video_path, attempts=[{"mode": "ytdlp"}]),
                error="",
            )
        ]

    monkeypatch.setattr("videocp.mac_workflow.download_jobs", fake_download_jobs)

    first = run_download_from_app_config(config_path)
    second = run_download_from_app_config(config_path)

    assert first[0]["action"] == "downloaded"
    assert second == []
    assert captured == [set(), {"cid-1"}]
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert history["entries"][0]["content_id"] == "cid-1"
    assert history["entries"][0]["task_name"] == "directory_download"


def test_download_from_app_config_force_redownload_bypasses_history(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    history_path = tmp_path / "download-history.json"
    history_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "task_name": "directory_download",
                        "content_id": "cid-1",
                        "site": "youtube",
                        "author": "",
                        "desc": "",
                        "output_path": "",
                        "status": "ok",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text(
        json.dumps(
            {
                "download": {
                    "inputs_text": "https://www.youtube.com/shorts/cid-1",
                    "output_dir": str(tmp_path / "downloads"),
                    "history_file": str(history_path),
                }
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_download_jobs(options):
        captured["skip_content_ids"] = options.skip_content_ids
        captured["force_redownload"] = options.force_redownload
        return []

    monkeypatch.setattr("videocp.mac_workflow.download_jobs", fake_download_jobs)

    assert run_download_from_app_config(config_path, force_redownload=True) == []
    assert captured == {"skip_content_ids": set(), "force_redownload": True}


def test_download_from_app_config_skips_items_in_publish_history(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    publish_history_path = tmp_path / "publish-history.json"
    publish_history_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "task_name": "directory_publish",
                        "content_id": "published-id",
                        "site": "youtube",
                        "author": "",
                        "desc": "",
                        "output_path": "",
                        "status": "ok",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text(
        json.dumps(
            {
                "download": {
                    "inputs_text": "https://www.youtube.com/shorts/published-id",
                    "output_dir": str(tmp_path / "downloads"),
                },
                "publish": {"history_file": str(publish_history_path)},
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_download_jobs(options):
        captured["skip_content_ids"] = options.skip_content_ids
        return []

    monkeypatch.setattr("videocp.mac_workflow.download_jobs", fake_download_jobs)

    assert run_download_from_app_config(config_path) == []
    assert captured["skip_content_ids"] == {"published-id"}


def test_parse_profile_uses_ytdlp_playlist_expansion(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(json.dumps({"download": {}}), encoding="utf-8")
    captured = {}

    def fake_expand(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return YtdlpPlaylistResult(
            video_urls=["https://www.youtube.com/shorts/demo"],
            uploader="Demo Channel",
        )

    monkeypatch.setattr("videocp.mac_workflow.expand_ytdlp_playlist", fake_expand)

    result = parse_profile_from_app_config(config_path, "https://www.youtube.com/@demo/shorts")

    assert result["ok"] is True
    assert result["name"] == "Demo Channel"
    assert result["first_video_url"] == "https://www.youtube.com/shorts/demo"
    assert captured["max_videos"] == 1
    assert captured["order"] == "latest"
    assert captured["remote_components"] is True


def test_parse_profile_uses_handle_instead_of_shorts_as_fallback_name(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(json.dumps({"download": {}}), encoding="utf-8")
    monkeypatch.setattr(
        "videocp.mac_workflow.expand_ytdlp_playlist",
        lambda *args, **kwargs: YtdlpPlaylistResult(video_urls=[], uploader=""),
    )

    result = parse_profile_from_app_config(config_path, "https://www.youtube.com/@%E5%B0%8F%E6%98%8E/shorts")

    assert result["name"] == "@小明"


def test_parse_bilibili_profile_uses_uid_as_fallback_name(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "videocp.mac_workflow.expand_ytdlp_playlist",
        lambda *args, **kwargs: YtdlpPlaylistResult(
            video_urls=["https://www.bilibili.com/video/BV1demo"],
            uploader="",
        ),
    )

    result = parse_profile_from_app_config(config_path, "https://space.bilibili.com/7612168/video")

    assert result["ok"] is True
    assert result["name"] == "B站 UP主 7612168"
    assert result["first_video_url"] == "https://www.bilibili.com/video/BV1demo"


def test_parse_bilibili_profile_falls_back_to_browser_expansion(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    config_path.write_text("{}", encoding="utf-8")

    class FakeBrowser:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def new_page(self):
            return SimpleNamespace(close=lambda: None)

    monkeypatch.setattr("videocp.mac_workflow.expand_ytdlp_playlist", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("412")))
    monkeypatch.setattr("videocp.mac_workflow.detect_system_browser_executable", lambda: "/Applications/Google Chrome.app")
    monkeypatch.setattr("videocp.mac_workflow.open_download_browser_session", lambda *_: FakeBrowser())
    monkeypatch.setattr(
        "videocp.mac_workflow.expand_profile",
        lambda **kwargs: SimpleNamespace(video_urls=["https://www.bilibili.com/video/BV1fallback"], author="回退UP主"),
    )

    result = parse_profile_from_app_config(config_path, "https://space.bilibili.com/7612168/video")

    assert result["ok"] is True
    assert result["name"] == "回退UP主"
    assert result["first_video_url"] == "https://www.bilibili.com/video/BV1fallback"


def test_parse_douyin_profile_falls_back_to_browser_expansion(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    config_path.write_text("{}", encoding="utf-8")

    class FakeBrowser:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def new_page(self):
            return SimpleNamespace(close=lambda: None)

    monkeypatch.setattr("videocp.mac_workflow.expand_ytdlp_playlist", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("unsupported")))
    monkeypatch.setattr("videocp.mac_workflow.detect_system_browser_executable", lambda: "/Applications/Google Chrome.app")
    monkeypatch.setattr("videocp.mac_workflow.open_download_browser_session", lambda *_: FakeBrowser())
    monkeypatch.setattr(
        "videocp.mac_workflow.expand_profile",
        lambda **kwargs: SimpleNamespace(video_urls=["https://www.douyin.com/video/123456"], author="抖音作者"),
    )

    result = parse_profile_from_app_config(config_path, "https://www.douyin.com/user/MS4wLjABAAAA-demo")

    assert result["ok"] is True
    assert result["name"] == "抖音作者"
    assert result["first_video_url"] == "https://www.douyin.com/video/123456"


def test_publish_from_directory_uses_sidecar_title_records_and_deletes(tmp_path: Path, monkeypatch):
    video = tmp_path / "downloads" / "demo.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(
        json.dumps(
            {
                "content_id": "cid-1",
                "title": "我的视频 #话题 @用户",
                "desc": "desc",
                "site": "youtube",
                "author": "author",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config = {
        "publish": {
            "input_dir": str(video.parent),
            "history_file": str(tmp_path / "history.json"),
            "skill_dir": str(tmp_path / "skill"),
            "scope": "channel",
            "guild_id": "123",
            "channel_id": "456",
            "feed_type": 2,
            "limit": 1,
            "title_template": "{title}",
            "content_template": "正文 {title}",
            "strip_tags_mentions": True,
            "delete_after_publish": True,
        }
    }
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    captured = {}

    def fake_publish_to_channel(**kwargs):
        captured.update(kwargs)
        return PublishResult(success=True, feed_id="feed-1", share_url="https://pd.qq.com/test")

    monkeypatch.setattr("videocp.mac_workflow.publish_to_channel", fake_publish_to_channel)

    result = run_publish_from_app_config(config_path)

    assert result[0]["action"] == "published"
    assert captured["guild_id"] == "123"
    assert captured["channel_id"] == "456"
    assert captured["title"] == "我的视频"
    assert captured["content"] == "正文 我的视频"
    assert not video.exists()
    assert not video.with_suffix(".json").exists()
    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert history["entries"][0]["content_id"] == "cid-1"


def test_publish_channel_scope_requires_channel_ids(tmp_path: Path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(
        json.dumps(
            {
                "publish": {
                    "input_dir": str(downloads),
                    "scope": "channel",
                    "guild_id": "",
                    "channel_id": "",
                }
            }
        ),
        encoding="utf-8",
    )

    result = run_publish_from_app_config(config_path)

    assert result[0]["ok"] is False
    assert "频道内发帖需要填写" in result[0]["error"]


def test_publish_removes_already_sent_video_when_delete_enabled(tmp_path: Path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    video = downloads / "demo.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(json.dumps({"content_id": "cid-1"}), encoding="utf-8")
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "task_name": "directory_publish",
                        "content_id": "cid-1",
                        "site": "",
                        "author": "",
                        "desc": "",
                        "output_path": str(video),
                        "status": "ok",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(
        json.dumps(
            {
                "publish": {
                    "input_dir": str(downloads),
                    "history_file": str(history_path),
                    "delete_after_publish": True,
                }
            }
        ),
        encoding="utf-8",
    )

    result = run_publish_from_app_config(config_path)

    assert result[0]["action"] == "skipped_deleted"
    assert not video.exists()
    assert not video.with_suffix(".json").exists()


def test_publish_retries_then_records_success(tmp_path: Path, monkeypatch):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    video = downloads / "demo.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(json.dumps({"content_id": "cid-retry"}), encoding="utf-8")
    history_path = tmp_path / "history.json"
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(
        json.dumps({"publish": {"input_dir": str(downloads), "history_file": str(history_path), "retry_count": 2}}),
        encoding="utf-8",
    )
    attempts = []

    def fake_publish_to_channel(**kwargs):
        attempts.append(kwargs)
        if len(attempts) < 3:
            return PublishResult(success=False, error="temporary failure")
        return PublishResult(success=True, feed_id="feed-ok", share_url="https://pd.qq.com/ok")

    monkeypatch.setattr("videocp.mac_workflow.publish_to_channel", fake_publish_to_channel)
    monkeypatch.setattr("videocp.mac_workflow.time.sleep", lambda *_: None)

    result = run_publish_from_app_config(config_path)

    assert len(attempts) == 3
    assert result[0]["action"] == "published"
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert [entry["status"] for entry in history["entries"]] == ["ok"]


def test_publish_login_error_checks_status_before_retry(tmp_path: Path, monkeypatch):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    video = downloads / "demo.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(json.dumps({"content_id": "cid-login"}), encoding="utf-8")
    history_path = tmp_path / "history.json"
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(
        json.dumps({"publish": {"input_dir": str(downloads), "history_file": str(history_path), "retry_count": 1}}),
        encoding="utf-8",
    )
    checks = []
    attempts = []

    def fake_publish_to_channel(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            return PublishResult(success=False, error="发帖失败（错误码 151）：[oidb]登录态验证失败")
        return PublishResult(success=True, feed_id="feed-ok", share_url="https://pd.qq.com/ok")

    def fake_check_tencent_login_status():
        checks.append(True)
        return PublishResult(success=True)

    monkeypatch.setattr("videocp.mac_workflow.publish_to_channel", fake_publish_to_channel)
    monkeypatch.setattr("videocp.mac_workflow.check_tencent_login_status", fake_check_tencent_login_status)
    monkeypatch.setattr("videocp.mac_workflow.time.sleep", lambda *_: None)

    result = run_publish_from_app_config(config_path)

    assert len(attempts) == 2
    assert checks == [True]
    assert result[0]["action"] == "published"


def test_publish_success_without_share_url_is_failed_and_keeps_video(tmp_path: Path, monkeypatch):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    video = downloads / "demo.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(json.dumps({"content_id": "cid-no-link"}), encoding="utf-8")
    history_path = tmp_path / "history.json"
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(
        json.dumps(
            {
                "publish": {
                    "input_dir": str(downloads),
                    "history_file": str(history_path),
                    "delete_after_publish": True,
                    "retry_count": 0,
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "videocp.mac_workflow.publish_to_channel",
        lambda **kwargs: PublishResult(success=True, feed_id="feed-no-link", share_url=""),
    )

    result = run_publish_from_app_config(config_path)

    assert result[0]["action"] == "failed"
    assert "未返回分享链接" in result[0]["error"]
    assert video.exists()
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert history["entries"][0]["status"] == "failed"
    assert history["entries"][0]["feed_id"] == ""
    assert history["entries"][0]["share_url"] == ""


def test_publish_retry_video_path_publishes_only_selected_failed_video(tmp_path: Path, monkeypatch):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    other = downloads / "other.mp4"
    other.write_bytes(b"video")
    other.with_suffix(".json").write_text(json.dumps({"content_id": "cid-other"}), encoding="utf-8")
    video = downloads / "demo.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(json.dumps({"content_id": "cid-retry-one"}), encoding="utf-8")
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "task_name": "directory_publish",
                        "content_id": "cid-other",
                        "site": "",
                        "author": "",
                        "desc": "old",
                        "output_path": str(other),
                        "status": "ok",
                        "synced_at": "2026-01-01T00:00:00+08:00",
                    },
                    {
                        "task_name": "directory_publish",
                        "content_id": "cid-retry-one",
                        "site": "",
                        "author": "",
                        "desc": "failed",
                        "output_path": str(video),
                        "status": "failed",
                        "error": "old failure",
                        "synced_at": "2026-01-02T00:00:00+08:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(
        json.dumps(
            {
                "publish": {
                    "input_dir": str(downloads),
                    "history_file": str(history_path),
                    "retry_video_path": str(video),
                    "delete_after_publish": False,
                }
            }
        ),
        encoding="utf-8",
    )
    attempts = []

    def fake_publish_to_channel(**kwargs):
        attempts.append(kwargs)
        return PublishResult(success=True, feed_id="feed-new", share_url="https://pd.qq.com/new")

    monkeypatch.setattr("videocp.mac_workflow.publish_to_channel", fake_publish_to_channel)

    result = run_publish_from_app_config(config_path)

    assert len(attempts) == 1
    assert attempts[0]["video_path"] == video
    assert result[0]["action"] == "published"
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert [entry["status"] for entry in history["entries"]] == ["ok", "failed", "ok"]


def test_publish_final_failure_is_recorded_but_not_deduped_or_deleted(tmp_path: Path, monkeypatch):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    video = downloads / "demo.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(json.dumps({"content_id": "cid-failed"}), encoding="utf-8")
    history_path = tmp_path / "history.json"
    config_path = tmp_path / "mac-app.json"
    config_path.write_text(
        json.dumps(
            {
                "publish": {
                    "input_dir": str(downloads),
                    "history_file": str(history_path),
                    "retry_count": 1,
                    "delete_after_publish": True,
                }
            }
        ),
        encoding="utf-8",
    )
    attempts = []

    def fake_publish_to_channel(**kwargs):
        attempts.append(kwargs)
        return PublishResult(success=False, error="still failed")

    monkeypatch.setattr("videocp.mac_workflow.publish_to_channel", fake_publish_to_channel)
    monkeypatch.setattr("videocp.mac_workflow.time.sleep", lambda *_: None)

    first = run_publish_from_app_config(config_path)
    second = run_publish_from_app_config(config_path)

    assert len(attempts) == 4
    assert first[0]["action"] == "failed"
    assert second[0]["action"] == "failed"
    assert video.exists()
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert [entry["status"] for entry in history["entries"]] == ["failed", "failed"]
