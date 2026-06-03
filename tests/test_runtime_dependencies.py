from pathlib import Path

from videocp.downloader import find_ffmpeg, find_ffprobe


def test_downloader_prefers_bundled_ffmpeg_and_ffprobe(tmp_path: Path, monkeypatch):
    bundled_bin = tmp_path / "bin"
    bundled_bin.mkdir()
    bundled_bin.joinpath("ffmpeg").write_text("", encoding="utf-8")
    bundled_bin.joinpath("ffprobe").write_text("", encoding="utf-8")
    monkeypatch.setenv("VIDEOCP_BUNDLED_BIN", str(bundled_bin))

    assert find_ffmpeg() == str(bundled_bin / "ffmpeg")
    assert find_ffprobe() == str(bundled_bin / "ffprobe")
