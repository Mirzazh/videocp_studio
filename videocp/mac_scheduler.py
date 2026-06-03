from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, time as wall_time
from pathlib import Path
from typing import Any

import yaml

from videocp.config import load_app_config, load_sync_config
from videocp.sync import SyncOptions, run_sync

APP_CONFIG_FILENAME = "mac-app.json"
DEFAULT_APP_CONFIG = {
    "tasks_file": "mac-tasks.yaml",
    "run_interval_minutes": 60,
    "active_start": "09:00",
    "active_end": "23:00",
    "sync": {
        "history_file": "./sync_history_mac.json",
        "skill_dir": "~/.openclaw/workspace/skills/tencent-channel-community",
        "videos_per_task": 1,
        "publish_method": "skill",
        "skip_rate": 0,
        "max_video_duration_secs": 0,
    },
    "cleanup": {
        "enabled": False,
        "max_age_days": 7,
        "max_total_gb": 20,
    },
    "download": {
        "inputs_text": "",
        "output_dir": "./downloads",
        "history_file": "./download_history_mac.json",
        "order": "latest",
        "count": 3,
        "youtube_auto_token": False,
        "ytdlp_extractor_args": "",
    },
    "publish": {
        "input_dir": "./downloads",
        "history_file": "./publish_history_mac.json",
        "skill_dir": "~/.openclaw/workspace/skills/tencent-channel-community",
        "scope": "author_global",
        "guild_id": "",
        "channel_id": "",
        "feed_type": 1,
        "limit": 1,
        "title_template": "{title}",
        "content_template": "{title}",
        "strip_tags_mentions": True,
        "delete_after_publish": True,
        "retry_count": 2,
    },
    "sources": [],
}


@dataclass(slots=True)
class CleanupResult:
    deleted_files: int = 0
    deleted_bytes: int = 0
    errors: list[str] = field(default_factory=list)


def default_app_config_path(start_dir: Path | None = None) -> Path:
    return (start_dir or Path.cwd()) / APP_CONFIG_FILENAME


def ensure_app_config(path: Path) -> dict[str, Any]:
    if path.is_file():
        return load_app_config_file(path)
    path.write_text(json.dumps(DEFAULT_APP_CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return load_app_config_file(path)


def load_app_config_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    merged = json.loads(json.dumps(DEFAULT_APP_CONFIG))
    _deep_update(merged, data)
    return merged


def save_app_config_file(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def parse_wall_time(value: str) -> wall_time:
    hour, minute = value.strip().split(":", 1)
    return wall_time(hour=int(hour), minute=int(minute))


def is_within_window(now: datetime, start: str, end: str) -> bool:
    start_time = parse_wall_time(start)
    end_time = parse_wall_time(end)
    current = now.time().replace(second=0, microsecond=0)
    if start_time <= end_time:
        return start_time <= current <= end_time
    return current >= start_time or current <= end_time


def resolve_config_path(value: str | Path, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def write_tasks_file(app_config: dict[str, Any], app_config_path: Path) -> Path:
    base_dir = app_config_path.parent
    tasks_path = resolve_config_path(app_config.get("tasks_file", "mac-tasks.yaml"), base_dir)
    sync_raw = dict(app_config.get("sync") or {})
    tasks: list[dict[str, Any]] = []
    for index, source in enumerate(app_config.get("sources") or [], start=1):
        if not source.get("enabled", True):
            continue
        source_url = str(source.get("source_url", "")).strip()
        if not source_url:
            continue
        scope = str(source.get("publish_scope", "author_global"))
        task: dict[str, Any] = {
            "name": str(source.get("name") or f"source-{index}"),
            "source_url": source_url,
            "title_template": str(source.get("title_template") or "{title}"),
            "content_template": str(source.get("content_template") or "{title}"),
            "feed_type": int(source.get("feed_type") or 1),
            "publish_method": "skill",
        }
        count = int(source.get("count") or 0)
        if count > 0:
            task["count"] = count
        if scope == "channel":
            task["guild_id"] = str(source.get("guild_id", "")).strip()
            task["channel_id"] = str(source.get("channel_id", "")).strip()
        tasks.append(task)

    payload = {"sync": sync_raw, "tasks": tasks}
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return tasks_path


def run_once(app_config_path: Path, *, dry_run: bool = False, task_name_filter: str | None = None) -> list[dict[str, Any]]:
    app_config = ensure_app_config(app_config_path)
    tasks_path = write_tasks_file(app_config, app_config_path)
    app_cfg = load_app_config(None, start_dir=app_config_path.parent)
    sync_cfg = load_sync_config(tasks_path=tasks_path, start_dir=app_config_path.parent)
    results = []
    if sync_cfg.tasks:
        results = run_sync(SyncOptions(
            app_config=app_cfg,
            sync_config=sync_cfg,
            dry_run=dry_run,
            task_name_filter=task_name_filter,
        ))
    cleanup_result = cleanup_downloads(app_cfg.output_dir, app_config.get("cleanup") or {})
    return [
        {
            "task_name": item.task_name,
            "ok": item.ok,
            "action": item.action,
            "content_id": item.content_id,
            "share_url": item.share_url,
            "output_path": item.output_path,
            "error": item.error,
        }
        for item in results
    ] + [{
        "task_name": "__cleanup__",
        "ok": not cleanup_result.errors,
        "action": "cleanup",
        "content_id": "",
        "share_url": "",
        "output_path": "",
        "error": "; ".join(cleanup_result.errors),
        "deleted_files": cleanup_result.deleted_files,
        "deleted_bytes": cleanup_result.deleted_bytes,
    }]


def cleanup_downloads(output_dir: Path, cleanup_config: dict[str, Any]) -> CleanupResult:
    if not cleanup_config.get("enabled", True):
        return CleanupResult()
    if not output_dir.exists():
        return CleanupResult()
    max_age_days = int(cleanup_config.get("max_age_days") or 0)
    max_total_gb = float(cleanup_config.get("max_total_gb") or 0)
    max_total_bytes = int(max_total_gb * 1024 * 1024 * 1024) if max_total_gb > 0 else 0
    now = time.time()
    result = CleanupResult()

    media_files = sorted(
        [path for path in output_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".mp4", ".m4v", ".mov", ".webm", ".mkv"}],
        key=lambda path: path.stat().st_mtime,
    )

    def delete_media(path: Path) -> None:
        try:
            size = path.stat().st_size
            sidecar = path.with_suffix(".json")
            path.unlink(missing_ok=True)
            if sidecar.exists():
                sidecar.unlink(missing_ok=True)
            result.deleted_files += 1
            result.deleted_bytes += size
        except OSError as exc:
            result.errors.append(f"{path}: {exc}")

    if max_age_days > 0:
        cutoff = now - max_age_days * 86400
        for media in list(media_files):
            if media.exists() and media.stat().st_mtime < cutoff:
                delete_media(media)

    if max_total_bytes > 0:
        remaining = [path for path in media_files if path.exists()]
        total = sum(path.stat().st_size for path in remaining)
        for media in remaining:
            if total <= max_total_bytes:
                break
            size = media.stat().st_size
            delete_media(media)
            total -= size
    return result


def run_scheduler(app_config_path: Path, *, dry_run: bool = False) -> None:
    last_run_at = 0.0
    while True:
        app_config = ensure_app_config(app_config_path)
        interval = max(1, int(app_config.get("run_interval_minutes") or 60)) * 60
        now = datetime.now()
        in_window = is_within_window(now, app_config.get("active_start", "09:00"), app_config.get("active_end", "23:00"))
        if in_window and time.monotonic() - last_run_at >= interval:
            run_once(app_config_path, dry_run=dry_run)
            last_run_at = time.monotonic()
        time.sleep(30)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videocp-scheduler")
    parser.add_argument("--app-config", default=str(default_app_config_path()), help="Path to mac-app.json.")
    parser.add_argument("--once", action="store_true", help="Run one sync cycle and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Plan without downloading or publishing.")
    parser.add_argument("--task-name", default=None, help="Run only the named source task.")
    args = parser.parse_args(argv)
    path = Path(args.app_config).expanduser().resolve()
    if args.once:
        print(json.dumps(run_once(path, dry_run=args.dry_run, task_name_filter=args.task_name), ensure_ascii=False, indent=2))
        return 0
    run_scheduler(path, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
