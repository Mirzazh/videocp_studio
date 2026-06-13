from __future__ import annotations

import json
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from videocp.bbdown import download_bilibili_with_bbdown
from videocp.browser import BrowserConfig, open_download_browser_session
from videocp.config import WatermarkConfig
from videocp.doctor import run_doctor
from videocp.downloader import (
    allocate_output_path,
    build_output_subdir,
    build_output_stem,
    download_best_candidate,
    probe_video_dimensions,
    sanitize_filename,
)
from videocp.errors import DownloadError
from videocp.extractor import extract_video
from videocp.input_parser import parse_input
from videocp.models import (
    DoctorCheck,
    DownloadArtifact,
    ExtractionResult,
    MediaCandidate,
    MediaKind,
    ParsedInput,
    TrackType,
    VideoMetadata,
    WatermarkMode,
)
from videocp.profile import default_profile_dir, detect_system_browser_executable
from videocp.profile_expander import INSTAGRAM_PROFILE_RE, expand_profile
from videocp.runtime_log import full_url, log_info, log_warn
from videocp.ytdlp import download_with_ytdlp, expand_ytdlp_playlist, fetch_ytdlp_metadata

YOUTUBE_COOKIE_HELP = (
    "YouTube 需要 Cookie：请在 App 的下载页粘贴有效的 YouTube cookies.txt 内容。"
    "建议用隐身窗口登录 YouTube，打开 https://www.youtube.com/robots.txt 后导出 youtube.com Cookie。"
)
YTDLP_DOWNLOAD_TIMEOUT_SECS = 300
YOUTUBE_LOW_FORMAT_FALLBACK_ARGS = "youtube:player_client=web_safari"
YOUTUBE_DOWNLOAD_RETRY_ARGS = (
    "youtube:player_client=web_safari",
    "youtube:player_client=mweb;fetch_pot=always",
    "youtube:player_client=tv",
)


@dataclass(slots=True)
class DownloadOptions:
    raw_inputs: list[str]
    output_dir: Path
    profile_dir: Path
    browser_path: str
    headless: bool
    timeout_secs: int
    input_file: Path | None = None
    max_concurrent: int = 1
    max_concurrent_per_site: int = 1
    start_interval_secs: float = 0.0
    watermark: WatermarkConfig | None = None
    profile_videos_count: int = 3
    profile_order: str = "latest"
    bilibili_download_mode: str = "tv"
    quality: str = "best"
    ytdlp_extractor_args: str = ""
    ytdlp_cookies_file: Path | None = None
    ytdlp_remote_components: bool = False
    skip_content_ids: set[str] | None = None
    force_redownload: bool = False


@dataclass(slots=True)
class DownloadJobResult:
    raw_input: str
    parsed_input: ParsedInput | None
    extraction: ExtractionResult | None
    artifact: DownloadArtifact | None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.extraction is not None and self.artifact is not None and not self.error


@dataclass(slots=True)
class DoctorOptions:
    profile_dir: Path
    browser_path: str
    headless: bool
    keep_open: bool = False
    login_urls: list[str] | None = None


def _content_id_candidates(content_id: str) -> set[str]:
    candidates: set[str] = set()
    raw = str(content_id or "").strip()
    if not raw:
        return candidates
    cleaned = raw.split("?", 1)[0].rstrip("/")
    if cleaned:
        candidates.add(cleaned)
        name = Path(cleaned).name
        if name:
            candidates.add(name)
            stem = Path(name).stem
            if stem:
                candidates.add(stem)
    return candidates


def _extract_content_id_from_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    video_ids = parse_qs(parsed.query).get("v")
    if video_ids:
        return video_ids[0]
    for part in reversed(parsed.path.rstrip("/").split("/")):
        if part and len(part) > 2:
            return part
    return str(url or "")


def _exclude_processed_inputs(prepared_inputs: list[ParsedInput], content_ids: set[str] | None) -> list[ParsedInput]:
    if not content_ids:
        return prepared_inputs
    processed_candidates: set[str] = set()
    for content_id in content_ids:
        processed_candidates.update(_content_id_candidates(content_id))
    pending: list[ParsedInput] = []
    for item in prepared_inputs:
        content_id = _extract_content_id_from_url(item.canonical_url)
        if not _content_id_candidates(content_id).isdisjoint(processed_candidates):
            log_info("job.download.skip_history", content_id=content_id, url=full_url(item.canonical_url))
            continue
        pending.append(item)
    return pending


def _find_existing_download(output_dir: Path, content_id: str) -> dict | None:
    if not output_dir.exists():
        return None
    requested_ids = _content_id_candidates(content_id)
    if not requested_ids:
        return None
    for sidecar in output_dir.rglob("*.json"):
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        sidecar_ids = _content_id_candidates(sidecar.stem)
        sidecar_ids.update(_content_id_candidates(str(data.get("content_id", ""))))
        if requested_ids.isdisjoint(sidecar_ids):
            continue
        video_path_value = data.get("output_path", "")
        video = Path(video_path_value) if isinstance(video_path_value, str) and video_path_value else sidecar.with_suffix(".mp4")
        if not video.is_absolute():
            video = (sidecar.parent / video).resolve()
        if video.is_file():
            if video.stat().st_size < 1024:
                continue
            width, height = probe_video_dimensions(video)
            if width <= 0 or height <= 0:
                continue
            return {"output_path": video, "sidecar_path": sidecar, "data": data}
    return None


def _artifact_from_existing(existing: dict, candidate: MediaCandidate) -> DownloadArtifact:
    return DownloadArtifact(
        output_path=existing["output_path"],
        sidecar_path=existing["sidecar_path"],
        chosen_candidate=candidate,
        attempts=[{"url": str(existing["output_path"]), "mode": "reuse", "status": "ok"}],
    )


def _raise_if_duration_exceeds_limit(extraction: ExtractionResult, max_duration_secs: int) -> None:
    if max_duration_secs <= 0 or extraction.metadata.duration_ms <= 0:
        return
    duration_secs = extraction.metadata.duration_ms / 1000
    if duration_secs <= max_duration_secs:
        return
    log_info(
        "download.skip_duration",
        site=extraction.metadata.site,
        content_id=extraction.metadata.content_id or "unknown",
        duration_secs=f"{duration_secs:.1f}",
        max_video_duration_secs=max_duration_secs,
    )
    raise DownloadError(
        "video duration exceeds limit: "
        f"duration_secs={duration_secs:.1f} max_video_duration_secs={max_duration_secs}"
    )


def _is_ytdlp_setup_error(error: str) -> bool:
    normalized = str(error or "").lower()
    return (
        "youtube 已返回视频标题" in str(error or "")
        or "youtube 需要 cookie" in str(error or "").lower()
        or "sign in to confirm" in normalized
        or "requested format is not available" in normalized
        or "no video formats" in normalized
        or "only images are available" in normalized
    )


def _is_timeout_error(error: object) -> bool:
    normalized = str(error or "").lower()
    return "timed out" in normalized or "timeout" in normalized or "超时" in normalized


def _youtube_error_message(exc: object) -> str:
    normalized = str(exc or "").lower()
    if _is_timeout_error(exc):
        return (
            "YouTube 下载超时：网络较慢、视频较大或 YouTube 响应太慢。"
            "App 已把下载超时提升到 5 分钟；如果仍失败，请稍后重试、换网络，或确认 Cookie 没有过期。"
            f" 原始错误: {exc}"
        )
    if "http error 403" in normalized or "forbidden" in normalized:
        return (
            "YouTube 临时拒绝了视频流下载：这通常是并发下载过多、视频链接令牌过期或 Cookie/PO Token 短暂失效。"
            "App 已自动重试；如果仍失败，请减少同时重新下载数量，稍后重试，或重新粘贴 Cookie。"
            f" 原始错误: {exc}"
        )
    if "youtube 下载队列等待超时" in str(exc or ""):
        return str(exc)
    return f"{YOUTUBE_COOKIE_HELP} 原始错误: {exc}"


def _is_youtube_forbidden_error(error: object) -> bool:
    normalized = str(error or "").lower()
    return "http error 403" in normalized or "forbidden" in normalized


def _cleanup_ytdlp_partial_files(path: Path) -> None:
    parent = path.parent
    if not parent.exists():
        return
    stem = path.stem
    for candidate in parent.glob(f"{stem}*"):
        if candidate.suffix == ".json":
            continue
        try:
            if candidate.is_file():
                candidate.unlink()
        except OSError:
            pass


def _youtube_download_extractor_candidates(primary: str) -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []
    for value in [primary, *YOUTUBE_DOWNLOAD_RETRY_ARGS]:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            candidates.append(cleaned)
    return candidates


class StartIntervalGate:
    def __init__(self, interval_secs: float):
        self.interval_secs = max(0.0, interval_secs)
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0

    def wait(self) -> None:
        if self.interval_secs <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                if now >= self._next_allowed_at:
                    self._next_allowed_at = now + self.interval_secs
                    return
                sleep_for = self._next_allowed_at - now
            time.sleep(sleep_for)


def read_input_file(input_file: Path) -> list[str]:
    lines: list[str] = []
    for line in input_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    log_info("batch.input_file.loaded", input_file=input_file, count=len(lines))
    return lines


def collect_download_inputs(raw_inputs: list[str], input_file: Path | None) -> list[str]:
    combined = list(raw_inputs)
    if input_file is not None:
        combined.extend(read_input_file(input_file))
    if not combined:
        raise RuntimeError("No inputs were provided. Pass URLs directly or use --input-file.")
    return combined


def prepare_link_list(raw_inputs: list[str], input_file: Path | None, output_file: Path, timeout_secs: int) -> list[ParsedInput]:
    log_info("prepare_list.start", output_file=output_file, timeout_secs=timeout_secs)
    prepared = [parse_input(raw_input, timeout_secs=timeout_secs) for raw_input in collect_download_inputs(raw_inputs, input_file)]
    seen: set[str] = set()
    lines: list[str] = []
    for item in prepared:
        if item.canonical_url in seen:
            continue
        seen.add(item.canonical_url)
        lines.append(item.canonical_url)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    log_info("prepare_list.complete", output_file=output_file, count=len(lines))
    return prepared


def dedupe_prepared_inputs(prepared_inputs: list[ParsedInput]) -> list[ParsedInput]:
    seen: set[str] = set()
    unique: list[ParsedInput] = []
    for item in prepared_inputs:
        if item.canonical_url in seen:
            continue
        seen.add(item.canonical_url)
        unique.append(item)
    return unique


def _expand_profile_inputs(
    prepared_inputs: list[ParsedInput],
    browser_config: BrowserConfig,
    profile_videos_count: int,
    timeout_secs: int,
    profile_order: str = "latest",
    ytdlp_cookies_file: Path | None = None,
    ytdlp_extractor_args: str = "",
    ytdlp_remote_components: bool = False,
) -> list[ParsedInput]:
    """Separate profile inputs from video inputs, expand profiles to video URLs."""
    profile_inputs = [item for item in prepared_inputs if item.is_profile]
    video_inputs = [item for item in prepared_inputs if not item.is_profile]
    if not profile_inputs:
        return video_inputs

    native_profiles = [item for item in profile_inputs if item.provider_key != "ytdlp"]
    ytdlp_profiles = [item for item in profile_inputs if item.provider_key == "ytdlp"]

    log_info("profile.expand.batch_start", profiles=len(profile_inputs), max_per_profile=profile_videos_count)
    expanded: list[ParsedInput] = []

    # Native provider profiles: browser-based expansion
    if native_profiles:
        with open_download_browser_session(browser_config) as browser:
            for profile_input in native_profiles:
                page = browser.new_page()
                try:
                    result = expand_profile(
                        page=page,
                        profile_url=profile_input.canonical_url,
                        max_videos=profile_videos_count,
                        timeout_secs=timeout_secs,
                    )
                finally:
                    page.close()
                if profile_input.provider_key == "xiaohongshu" and not result.video_urls:
                    raise DownloadError(
                        "小红书主页没有解析到可下载的视频。请确认已经登录、主页中存在视频笔记，然后重试。"
                    )
                for url in result.pinned_urls:
                    expanded.append(ParsedInput(
                        raw_input=url,
                        extracted_url=url,
                        canonical_url=url,
                        provider_key=profile_input.provider_key,
                        is_pinned=True,
                        author_hint=result.author,
                    ))
                for url in result.video_urls:
                    provider_key = (
                        "ytdlp"
                        if profile_input.provider_key == "xiaohongshu"
                        else profile_input.provider_key
                    )
                    expanded.append(ParsedInput(
                        raw_input=url,
                        extracted_url=url,
                        canonical_url=url,
                        provider_key=provider_key,
                        author_hint=result.author,
                    ))

    # yt-dlp profiles: playlist expansion via yt-dlp (or browser for Instagram)
    if ytdlp_profiles:
        # Separate Instagram profiles (need browser expansion) from others (yt-dlp --flat-playlist)
        ig_profiles = [p for p in ytdlp_profiles if INSTAGRAM_PROFILE_RE.search(p.canonical_url)]
        other_ytdlp_profiles = [p for p in ytdlp_profiles if not INSTAGRAM_PROFILE_RE.search(p.canonical_url)]

        # Instagram: browser-based reel link extraction
        if ig_profiles:
            from videocp.profile_expander import _expand_instagram_reels
            with open_download_browser_session(browser_config) as browser:
                for profile_input in ig_profiles:
                    page = browser.new_page()
                    try:
                        result = _expand_instagram_reels(
                            page=page,
                            profile_url=profile_input.canonical_url,
                            max_videos=profile_videos_count,
                            timeout_secs=timeout_secs,
                        )
                    finally:
                        page.close()
                    for url in result.video_urls:
                        expanded.append(ParsedInput(
                            raw_input=url,
                            extracted_url=url,
                            canonical_url=url,
                            provider_key="ytdlp",
                            author_hint=result.author,
                        ))

        # Other yt-dlp profiles: playlist expansion via yt-dlp
        if other_ytdlp_profiles:
            for profile_input in other_ytdlp_profiles:
                try:
                    result = expand_ytdlp_playlist(
                        url=profile_input.canonical_url,
                        max_videos=profile_videos_count,
                        cookies_file=ytdlp_cookies_file,
                        order=profile_order,
                        extractor_args=ytdlp_extractor_args,
                        remote_components=ytdlp_remote_components,
                    )
                except DownloadError as exc:
                    if "youtube" in profile_input.canonical_url.lower():
                        raise DownloadError(f"{YOUTUBE_COOKIE_HELP} 原始错误: {exc}") from exc
                    if "space.bilibili.com" in profile_input.canonical_url.lower():
                        log_warn("profile.expand.ytdlp_fallback_browser", site="bilibili", error=str(exc))
                        if profile_order == "popular":
                            log_warn(
                                "profile.expand.bilibili_popular_fallback_latest",
                                message="B站热度排序依赖空间接口，接口不可用时浏览器回退只能按页面展示顺序下载",
                            )
                        with open_download_browser_session(browser_config) as browser:
                            page = browser.new_page()
                            try:
                                native_result = expand_profile(
                                    page=page,
                                    profile_url=profile_input.canonical_url,
                                    max_videos=profile_videos_count,
                                    timeout_secs=timeout_secs,
                                )
                            finally:
                                page.close()
                        for url in native_result.video_urls:
                            expanded.append(ParsedInput(
                                raw_input=url,
                                extracted_url=url,
                                canonical_url=url,
                                provider_key="bilibili",
                                author_hint=native_result.author,
                            ))
                        continue
                    raise
                result_urls = result.video_urls
                result_author = result.uploader
                if (
                    "space.bilibili.com" in profile_input.canonical_url.lower()
                    and len(result_urls) < profile_videos_count
                ):
                    log_warn(
                        "profile.expand.bilibili_short_result",
                        requested=profile_videos_count,
                        received=len(result_urls),
                        message="B站接口只返回了部分视频，继续使用浏览器分页补齐",
                    )
                    separator = "&" if "?" in profile_input.canonical_url else "?"
                    browser_profile_url = (
                        f"{profile_input.canonical_url}{separator}order="
                        f"{'click' if profile_order == 'popular' else 'pubdate'}"
                    )
                    with open_download_browser_session(browser_config) as browser:
                        page = browser.new_page()
                        try:
                            native_result = expand_profile(
                                page=page,
                                profile_url=browser_profile_url,
                                max_videos=profile_videos_count,
                                timeout_secs=timeout_secs,
                            )
                        finally:
                            page.close()
                    result_urls = list(dict.fromkeys([
                        *result_urls,
                        *native_result.video_urls,
                    ]))[:profile_videos_count]
                    result_author = result_author or native_result.author
                for url in result_urls:
                    provider_key = "bilibili" if "bilibili.com/video/" in url.lower() else "ytdlp"
                    expanded.append(ParsedInput(
                        raw_input=url,
                        extracted_url=url,
                        canonical_url=url,
                        provider_key=provider_key,
                        author_hint=result_author,
                    ))

    log_info("profile.expand.batch_complete", expanded=len(expanded))
    combined = video_inputs + expanded
    return dedupe_prepared_inputs(combined)


def _download_prepared_input(
    parsed: ParsedInput,
    browser_config: BrowserConfig,
    timeout_secs: int,
) -> ExtractionResult:
    with open_download_browser_session(browser_config) as browser:
        page = browser.new_page()
        try:
            extraction = extract_video(page, parsed.canonical_url, timeout_secs=timeout_secs)
        finally:
            page.close()
    return extraction


def _download_extraction_artifact(
    extraction: ExtractionResult,
    output_dir: Path,
    timeout_secs: int,
    watermark: WatermarkConfig | None = None,
    max_video_duration_secs: int = 0,
) -> DownloadArtifact:
    _raise_if_duration_exceeds_limit(extraction, max_video_duration_secs)
    return download_best_candidate(extraction, output_dir=output_dir, timeout_secs=timeout_secs, watermark=watermark)


def _download_bilibili_input(
    parsed: ParsedInput,
    browser_config: BrowserConfig,
    output_dir: Path,
    timeout_secs: int,
    watermark: WatermarkConfig | None = None,
    max_video_duration_secs: int = 0,
    bilibili_download_mode: str = "tv",
    quality: str = "best",
) -> tuple[ExtractionResult, DownloadArtifact]:
    kwargs = {
        "source_url": parsed.canonical_url,
        "browser_config": browser_config,
        "output_dir": output_dir,
        "timeout_secs": timeout_secs,
        "watermark": watermark,
        "author_hint": parsed.author_hint,
        "bilibili_download_mode": bilibili_download_mode,
        "quality": quality,
    }
    if max_video_duration_secs > 0:
        kwargs["max_video_duration_secs"] = max_video_duration_secs
    return download_bilibili_with_bbdown(**kwargs)


def _download_ytdlp_input(
    parsed: ParsedInput,
    browser_config: BrowserConfig,
    output_dir: Path,
    timeout_secs: int,
    max_video_duration_secs: int = 0,
    extractor_args: str = "",
    cookies_file: Path | None = None,
    remote_components: bool = False,
    force_redownload: bool = False,
    quality: str = "best",
) -> tuple[ExtractionResult, DownloadArtifact]:
    """Download a video via yt-dlp, optionally using a user-provided cookies.txt file."""
    del browser_config
    cookies: list[dict] = []

    is_youtube_url = "youtube.com" in parsed.canonical_url.lower() or "youtu.be" in parsed.canonical_url.lower()
    try:
        meta = fetch_ytdlp_metadata(
            parsed.canonical_url,
            cookies_file,
            extractor_args=extractor_args,
            remote_components=remote_components,
        )
    except DownloadError as exc:
        if is_youtube_url:
            raise DownloadError(_youtube_error_message(exc)) from exc
        raise
    effective_extractor_args = extractor_args
    if is_youtube_url and 0 < meta.max_resolution <= 360:
        log_warn(
            "ytdlp.metadata.low_quality_retry",
            formats=meta.formats_count,
            max_resolution=meta.max_resolution,
            fallback_client="web_safari",
        )
        try:
            fallback_meta = fetch_ytdlp_metadata(
                parsed.canonical_url,
                cookies_file,
                extractor_args=YOUTUBE_LOW_FORMAT_FALLBACK_ARGS,
                remote_components=remote_components,
            )
        except DownloadError as exc:
            log_warn("ytdlp.metadata.low_quality_retry_failed", error=str(exc))
        else:
            if fallback_meta.max_resolution > meta.max_resolution:
                meta = fallback_meta
                effective_extractor_args = YOUTUBE_LOW_FORMAT_FALLBACK_ARGS
                log_info(
                    "ytdlp.metadata.low_quality_recovered",
                    formats=meta.formats_count,
                    max_resolution=meta.max_resolution,
                    player_client="web_safari",
                )
    if meta.site == "youtube" and meta.formats_count == 0:
        raise DownloadError(
            f"{YOUTUBE_COOKIE_HELP} yt-dlp 已识别视频标题，但没有返回可下载的视频格式。"
        )

    # Build extraction result for consistent output
    site = meta.site or sanitize_filename(parsed.canonical_url.split("/")[2])
    metadata = VideoMetadata(
        source_url=parsed.canonical_url,
        site=site,
        canonical_url=parsed.canonical_url,
        page_url=parsed.canonical_url,
        aweme_id=meta.id,
        author=meta.uploader,
        desc=meta.title,
        title=meta.title,
        duration_ms=int(meta.duration_secs * 1000) if meta.duration_secs > 0 else 0,
    )
    candidate = MediaCandidate(
        url=parsed.canonical_url,
        kind=MediaKind.MP4,
        track_type=TrackType.MUXED,
        watermark_mode=WatermarkMode.NO_WATERMARK,
        source="ytdlp",
        observed_via="ytdlp",
        note=f"yt-dlp: {meta.title}",
    )
    extraction = ExtractionResult(
        metadata=metadata,
        candidates=[candidate],
        cookies=cookies,
        user_agent="",
        diagnostics={"downloader": "ytdlp", "ytdlp_id": meta.id, "ytdlp_site": meta.site},
    )

    existing = None if force_redownload else _find_existing_download(output_dir, metadata.content_id)
    if existing:
        log_info(
            "job.download.reuse",
            site=metadata.site,
            content_id=metadata.content_id or "unknown",
            output=existing["output_path"],
        )
        return extraction, _artifact_from_existing(existing, candidate)

    # Allocate output path
    _raise_if_duration_exceeds_limit(extraction, max_video_duration_secs)
    subdir = build_output_subdir(extraction)
    stem = build_output_stem(extraction)
    if force_redownload:
        target_dir = output_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{stem}.mp4"
        download_path = target_dir / f"{stem}.redownload.mp4"
    else:
        output_path = allocate_output_path(output_dir, subdir, stem)
        download_path = output_path
    sidecar_path = output_path.with_suffix(".json")

    # Download
    download_attempt_errors: list[str] = []
    extractor_candidates = (
        _youtube_download_extractor_candidates(effective_extractor_args)
        if is_youtube_url else [effective_extractor_args]
    )
    for attempt_index, attempt_extractor_args in enumerate(extractor_candidates, start=1):
        try:
            download_with_ytdlp(
                url=parsed.canonical_url,
                output_path=download_path,
                cookies_file=cookies_file,
                timeout_secs=max(timeout_secs, YTDLP_DOWNLOAD_TIMEOUT_SECS),
                extractor_args=attempt_extractor_args,
                remote_components=remote_components,
                quality=quality,
            )
            effective_extractor_args = attempt_extractor_args
            break
        except DownloadError as exc:
            download_attempt_errors.append(str(exc))
            if not is_youtube_url or not _is_youtube_forbidden_error(exc) or attempt_index == len(extractor_candidates):
                if is_youtube_url:
                    raise DownloadError(_youtube_error_message(exc)) from exc
                raise
            _cleanup_ytdlp_partial_files(download_path)
            log_warn(
                "ytdlp.download.forbidden_retry",
                attempt=attempt_index,
                next_extractor_args=extractor_candidates[attempt_index],
                error=str(exc),
            )
    if download_path != output_path:
        download_path.replace(output_path)

    width, height = probe_video_dimensions(output_path)
    log_info(
        "ytdlp.download.quality",
        content_id=metadata.content_id or "unknown",
        width=width,
        height=height,
        quality=quality,
    )

    # Write sidecar
    sidecar_payload = {
        "site": metadata.site,
        "content_id": metadata.content_id,
        "author": metadata.author,
        "desc": metadata.desc,
        "title": metadata.title,
        "source_url": metadata.source_url,
        "canonical_url": metadata.canonical_url,
        "page_url": metadata.page_url,
        "output_path": str(output_path),
        "chosen_candidate": candidate.to_dict(),
        "watermark_mode": candidate.watermark_mode.value,
        "candidates": [candidate.to_dict()],
        "diagnostics": {
            **extraction.diagnostics,
            "download_quality": quality,
            "video_width": width,
            "video_height": height,
            "ytdlp_extractor_args": effective_extractor_args,
            "download_attempt_errors": download_attempt_errors,
        },
        "attempts": [{"url": parsed.canonical_url, "mode": "ytdlp", "status": "ok"}],
    }
    sidecar_path.write_text(
        json.dumps(sidecar_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    artifact = DownloadArtifact(
        output_path=output_path,
        sidecar_path=sidecar_path,
        chosen_candidate=candidate,
        attempts=[{"url": parsed.canonical_url, "mode": "ytdlp", "status": "ok"}],
    )
    return extraction, artifact


def _run_download_jobs(
    prepared_inputs: list[ParsedInput],
    browser_config: BrowserConfig,
    output_dir: Path,
    timeout_secs: int,
    max_concurrent: int,
    max_concurrent_per_site: int,
    start_interval_secs: float,
    watermark: WatermarkConfig | None = None,
    max_video_duration_secs: int = 0,
    ytdlp_extractor_args: str = "",
    ytdlp_cookies_file: Path | None = None,
    ytdlp_remote_components: bool = False,
    force_redownload: bool = False,
    bilibili_download_mode: str = "tv",
    quality: str = "best",
) -> list[DownloadJobResult]:
    results: list[DownloadJobResult | None] = [None] * len(prepared_inputs)
    total_limit = max(1, max_concurrent)
    per_site_limit = max(1, max_concurrent_per_site)
    gate = StartIntervalGate(start_interval_secs)
    site_semaphores: dict[str, threading.Semaphore] = {}
    site_lock = threading.Lock()
    ytdlp_setup_failed = threading.Event()

    def site_semaphore(provider_key: str) -> threading.Semaphore:
        with site_lock:
            semaphore = site_semaphores.get(provider_key)
            if semaphore is None:
                semaphore = threading.Semaphore(per_site_limit)
                site_semaphores[provider_key] = semaphore
            return semaphore

    total_slots = threading.Semaphore(total_limit)
    log_info(
        "batch.download.start",
        jobs=len(prepared_inputs),
        output_dir=output_dir,
        max_concurrent=total_limit,
        max_concurrent_per_site=per_site_limit,
        start_interval_secs=start_interval_secs,
    )

    def wait_for_slot_release(active_futures: list) -> list:
        if not active_futures:
            return active_futures
        done, pending = wait(active_futures, return_when=FIRST_COMPLETED)
        for future in done:
            future.result()
        return list(pending)

    def worker(index: int, parsed: ParsedInput, semaphore: threading.Semaphore) -> None:
        extraction: ExtractionResult | None = None
        try:
            if parsed.provider_key == "ytdlp" and ytdlp_setup_failed.is_set():
                results[index] = DownloadJobResult(
                    raw_input=parsed.raw_input,
                    parsed_input=parsed,
                    extraction=None,
                    artifact=None,
                    error="已跳过：前面的 YouTube 下载验证或格式检查失败，请先粘贴有效 Cookie 后重试。",
                )
                return
            gate.wait()
            log_info(
                "job.extract.start",
                job=index + 1,
                site=parsed.provider_key or "unknown",
                url=full_url(parsed.canonical_url),
            )
            if parsed.provider_key == "ytdlp":
                kwargs = {
                    "parsed": parsed,
                    "browser_config": browser_config,
                    "output_dir": output_dir,
                    "timeout_secs": timeout_secs,
                    "extractor_args": ytdlp_extractor_args,
                    "cookies_file": ytdlp_cookies_file,
                    "remote_components": ytdlp_remote_components,
                    "force_redownload": force_redownload,
                    "quality": quality,
                }
                if max_video_duration_secs > 0:
                    kwargs["max_video_duration_secs"] = max_video_duration_secs
                extraction, artifact = _download_ytdlp_input(**kwargs)
                results[index] = DownloadJobResult(
                    raw_input=parsed.raw_input,
                    parsed_input=parsed,
                    extraction=extraction,
                    artifact=artifact,
                )
                log_info(
                    "job.download.complete",
                    job=index + 1,
                    site=extraction.metadata.site,
                    content_id=extraction.metadata.content_id or "unknown",
                    output=artifact.output_path,
                )
            elif parsed.provider_key == "bilibili":
                if bilibili_download_mode == "ytdlp":
                    kwargs = {
                        "parsed": parsed,
                        "browser_config": browser_config,
                        "output_dir": output_dir,
                        "timeout_secs": timeout_secs,
                        "extractor_args": ytdlp_extractor_args,
                        "cookies_file": ytdlp_cookies_file,
                        "remote_components": ytdlp_remote_components,
                        "force_redownload": force_redownload,
                        "quality": quality,
                    }
                    if max_video_duration_secs > 0:
                        kwargs["max_video_duration_secs"] = max_video_duration_secs
                    extraction, artifact = _download_ytdlp_input(**kwargs)
                else:
                    kwargs = {
                        "parsed": parsed,
                        "browser_config": browser_config,
                        "output_dir": output_dir,
                        "timeout_secs": timeout_secs,
                        "watermark": watermark,
                        "bilibili_download_mode": bilibili_download_mode,
                        "quality": quality,
                    }
                    if max_video_duration_secs > 0:
                        kwargs["max_video_duration_secs"] = max_video_duration_secs
                    extraction, artifact = _download_bilibili_input(**kwargs)
                results[index] = DownloadJobResult(
                    raw_input=parsed.raw_input,
                    parsed_input=parsed,
                    extraction=extraction,
                    artifact=artifact,
                )
                log_info(
                    "job.download.complete",
                    job=index + 1,
                    site=extraction.metadata.site,
                    content_id=extraction.metadata.content_id or "unknown",
                    output=artifact.output_path,
                )
            else:
                extraction = _download_prepared_input(
                    parsed=parsed,
                    browser_config=browser_config,
                    timeout_secs=timeout_secs,
                )
                if parsed.author_hint:
                    extraction.metadata.author = parsed.author_hint
                log_info(
                    "job.extract.complete",
                    job=index + 1,
                    site=parsed.provider_key or extraction.metadata.site,
                    content_id=extraction.metadata.content_id or "unknown",
                    candidates=len(extraction.candidates),
                )
                existing = None if force_redownload else _find_existing_download(output_dir, extraction.metadata.content_id)
                if existing:
                    candidate = extraction.candidates[0] if extraction.candidates else MediaCandidate(
                        url=parsed.canonical_url,
                        kind=MediaKind.MP4,
                        track_type=TrackType.UNKNOWN,
                        watermark_mode=WatermarkMode.UNKNOWN,
                        source="reuse",
                        observed_via="sidecar",
                    )
                    artifact = _artifact_from_existing(existing, candidate)
                    results[index] = DownloadJobResult(
                        raw_input=parsed.raw_input,
                        parsed_input=parsed,
                        extraction=extraction,
                        artifact=artifact,
                    )
                    log_info(
                        "job.download.reuse",
                        job=index + 1,
                        site=parsed.provider_key or extraction.metadata.site,
                        content_id=extraction.metadata.content_id or "unknown",
                        output=artifact.output_path,
                    )
                    return
                kwargs = {
                    "extraction": extraction,
                    "output_dir": output_dir,
                    "timeout_secs": timeout_secs,
                    "watermark": watermark,
                }
                if max_video_duration_secs > 0:
                    kwargs["max_video_duration_secs"] = max_video_duration_secs
                try:
                    artifact = _download_extraction_artifact(**kwargs)
                except DownloadError as exc:
                    if parsed.provider_key == "youtube":
                        raise DownloadError(
                            "YouTube 返回了受保护的视频流，当前未配置可用 Cookie/PO Token，已跳过下载；"
                            "请在 App 的下载页粘贴 YouTube cookies.txt 内容后重试。"
                        ) from exc
                    raise
                results[index] = DownloadJobResult(
                    raw_input=parsed.raw_input,
                    parsed_input=parsed,
                    extraction=extraction,
                    artifact=artifact,
                )
                log_info(
                    "job.download.complete",
                    job=index + 1,
                    site=parsed.provider_key or extraction.metadata.site,
                    content_id=extraction.metadata.content_id or "unknown",
                    output=artifact.output_path,
                )
        except Exception as exc:
            if parsed.provider_key == "ytdlp" and _is_ytdlp_setup_error(str(exc)):
                ytdlp_setup_failed.set()
            results[index] = DownloadJobResult(
                raw_input=parsed.raw_input,
                parsed_input=parsed,
                extraction=None,
                artifact=None,
                error=str(exc),
            )
            if extraction is None:
                log_warn(
                    "job.extract.failed",
                    job=index + 1,
                    site=parsed.provider_key or "unknown",
                    url=full_url(parsed.canonical_url),
                    error=str(exc),
                )
            else:
                log_warn(
                    "job.download.failed",
                    job=index + 1,
                    site=parsed.provider_key or extraction.metadata.site,
                    error=str(exc),
                )
        finally:
            semaphore.release()
            total_slots.release()

    pending_inputs = list(enumerate(prepared_inputs))
    active_futures: list = []
    with ThreadPoolExecutor(max_workers=total_limit) as executor:
        while pending_inputs or active_futures:
            started_any = False
            index = 0
            while index < len(pending_inputs):
                if not total_slots.acquire(blocking=False):
                    break
                item_index, parsed = pending_inputs[index]
                semaphore = site_semaphore(parsed.provider_key or "unknown")
                if not semaphore.acquire(blocking=False):
                    total_slots.release()
                    index += 1
                    continue
                pending_inputs.pop(index)
                started_any = True
                active_futures.append(executor.submit(worker, item_index, parsed, semaphore))
            if pending_inputs and not started_any:
                active_futures = wait_for_slot_release(active_futures)
                continue
            if active_futures:
                active_futures = wait_for_slot_release(active_futures)
    return [item for item in results if item is not None]


def download_videos(options: DownloadOptions) -> list[tuple[ExtractionResult, DownloadArtifact]]:
    browser_path = options.browser_path or detect_system_browser_executable()
    if not browser_path:
        raise RuntimeError("No Chrome-family browser found. Use --browser-path.")
    log_info(
        "download.session.start",
        output_dir=options.output_dir,
        profile_dir=options.profile_dir or default_profile_dir(),
        headless=options.headless,
    )
    browser_config = BrowserConfig(
        profile_dir=options.profile_dir or default_profile_dir(),
        browser_path=browser_path,
        headless=options.headless,
    )
    prepared_inputs = [
        parse_input(raw_input, timeout_secs=options.timeout_secs)
        for raw_input in collect_download_inputs(options.raw_inputs, options.input_file)
    ]
    prepared_inputs = dedupe_prepared_inputs(prepared_inputs)
    prepared_inputs = _expand_profile_inputs(
        prepared_inputs,
        browser_config,
        options.profile_videos_count,
        options.timeout_secs,
        options.profile_order,
        options.ytdlp_cookies_file,
        options.ytdlp_extractor_args,
        options.ytdlp_remote_components,
    )
    prepared_inputs = _exclude_processed_inputs(prepared_inputs, options.skip_content_ids)
    job_results = _run_download_jobs(
        prepared_inputs=prepared_inputs,
        browser_config=browser_config,
        output_dir=options.output_dir,
        timeout_secs=options.timeout_secs,
        max_concurrent=options.max_concurrent,
        max_concurrent_per_site=options.max_concurrent_per_site,
        start_interval_secs=options.start_interval_secs,
        watermark=options.watermark,
        ytdlp_extractor_args=options.ytdlp_extractor_args,
        ytdlp_cookies_file=options.ytdlp_cookies_file,
        ytdlp_remote_components=options.ytdlp_remote_components,
        force_redownload=options.force_redownload,
        bilibili_download_mode=options.bilibili_download_mode,
        quality=options.quality,
    )
    failures = [item for item in job_results if not item.ok]
    if failures:
        failed = failures[0]
        raise RuntimeError(f"Download failed for {failed.raw_input}: {failed.error}")
    return [(item.extraction, item.artifact) for item in job_results if item.ok]


def download_jobs(options: DownloadOptions) -> list[DownloadJobResult]:
    browser_path = options.browser_path or detect_system_browser_executable()
    if not browser_path:
        raise RuntimeError("No Chrome-family browser found. Use --browser-path.")
    log_info(
        "download.jobs.start",
        output_dir=options.output_dir,
        profile_dir=options.profile_dir or default_profile_dir(),
        headless=options.headless,
        timeout_secs=options.timeout_secs,
    )
    browser_config = BrowserConfig(
        profile_dir=options.profile_dir or default_profile_dir(),
        browser_path=browser_path,
        headless=options.headless,
    )
    prepared_inputs = [
        parse_input(raw_input, timeout_secs=options.timeout_secs)
        for raw_input in collect_download_inputs(options.raw_inputs, options.input_file)
    ]
    prepared_inputs = dedupe_prepared_inputs(prepared_inputs)
    prepared_inputs = _expand_profile_inputs(
        prepared_inputs,
        browser_config,
        options.profile_videos_count,
        options.timeout_secs,
        options.profile_order,
        options.ytdlp_cookies_file,
        options.ytdlp_extractor_args,
        options.ytdlp_remote_components,
    )
    prepared_inputs = _exclude_processed_inputs(prepared_inputs, options.skip_content_ids)
    return _run_download_jobs(
        prepared_inputs=prepared_inputs,
        browser_config=browser_config,
        output_dir=options.output_dir,
        timeout_secs=options.timeout_secs,
        max_concurrent=options.max_concurrent,
        max_concurrent_per_site=options.max_concurrent_per_site,
        start_interval_secs=options.start_interval_secs,
        watermark=options.watermark,
        ytdlp_extractor_args=options.ytdlp_extractor_args,
        ytdlp_cookies_file=options.ytdlp_cookies_file,
        ytdlp_remote_components=options.ytdlp_remote_components,
        force_redownload=options.force_redownload,
        bilibili_download_mode=options.bilibili_download_mode,
        quality=options.quality,
    )


def download_video(options: DownloadOptions) -> tuple[ExtractionResult, DownloadArtifact]:
    result = download_videos(options)
    if not result:
        raise RuntimeError("No inputs were provided.")
    return result[0]


def doctor(options: DoctorOptions) -> list[DoctorCheck]:
    return run_doctor(
        profile_dir=options.profile_dir or default_profile_dir(),
        browser_path=options.browser_path,
        headless=options.headless,
        keep_open=options.keep_open,
        login_urls=options.login_urls,
    )


def series_command(
    raw_input: str,
    season_id: int | None = None,
    download: bool = False,
    json_output: bool = False,
    config=None,
    output_dir_override: Path | None = None,
    timeout_secs_override: int | None = None,
    headless_override: bool | None = None,
    profile_dir_override: Path | None = None,
    browser_path_override: str | None = None,
    bb_mode_override: str | None = None,
) -> int:
    from videocp.bilibili_series import extract_mid_from_url, fetch_all_archives, fetch_seasons_series_list

    raw = str(raw_input or "").strip()
    mid = int(raw) if raw.isdigit() else extract_mid_from_url(raw)
    if not mid:
        print("error: 请传入 B站空间链接或数字 mid")
        return 1

    profile_dir = profile_dir_override or (config.profile_dir if config else default_profile_dir())
    browser_path = browser_path_override or (config.browser_path if config else detect_system_browser_executable())
    headless = headless_override if headless_override is not None else (config.headless if config else True)
    timeout_secs = timeout_secs_override or (config.timeout_secs if config else 30)
    output_dir = output_dir_override or (config.output_dir if config else Path("./downloads").resolve())
    bb_mode = bb_mode_override or (config.bilibili_download_mode if config else "tv")
    browser_config = BrowserConfig(profile_dir=profile_dir, browser_path=browser_path, headless=headless)

    if not browser_path:
        print("error: No Chrome-family browser found. Use --browser-path.")
        return 1

    with open_download_browser_session(browser_config) as browser:
        page = browser.new_page()
        try:
            series_list = fetch_seasons_series_list(page, mid=mid, timeout_secs=timeout_secs)
            if season_id is not None:
                series_list = [item for item in series_list if item.season_id == season_id]
            payload = []
            for item in series_list:
                videos = fetch_all_archives(page, mid=mid, season_id=item.season_id, timeout_secs=timeout_secs)
                payload.append({"series": item, "videos": videos})
        finally:
            page.close()

    if not download:
        if json_output:
            print(json.dumps([
                {
                    "season_id": item["series"].season_id,
                    "name": item["series"].meta_name,
                    "total": item["series"].total,
                    "videos": [
                        {
                            "bvid": video.bvid,
                            "title": video.title,
                            "url": video.video_url,
                            "duration_secs": video.duration_secs,
                        }
                        for video in item["videos"]
                    ],
                }
                for item in payload
            ], ensure_ascii=False, indent=2))
        else:
            for item in payload:
                info = item["series"]
                print(f"[{info.season_id}] {info.meta_name} ({len(item['videos'])}/{info.total})")
                for video in item["videos"]:
                    print(f"  - {video.bvid} {video.title}")
        return 0

    prepared_inputs: list[ParsedInput] = []
    for item in payload:
        author_hint = item["series"].meta_name
        for video in item["videos"]:
            prepared_inputs.append(ParsedInput(
                raw_input=video.video_url,
                extracted_url=video.video_url,
                canonical_url=video.video_url,
                provider_key="bilibili",
                author_hint=author_hint,
            ))
    results = _run_download_jobs(
        prepared_inputs=dedupe_prepared_inputs(prepared_inputs),
        browser_config=browser_config,
        output_dir=output_dir,
        timeout_secs=timeout_secs,
        max_concurrent=(config.max_concurrent if config else 1),
        max_concurrent_per_site=(config.max_concurrent_per_site if config else 1),
        start_interval_secs=(config.start_interval_secs if config else 0.0),
        watermark=(config.watermark if config else None),
        bilibili_download_mode=bb_mode,
    )
    if json_output:
        print(json.dumps([
            {
                "ok": item.ok,
                "url": item.raw_input,
                "path": str(item.artifact.output_path) if item.artifact else "",
                "content_id": item.extraction.metadata.content_id if item.extraction else "",
                "error": item.error,
            }
            for item in results
        ], ensure_ascii=False, indent=2))
    else:
        for item in results:
            if item.ok:
                print(f"Downloaded {item.extraction.metadata.content_id}: {item.artifact.output_path}")
            else:
                print(f"Failed {item.raw_input}: {item.error}")
    return 0 if all(item.ok for item in results) else 1
