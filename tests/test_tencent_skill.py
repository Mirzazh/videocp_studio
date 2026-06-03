from pathlib import Path

from videocp.tencent_skill import _find_cli
from videocp.youtube_po import _ensure_script_provider


def test_find_cli_prefers_bundled_runtime(tmp_path: Path, monkeypatch):
    bundled_bin = tmp_path / "bin"
    bundled_bin.mkdir()
    bundled_cli = bundled_bin / "tencent-channel-cli"
    bundled_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("VIDEOCP_BUNDLED_BIN", str(bundled_bin))

    assert _find_cli() == str(bundled_cli)


def test_youtube_helper_uses_bundled_runtime_without_install(tmp_path: Path, monkeypatch):
    bundled_server = tmp_path / "bgutil-server"
    bundled_server.joinpath("src").mkdir(parents=True)
    bundled_server.joinpath("src/generate_once.ts").write_text("", encoding="utf-8")
    bundled_server.joinpath("node_modules").mkdir()
    monkeypatch.setenv("VIDEOCP_BUNDLED_BGUTIL_SERVER", str(bundled_server))
    monkeypatch.setattr("videocp.youtube_po.shutil.which", lambda name: "/runtime/bin/deno" if name == "deno" else None)

    _ensure_script_provider(timeout_secs=1)
