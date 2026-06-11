from pathlib import Path

from videocp.sync_history import SyncHistoryEntry, add_entry, find_processed_entry, load_history, replace_entry


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


def test_find_processed_entry_is_scoped_to_publish_account(tmp_path: Path):
    history_path = tmp_path / "history.json"
    history = load_history(history_path)
    account_a = _entry("video-1")
    account_a.task_name = "directory_publish"
    account_a.account_id = "account-a"
    add_entry(history, account_a)

    assert find_processed_entry(history, "directory_publish", "video-1", "account-a") is not None
    assert find_processed_entry(history, "directory_publish", "video-1", "account-b") is None


def test_add_entry_keeps_publish_records_for_different_accounts(tmp_path: Path):
    history = load_history(tmp_path / "history.json")
    for account_id in ("account-a", "account-b"):
        entry = _entry("video-1")
        entry.task_name = "directory_publish"
        entry.account_id = account_id
        add_entry(history, entry)

    assert [entry.account_id for entry in load_history(history.path).entries] == [
        "account-a",
        "account-b",
    ]


def test_legacy_publish_record_without_account_still_prevents_duplicate(tmp_path: Path):
    history = load_history(tmp_path / "history.json")
    legacy = _entry("video-1")
    legacy.task_name = "directory_publish"
    add_entry(history, legacy)

    assert find_processed_entry(history, "directory_publish", "video-1", "account-b") is not None
