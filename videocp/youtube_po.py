from __future__ import annotations

import importlib.metadata
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


PROVIDER_PACKAGE = "bgutil-ytdlp-pot-provider"
PROVIDER_REPO = "https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git"
PROVIDER_BRANCH = "1.3.1"
PROVIDER_HOME = Path.home() / "bgutil-ytdlp-pot-provider"
DEFAULT_EXTRACTOR_ARGS = "youtube:player_client=mweb;fetch_pot=always"


@dataclass(slots=True)
class YoutubePoSetupResult:
    ok: bool
    action: str
    package: str = PROVIDER_PACKAGE
    version: str = ""
    extractor_args: str = DEFAULT_EXTRACTOR_ARGS
    error: str = ""

    def to_dict(self) -> dict[str, str | bool]:
        return asdict(self)


def provider_version() -> str:
    try:
        return importlib.metadata.version(PROVIDER_PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return ""


def merge_extractor_args(current: str) -> str:
    current = str(current or "").strip()
    return current or DEFAULT_EXTRACTOR_ARGS


def _run(cmd: list[str], timeout_secs: int, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_secs, cwd=cwd)


def _find_executable(name: str) -> str:
    bundled_bin = os.environ.get("VIDEOCP_BUNDLED_BIN", "")
    bundled_path = Path(bundled_bin) / name if bundled_bin else None
    if bundled_path is not None and bundled_path.is_file():
        return str(bundled_path)
    return shutil.which(name) or ""


def _ensure_python_plugin(timeout_secs: int) -> str:
    existing = provider_version()
    if existing:
        return existing
    result = _run([sys.executable, "-m", "pip", "install", "-U", PROVIDER_PACKAGE], timeout_secs)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "安装 Python provider 失败").strip())
    installed = provider_version()
    if not installed:
        raise RuntimeError("Python provider 安装完成，但 yt-dlp 未检测到插件")
    return installed


def _ensure_script_provider(timeout_secs: int) -> None:
    deno = _find_executable("deno")
    if not deno:
        raise RuntimeError("缺少 deno。请先安装 Homebrew deno，或运行: brew install deno")
    bundled_server = Path(os.environ.get("VIDEOCP_BUNDLED_BGUTIL_SERVER", "")).expanduser()
    if bundled_server.joinpath("src/generate_once.ts").is_file() and bundled_server.joinpath("node_modules").is_dir():
        return
    server_dir = PROVIDER_HOME / "server"
    script = server_dir / "src" / "generate_once.ts"
    if not script.exists():
        git = _find_executable("git")
        if not git:
            raise RuntimeError("缺少 git，无法下载 bgutil provider 脚本")
        PROVIDER_HOME.parent.mkdir(parents=True, exist_ok=True)
        result = _run(
            [git, "clone", "--single-branch", "--branch", PROVIDER_BRANCH, PROVIDER_REPO, str(PROVIDER_HOME)],
            timeout_secs,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "下载 bgutil provider 脚本失败").strip())
    if not (server_dir / "deno.lock").exists() or not (server_dir / "node_modules").exists():
        result = _run([deno, "install"], timeout_secs, cwd=server_dir)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "初始化 bgutil provider 依赖失败").strip())


def ensure_provider_installed(*, install: bool = True, timeout_secs: int = 240) -> YoutubePoSetupResult:
    try:
        version = provider_version()
        if install:
            version = _ensure_python_plugin(timeout_secs)
            _ensure_script_provider(timeout_secs)
            return YoutubePoSetupResult(ok=True, action="ready", version=version)
        if not version:
            return YoutubePoSetupResult(ok=False, action="missing", error=f"{PROVIDER_PACKAGE} 未安装")
        _ensure_script_provider(timeout_secs)
        return YoutubePoSetupResult(ok=True, action="ready", version=version)
    except Exception as exc:
        return YoutubePoSetupResult(ok=False, action="failed", version=provider_version(), error=str(exc))
