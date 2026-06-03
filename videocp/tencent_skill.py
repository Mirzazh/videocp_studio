from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path


SKILL_URL = "https://connect.qq.com/skills/tencent-channel-community.zip"
SKILL_DIR = Path.home() / ".openclaw/workspace/skills/tencent-channel-community"
ENV_FILE = Path.home() / ".qqcli/.env"


@dataclass(slots=True)
class TencentSkillStatus:
    ok: bool
    skill_dir: str
    cli: str = ""
    logged_in: bool = False
    token_source: str = ""
    nickname: str = ""
    global_nickname: str = ""
    is_guild_author: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _find_cli() -> str:
    bundled_bin = os.environ.get("VIDEOCP_BUNDLED_BIN", "")
    for candidate in (
        str(Path(bundled_bin) / "tencent-channel-cli") if bundled_bin else "",
        shutil.which("tencent-channel-cli"),
        str(Path.home() / ".local/bin/tencent-channel-cli"),
        "/opt/homebrew/bin/tencent-channel-cli",
        "/usr/local/bin/tencent-channel-cli",
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def _download_and_install_skill() -> None:
    SKILL_DIR.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tencent-channel-skill-") as temp_raw:
        archive = Path(temp_raw) / "tencent-channel-community.zip"
        urllib.request.urlretrieve(SKILL_URL, archive)
        extract_root = Path(temp_raw) / "extract"
        extract_root.mkdir()
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extract_root)
        found = next((path for path in extract_root.rglob("SKILL.md") if path.parent.name == "tencent-channel-community"), None)
        source_dir = found.parent if found else extract_root
        if SKILL_DIR.exists():
            shutil.rmtree(SKILL_DIR)
        shutil.copytree(source_dir, SKILL_DIR)


def _write_token(token: str) -> None:
    cleaned = token.strip()
    if not cleaned:
        return
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if ENV_FILE.is_file():
        existing = ENV_FILE.read_text(encoding="utf-8").splitlines()
    lines = [line for line in existing if not line.startswith("QQ_AI_CONNECT_TOKEN=")]
    lines.append(f"QQ_AI_CONNECT_TOKEN={cleaned}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)


def setup_tencent_channel_skill(*, token: str = "", install: bool = True) -> TencentSkillStatus:
    try:
        if install and not SKILL_DIR.joinpath("SKILL.md").is_file():
            _download_and_install_skill()
        if token.strip():
            _write_token(token)
        return check_tencent_channel_skill()
    except Exception as exc:
        return TencentSkillStatus(ok=False, skill_dir=str(SKILL_DIR), cli=_find_cli(), error=str(exc))


def check_tencent_channel_skill() -> TencentSkillStatus:
    cli = _find_cli()
    if not SKILL_DIR.joinpath("SKILL.md").is_file():
        return TencentSkillStatus(ok=False, skill_dir=str(SKILL_DIR), cli=cli, error="腾讯频道 Skill 未安装")
    if not cli:
        return TencentSkillStatus(ok=False, skill_dir=str(SKILL_DIR), error="tencent-channel-cli 未安装")

    bundled_bin = os.environ.get("VIDEOCP_BUNDLED_BIN", "")
    env = {**os.environ, "PATH": f"{bundled_bin}:/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")}
    proc = subprocess.run([cli, "login", "status", "--json"], capture_output=True, text=True, timeout=30, env=env)
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    logged_in = bool(payload.get("success") and (data.get("isLoggedIn") or data.get("valid")))
    token_source = str(data.get("tokenSource") or "")
    nickname = ""
    global_nickname = ""
    is_guild_author = False
    if logged_in:
        user_proc = subprocess.run([cli, "manage", "get-user-info", "--json"], capture_output=True, text=True, timeout=30, env=env)
        try:
            user_payload = json.loads(user_proc.stdout or "{}")
        except json.JSONDecodeError:
            user_payload = {}
        user_data = user_payload.get("data", {}) if isinstance(user_payload, dict) else {}
        if isinstance(user_data, dict) and user_payload.get("success"):
            nickname = str(user_data.get("nickname") or "")
            global_nickname = str(user_data.get("global_nickname") or "")
            is_guild_author = bool(user_data.get("is_guild_author"))
    return TencentSkillStatus(
        ok=logged_in,
        skill_dir=str(SKILL_DIR),
        cli=cli,
        logged_in=logged_in,
        token_source=token_source,
        nickname=nickname,
        global_nickname=global_nickname,
        is_guild_author=is_guild_author,
        error="" if logged_in else "腾讯频道 Token 未配置或未通过登录检查",
    )
