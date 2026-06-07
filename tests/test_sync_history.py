from pathlib import Path

from videocp.sync_history import SyncHistoryEntry, add_entry, load_history, replace_entry


def _entry(content_id: str) -> SyncHistoryEntry:
    return SyncHistoryEntry(
        task_name="directory_download",
        content_id=content_id,
        site="youtube",
        author="author",
        desc="title",
        output_path=f"/downloads/{content_id}.mp4",
    )


def test_add_entry_merges_stale_history_instances(tmp_path: Path):
    history_path = tmp_path / "download-history.json"
    first_process_view = load_history(history_path)
    second_process_view = load_history(history_path)

    add_entry(first_process_view, _entry("video-1"))
    add_entry(second_process_view, _entry("video-2"))

    history = load_history(history_path)
    assert [entry.content_id for entry in history.entries] == ["video-1", "video-2"]


def test_add_entry_does_not_duplicate_same_completed_item(tmp_path: Path):
    history_path = tmp_path / "download-history.json"
    history = load_history(history_path)

    add_entry(history, _entry("video-1"))
    add_entry(history, _entry("video-1"))

    assert [entry.content_id for entry in load_history(history_path).entries] == ["video-1"]


def test_replace_entry_updates_redownload_path_without_duplicate(tmp_path: Path):
    history_path = tmp_path / "history.json"
    history = load_history(history_path)
    original = _entry("video-1")
    original.output_path = "/old/video.mp4"
    add_entry(history, original)

    replacement = _entry("video-1")
    replacement.output_path = "/new/video.mp4"
    replace_entry(history, replacement)

    entries = load_history(history_path).entries
    assert len(entries) == 1
    assert entries[0].output_path == "/new/video.mp4"
