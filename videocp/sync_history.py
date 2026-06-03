from __future__ import annotations

import json
import os
import fcntl
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SyncHistoryEntry:
    task_name: str
    content_id: str
    site: str
    author: str
    desc: str
    output_path: str
    feed_id: str = ""
    share_url: str = ""
    synced_at: str = ""
    status: str = "ok"
    error: str = ""


@dataclass(slots=True)
class SyncHistory:
    path: Path
    entries: list[SyncHistoryEntry] = field(default_factory=list)


def load_history(path: Path) -> SyncHistory:
    if not path.is_file():
        return SyncHistory(path=path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = [
            SyncHistoryEntry(**{k: v for k, v in raw.items() if k in SyncHistoryEntry.__slots__})
            for raw in data.get("entries", [])
        ]
        return SyncHistory(path=path, entries=entries)
    except (json.JSONDecodeError, KeyError, TypeError):
        return SyncHistory(path=path)


def is_synced(history: SyncHistory, task_name: str, content_id: str) -> bool:
    return any(
        e.task_name == task_name and e.content_id == content_id and e.status == "ok"
        for e in history.entries
    )


def find_processed_entry(history: SyncHistory, task_name: str, content_id: str) -> SyncHistoryEntry | None:
    final_statuses = {"ok", "skipped_unavailable", "skipped_random", "skipped_duration"}
    for entry in reversed(history.entries):
        if entry.task_name == task_name and entry.content_id == content_id and entry.status in final_statuses:
            return entry
    return None


def add_entry(history: SyncHistory, entry: SyncHistoryEntry) -> None:
    if not entry.synced_at:
        entry.synced_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
    history.path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = history.path.with_suffix(history.path.suffix + ".lock")
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        latest = load_history(history.path)
        if entry.status == "failed" or not any(
            existing.task_name == entry.task_name
            and existing.content_id == entry.content_id
            and existing.status == entry.status
            for existing in latest.entries
        ):
            latest.entries.append(entry)
            _save(latest)
        history.entries = latest.entries
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _save(history: SyncHistory) -> None:
    payload: dict[str, Any] = {
        "version": 1,
        "entries": [asdict(e) for e in history.entries],
    }
    history.path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = history.path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, history.path)
    history.path.chmod(0o600)
