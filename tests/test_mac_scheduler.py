import json
from pathlib import Path

from videocp.config import AppConfig, WatermarkConfig
from videocp.mac_scheduler import cleanup_downloads, is_within_window, run_once, write_tasks_file


def test_write_tasks_file_maps_global_and_channel_sources(tmp_path: Path):
    config_path = tmp_path / "mac-app.json"
    config = {
        "tasks_file": "generated.yaml",
        "sync": {
            "history_file": "./history.json",
            "skill_dir": "~/.openclaw/workspace/skills/tencent-channel-community",
            "videos_per_task": 1,
            "publish_method": "skill",
            "skip_rate": 0,
        },
        "sources": [
            {
                "name": "global",
                "source_url": "https://www.youtube.com/@a/videos",
                "publish_scope": "author_global",
                "count": 2,
            },
            {
                "name": "channel",
                "source_url": "https://www.youtube.com/@b/shorts",
                "publish_scope": "channel",
                "guild_id": "123",
                "channel_id": "456",
            },
        ],
    }

    tasks_path = write_tasks_file(config, config_path)
    text = tasks_path.read_text(encoding="utf-8")

    assert "name: global" in text
    assert "name: channel" in text
    assert "guild_id: '123'" in text or 'guild_id: "123"' in text
    assert "channel_id: '456'" in text or 'channel_id: "456"' in text


def test_is_within_window_handles_overnight():
    from datetime import datetime

    assert is_within_window(datetime(2026, 1, 1, 23, 0), "22:00", "02:00") is True
    assert is_within_window(datetime(2026, 1, 1, 1, 0), "22:00", "02:00") is True
    assert is_within_window(datetime(2026, 1, 1, 12, 0), "22:00", "02:00") is False


def test_cleanup_downloads_deletes_old_media_and_sidecar(tmp_path: Path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    video = downloads / "old.mp4"
    sidecar = downloads / "old.json"
    video.write_bytes(b"video")
    sidecar.write_text(json.dumps({"ok": True}), encoding="utf-8")
    old_time = 1_600_000_000
    video.touch()
    sidecar.touch()
    import os

    os.utime(video, (old_time, old_time))
    os.utime(sidecar, (old_time, old_time))

    result = cleanup_downloads(downloads, {"enabled": True, "max_age_days": 1, "max_total_gb": 0})

    assert result.deleted_files == 1
    assert not video.exists()
    assert not sidecar.exists()


def test_run_once_passes_task_name_filter(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "mac-app.json"
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "tasks_file": "generated.yaml",
                "cleanup": {"enabled": False},
                "sources": [
                    {"name": "first", "source_url": "https://example.com/a"},
                    {"name": "second", "source_url": "https://example.com/b"},
                ],
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "videocp.mac_scheduler.load_app_config",
        lambda *a, **k: AppConfig(
            output_dir=downloads,
            profile_dir=tmp_path / "profile",
            browser_path="/usr/bin/chrome",
            headless=False,
            timeout_secs=30,
            max_concurrent=1,
            max_concurrent_per_site=1,
            start_interval_secs=0,
            watermark=WatermarkConfig(),
        ),
    )

    def fake_run_sync(options):
        captured["task_name_filter"] = options.task_name_filter
        captured["task_names"] = [task.name for task in options.sync_config.tasks]
        return []

    monkeypatch.setattr("videocp.mac_scheduler.run_sync", fake_run_sync)

    run_once(config_path, task_name_filter="second")

    assert captured["task_name_filter"] == "second"
    assert captured["task_names"] == ["first", "second"]
