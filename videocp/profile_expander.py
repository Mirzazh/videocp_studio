from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from playwright.sync_api import Page, Response

from videocp.errors import DownloadError
from videocp.providers import DOUYIN_USER_PROFILE_RE, SiteProvider, resolve_provider
from videocp.runtime_log import full_url, log_info, log_warn

INSTAGRAM_REEL_URL_TEMPLATE = "https://www.instagram.com/reel/{shortcode}/"
INSTAGRAM_REEL_LINK_RE = re.compile(r'/reel/([A-Za-z0-9_-]+)')
INSTAGRAM_PROFILE_RE = re.compile(
    r"instagram\.com/(?!p/|reel/|stories/|explore/|accounts/|direct/)[^/?#]+(/reels)?/?$",
    re.IGNORECASE,
)
DOUYIN_VIDEO_URL_TEMPLATE = "https://www.douyin.com/video/{aweme_id}"
DOUYIN_VIDEO_LINK_RE = re.compile(r'/video/(\d+)')
BILIBILI_VIDEO_URL_TEMPLATE = "https://www.bilibili.com/video/{bvid}"
BILIBILI_BVID_RE = re.compile(r'/(BV[A-Za-z0-9]+)')
BILIBILI_SPACE_VIDEO_SUFFIX = "/video"
XHS_EXPLORE_URL_TEMPLATE = "https://www.xiaohongshu.com/explore/{note_id}"
XHS_NOTE_LINK_RE = re.compile(r'/(?:explore|discovery/item)/([A-Za-z0-9]+)')


def _bilibili_video_page_url(profile_url: str, page_number: int) -> str:
    parsed = urlparse(profile_url)
    path = parsed.path.rstrip("/")
    if not path.endswith(BILIBILI_SPACE_VIDEO_SUFFIX):
        path += BILIBILI_SPACE_VIDEO_SUFFIX
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["pn"] = str(max(1, page_number))
    query.setdefault("order", "pubdate")
    return urlunparse(parsed._replace(path=path, query=urlencode(query)))


def _extract_author_from_dom(page: Page, selectors: list[str]) -> str:
    """Try multiple CSS selectors to extract the profile author name from the page."""
    for selector in selectors:
        try:
            el = page.query_selector(selector)
            if el:
                text = (el.text_content() or "").strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


@dataclass(slots=True)
class ProfileExpandResult:
    video_urls: list[str]
    pinned_urls: list[str]
    author: str


def expand_profile(
    page: Page,
    profile_url: str,
    max_videos: int,
    timeout_secs: int,
) -> ProfileExpandResult:
    """Expand a profile URL into individual video URLs using CDP browser.

    Dispatches to provider-specific expansion logic.
    Returns video URLs and the profile author name.
    """
    provider = resolve_provider(profile_url)
    expander = _PROFILE_EXPANDERS.get(provider.key)
    if expander is None:
        log_warn("profile.expand.unsupported", site=provider.key, url=full_url(profile_url))
        return ProfileExpandResult(video_urls=[], pinned_urls=[], author="")
    return expander(page, profile_url, max_videos, timeout_secs)


# Keep backward-compatible alias
def expand_profile_to_video_urls(
    page: Page,
    profile_url: str,
    max_videos: int,
    timeout_secs: int,
) -> list[str]:
    return expand_profile(page, profile_url, max_videos, timeout_secs).video_urls


def _expand_douyin_profile(
    page: Page,
    profile_url: str,
    max_videos: int,
    timeout_secs: int,
) -> ProfileExpandResult:
    """Extract recent video URLs from a Douyin user profile page.

    Strategy:
    1. Intercept XHR JSON responses containing aweme_list with aweme_id fields.
    2. Fallback: extract /video/ links from the DOM.
    3. Scroll to load more if needed.
    """
    collected_ids: list[str] = []
    pinned_ids: list[str] = []
    seen_ids: set[str] = set()

    def _collect_from_json(payload: object) -> None:
        if not isinstance(payload, dict):
            return
        aweme_list = payload.get("aweme_list")
        if not isinstance(aweme_list, list):
            for value in payload.values():
                if isinstance(value, (dict, list)):
                    _collect_from_json(value)
            return
        for item in aweme_list:
            if not isinstance(item, dict):
                continue
            aweme_id = item.get("aweme_id")
            if not isinstance(aweme_id, str) or not aweme_id:
                continue
            # Collect pinned/topped videos separately — they don't count against quota
            is_top = item.get("is_top") or item.get("tag", {}).get("is_top")
            if is_top and int(is_top) == 1:
                if aweme_id not in seen_ids:
                    seen_ids.add(aweme_id)
                    pinned_ids.append(aweme_id)
                    log_info("profile.expand.pinned", site="douyin", aweme_id=aweme_id)
                continue
            if aweme_id not in seen_ids:
                seen_ids.add(aweme_id)
                collected_ids.append(aweme_id)

    def on_response(response: Response) -> None:
        url = response.url.lower()
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" not in content_type and "aweme" not in url:
            return
        try:
            body = response.json()
        except Exception:
            return
        _collect_from_json(body)

    page.on("response", on_response)
    log_info("profile.expand.start", site="douyin", url=full_url(profile_url), max_videos=max_videos)

    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=timeout_secs * 1000)
    except Exception as exc:
        log_warn("profile.expand.goto_failed", site="douyin", url=full_url(profile_url), error=str(exc))
        return ProfileExpandResult(video_urls=[], pinned_urls=[], author="")

    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_secs * 1000, 8000))
    except Exception:
        pass

    page.wait_for_timeout(3000)

    # Scroll to load more videos if we don't have enough
    scroll_attempts = 0
    max_scroll_attempts = 5
    while len(collected_ids) < max_videos and scroll_attempts < max_scroll_attempts:
        prev_count = len(collected_ids)
        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        page.wait_for_timeout(2000)
        if len(collected_ids) == prev_count:
            scroll_attempts += 1
        else:
            scroll_attempts = 0

    # Fallback: extract video links from the DOM if XHR interception yielded nothing
    if not collected_ids:
        log_info("profile.expand.fallback_dom", site="douyin")
        hrefs = page.eval_on_selector_all(
            'a[href*="/video/"]',
            "els => els.map(e => e.getAttribute('href'))",
        )
        for href in hrefs:
            if not isinstance(href, str):
                continue
            match = DOUYIN_VIDEO_LINK_RE.search(href)
            if match:
                aweme_id = match.group(1)
                if aweme_id not in seen_ids:
                    seen_ids.add(aweme_id)
                    collected_ids.append(aweme_id)

    pinned_urls = [
        DOUYIN_VIDEO_URL_TEMPLATE.format(aweme_id=aweme_id)
        for aweme_id in pinned_ids
    ]
    video_urls = [
        DOUYIN_VIDEO_URL_TEMPLATE.format(aweme_id=aweme_id)
        for aweme_id in collected_ids[:max_videos]
    ]
    author = _extract_author_from_dom(page, [
        '[data-e2e="user-info"] .name',
        '[data-e2e="user-name"]',
        '.user-info .nickname',
        'h1.name',
        'span.name',
    ])
    log_info(
        "profile.expand.complete",
        site="douyin",
        url=full_url(profile_url),
        author=author,
        found=len(collected_ids),
        pinned=len(pinned_ids),
        returned=len(video_urls),
    )
    return ProfileExpandResult(video_urls=video_urls, pinned_urls=pinned_urls, author=author)


def _expand_bilibili_profile(
    page: Page,
    profile_url: str,
    max_videos: int,
    timeout_secs: int,
) -> ProfileExpandResult:
    """Extract recent video URLs from a Bilibili space page.

    Strategy:
    1. Navigate to space.bilibili.com/{uid}/video for chronological order.
    2. Intercept XHR JSON responses from arc/search API containing vlist/archives.
    3. Fallback: extract /video/BV... links from DOM.
    4. Scroll to load more if needed.
    """
    collected_bvids: list[str] = []
    seen_bvids: set[str] = set()

    def _collect_from_json(payload: object) -> None:
        if not isinstance(payload, dict):
            return
        data = payload.get("data")
        if not isinstance(data, dict):
            # Recurse into nested dicts
            for value in payload.values():
                if isinstance(value, dict):
                    _collect_from_json(value)
            return
        # arc/search API: data.list.vlist
        vlist_container = data.get("list")
        if isinstance(vlist_container, dict):
            vlist = vlist_container.get("vlist")
            if isinstance(vlist, list):
                for item in vlist:
                    if not isinstance(item, dict):
                        continue
                    bvid = item.get("bvid")
                    if isinstance(bvid, str) and bvid and bvid not in seen_bvids:
                        seen_bvids.add(bvid)
                        collected_bvids.append(bvid)
        # Newer API variant: data.archives
        archives = data.get("archives")
        if isinstance(archives, list):
            for item in archives:
                if not isinstance(item, dict):
                    continue
                bvid = item.get("bvid")
                if isinstance(bvid, str) and bvid and bvid not in seen_bvids:
                    seen_bvids.add(bvid)
                    collected_bvids.append(bvid)

    def on_response(response: Response) -> None:
        url = response.url.lower()
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            return
        if not any(hint in url for hint in ("arc/search", "space", "wbi")):
            return
        try:
            body = response.json()
        except Exception:
            return
        _collect_from_json(body)

    page.on("response", on_response)

    # Navigate to the first explicit page. Building this through the same URL
    # helper avoids malformed URLs when the profile already contains a query.
    video_tab_url = _bilibili_video_page_url(profile_url, 1)
    log_info("profile.expand.start", site="bilibili", url=full_url(video_tab_url), max_videos=max_videos)

    try:
        page.goto(video_tab_url, wait_until="domcontentloaded", timeout=timeout_secs * 1000)
    except Exception as exc:
        log_warn("profile.expand.goto_failed", site="bilibili", url=full_url(video_tab_url), error=str(exc))
        return ProfileExpandResult(video_urls=[], pinned_urls=[], author="")

    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_secs * 1000, 8000))
    except Exception:
        pass

    page.wait_for_timeout(3000)

    def collect_from_dom() -> int:
        before = len(collected_bvids)
        try:
            hrefs = page.eval_on_selector_all(
                'a[href*="/video/BV"]',
                "els => els.map(e => e.getAttribute('href'))",
            )
        except Exception:
            hrefs = []
        for href in hrefs:
            if not isinstance(href, str):
                continue
            match = BILIBILI_BVID_RE.search(href)
            if match:
                bvid = match.group(1)
                if bvid not in seen_bvids:
                    seen_bvids.add(bvid)
                    collected_bvids.append(bvid)
        return len(collected_bvids) - before

    collect_from_dom()

    # Scroll first in case the current Bilibili layout lazy-loads cards.
    scroll_attempts = 0
    max_scroll_attempts = 5
    while len(collected_bvids) < max_videos and scroll_attempts < max_scroll_attempts:
        prev_count = len(collected_bvids)
        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        page.wait_for_timeout(2000)
        collect_from_dom()
        if len(collected_bvids) == prev_count:
            scroll_attempts += 1
        else:
            scroll_attempts = 0

    # Bilibili space pages are paginated rather than infinitely scrolling.
    # Navigate explicit page numbers when the first page does not satisfy the
    # requested count. This also avoids repeatedly hitting the guarded WBI API.
    page_number = 2
    max_page_number = max(2, (max_videos + 24) // 25 + 1)
    while len(collected_bvids) < max_videos and page_number <= max_page_number:
        before = len(collected_bvids)
        page_url = _bilibili_video_page_url(profile_url, page_number)
        log_info(
            "profile.expand.bilibili_page",
            page=page_number,
            collected=before,
            url=full_url(page_url),
        )
        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=timeout_secs * 1000)
            page.wait_for_timeout(2000)
            collect_from_dom()
        except Exception as exc:
            log_warn(
                "profile.expand.bilibili_page_failed",
                page=page_number,
                error=str(exc),
            )
            break
        if len(collected_bvids) == before:
            break
        page_number += 1

    video_urls = [
        BILIBILI_VIDEO_URL_TEMPLATE.format(bvid=bvid)
        for bvid in collected_bvids[:max_videos]
    ]
    author = _extract_author_from_dom(page, [
        '#h-name',
        '.h-name',
        '.nickname',
        'span.name',
    ])
    log_info(
        "profile.expand.complete",
        site="bilibili",
        url=full_url(profile_url),
        author=author,
        found=len(collected_bvids),
        returned=len(video_urls),
    )
    return ProfileExpandResult(video_urls=video_urls, pinned_urls=[], author=author)


def _extract_xhs_video_urls_from_dom(page: Page) -> list[str]:
    """Extract complete video note URLs from XHS profile DOM.

    Each note card is a <section class="note-item"> containing:
    - A hidden <a href="/explore/{noteId}?xsec_token=..."> link
    - A <span class="play-icon"> if the note is a video
    The access token in the link is required by current Xiaohongshu pages.
    """
    result = page.evaluate("""() => {
        var items = document.querySelectorAll("section.note-item");
        var urls = [];
        for (var i = 0; i < items.length; i++) {
            var el = items[i];
            if (!el.querySelector(".play-icon")) continue;
            var links = el.querySelectorAll("a[href*='/explore/']");
            for (var j = 0; j < links.length; j++) {
                var href = links[j].getAttribute("href") || "";
                var m = href.match(/\\/explore\\/([A-Za-z0-9]+)/);
                if (m && m[1]) {
                    urls.push(new URL(href, window.location.origin).href);
                    break;
                }
            }
        }
        return urls;
    }""")
    if not isinstance(result, list):
        return []
    return [url for url in result if isinstance(url, str) and "/explore/" in url]


def _extract_xhs_video_note_ids_from_dom(page: Page) -> list[str]:
    """Backward-compatible helper returning IDs from complete DOM URLs."""
    note_ids: list[str] = []
    for url in _extract_xhs_video_urls_from_dom(page):
        match = XHS_NOTE_LINK_RE.search(url)
        if match:
            note_ids.append(match.group(1))
    return note_ids


def _xhs_login_prompt_visible(page: Page) -> bool:
    try:
        return bool(page.evaluate("""() => {
            const selectors = [
                "input[type='password']",
                "input[placeholder*='手机号']",
                "input[placeholder*='手机号码']",
                ".login-container",
                ".login-modal",
                "[class*='login-modal']",
                "[class*='login-container']"
            ];
            if (selectors.some(selector => document.querySelector(selector))) return true;
            const text = (document.body && document.body.innerText || "").replace(/\\s+/g, "");
            return [
                "登录后查看",
                "登录即可查看",
                "手机号登录",
                "扫码登录",
                "密码登录"
            ].some(value => text.includes(value));
        }"""))
    except Exception:
        return False


def _show_xhs_login_banner(page: Page, message: str, success: bool = False) -> None:
    try:
        page.evaluate(
            """({message, success}) => {
                let banner = document.getElementById("videocp-xhs-login-banner");
                if (!banner) {
                    banner = document.createElement("div");
                    banner.id = "videocp-xhs-login-banner";
                    banner.style.cssText = [
                        "position:fixed",
                        "top:16px",
                        "left:50%",
                        "transform:translateX(-50%)",
                        "z-index:2147483647",
                        "padding:10px 16px",
                        "border-radius:8px",
                        "color:white",
                        "font:600 14px -apple-system,BlinkMacSystemFont,sans-serif",
                        "box-shadow:0 6px 24px rgba(0,0,0,.24)",
                        "pointer-events:none"
                    ].join(";");
                    document.documentElement.appendChild(banner);
                }
                banner.style.background = success ? "#1f9d61" : "#ff2442";
                banner.textContent = message;
            }""",
            {"message": message, "success": success},
        )
    except Exception:
        pass


def _wait_for_xhs_login(page: Page, timeout_secs: int = 180) -> bool:
    deadline = time.monotonic() + max(30, timeout_secs)
    next_log_at = time.monotonic()
    _show_xhs_login_banner(page, "请完成小红书登录，登录成功后 App 会自动继续")
    log_info("profile.expand.login_wait", site="xiaohongshu", timeout_secs=max(30, timeout_secs))
    while time.monotonic() < deadline:
        if _extract_xhs_video_urls_from_dom(page):
            _show_xhs_login_banner(page, "登录成功，正在读取主页视频", success=True)
            page.wait_for_timeout(1500)
            log_info("profile.expand.login_complete", site="xiaohongshu")
            return True
        now = time.monotonic()
        if now >= next_log_at:
            remaining = max(0, int(deadline - now))
            log_info("profile.expand.login_waiting", site="xiaohongshu", remaining_secs=remaining)
            next_log_at = now + 15
        page.wait_for_timeout(1000)
    log_warn("profile.expand.login_timeout", site="xiaohongshu", timeout_secs=max(30, timeout_secs))
    return False


def _expand_xiaohongshu_profile(
    page: Page,
    profile_url: str,
    max_videos: int,
    timeout_secs: int,
) -> ProfileExpandResult:
    """Extract recent video note URLs from a Xiaohongshu user profile page.

    Strategy:
    1. Intercept profile JSON responses and collect video note IDs.
    2. Navigate to profile, waiting for interactive login when required.
    3. Extract video note IDs from DOM and scroll to load more if needed.
    """
    seen_note_ids: set[str] = set()
    collected_video_urls: list[str] = []

    def _add_note(value: object, token: object = "", source: object = "") -> None:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]{16,32}", value):
            return
        if value not in seen_note_ids:
            seen_note_ids.add(value)
            query: dict[str, str] = {}
            if isinstance(token, str) and token:
                query["xsec_token"] = token
            if isinstance(source, str) and source:
                query["xsec_source"] = source
            suffix = f"?{urlencode(query)}" if query else ""
            collected_video_urls.append(f"{XHS_EXPLORE_URL_TEMPLATE.format(note_id=value)}{suffix}")

    def _collect_from_json(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                _collect_from_json(item)
            return
        if not isinstance(value, dict):
            return
        note_card = value.get("note_card")
        card = note_card if isinstance(note_card, dict) else value
        note_type = str(card.get("type") or card.get("note_type") or "").lower()
        has_video = (
            note_type == "video"
            or isinstance(card.get("video"), dict)
            or isinstance(card.get("video_info"), dict)
            or isinstance(card.get("videoInfo"), dict)
        )
        if has_video:
            token = (
                value.get("xsec_token")
                or value.get("xsecToken")
                or card.get("xsec_token")
                or card.get("xsecToken")
            )
            source = (
                value.get("xsec_source")
                or value.get("xsecSource")
                or card.get("xsec_source")
                or card.get("xsecSource")
                or "pc_user"
            )
            _add_note(value.get("note_id") or value.get("noteId") or value.get("id"), token, source)
            _add_note(card.get("note_id") or card.get("noteId") or card.get("id"), token, source)
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                _collect_from_json(nested)

    def on_response(response: Response) -> None:
        url = response.url.lower()
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            return
        if not any(hint in url for hint in ("user_posted", "/feed", "/note", "xiaohongshu")):
            return
        try:
            _collect_from_json(response.json())
        except Exception:
            return

    page.on("response", on_response)
    log_info("profile.expand.start", site="xiaohongshu", url=full_url(profile_url), max_videos=max_videos)

    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=timeout_secs * 1000)
    except Exception as exc:
        log_warn("profile.expand.goto_failed", site="xiaohongshu", url=full_url(profile_url), error=str(exc))
        return ProfileExpandResult(video_urls=[], pinned_urls=[], author="")

    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_secs * 1000, 8000))
    except Exception:
        pass

    page.wait_for_timeout(3000)

    def _collect_from_dom() -> None:
        for video_url in _extract_xhs_video_urls_from_dom(page):
            match = XHS_NOTE_LINK_RE.search(video_url)
            if not match or match.group(1) in seen_note_ids:
                continue
            seen_note_ids.add(match.group(1))
            collected_video_urls.append(urljoin(profile_url, video_url))

    _collect_from_dom()
    log_info("profile.expand.dom", site="xiaohongshu", found=len(collected_video_urls))

    if not collected_video_urls and _xhs_login_prompt_visible(page):
        login_timeout_secs = max(180, timeout_secs * 4)
        if not _wait_for_xhs_login(page, timeout_secs=login_timeout_secs):
            raise DownloadError(
                f"小红书登录等待超时（{login_timeout_secs} 秒）。请重新下载，并在弹出的浏览器中完成登录。"
            )
        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout_secs * 1000, 8000))
        except Exception:
            pass
        _collect_from_dom()
        log_info("profile.expand.dom_after_login", site="xiaohongshu", found=len(collected_video_urls))

    # Scroll to load more if needed
    scroll_attempts = 0
    max_scroll_attempts = 5
    while len(collected_video_urls) < max_videos and scroll_attempts < max_scroll_attempts:
        prev_count = len(collected_video_urls)
        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        page.wait_for_timeout(2000)
        _collect_from_dom()
        if len(collected_video_urls) == prev_count:
            scroll_attempts += 1
        else:
            scroll_attempts = 0

    author = _extract_author_from_dom(page, [
        ".user-name",
        ".user-nickname",
        ".info .name",
        "span.name",
    ])

    video_urls = collected_video_urls[:max_videos]
    log_info(
        "profile.expand.complete",
        site="xiaohongshu",
        url=full_url(profile_url),
        author=author,
        found=len(collected_video_urls),
        returned=len(video_urls),
    )
    return ProfileExpandResult(video_urls=video_urls, pinned_urls=[], author=author)


def _expand_instagram_reels(
    page: Page,
    profile_url: str,
    max_videos: int,
    timeout_secs: int,
) -> ProfileExpandResult:
    """Extract recent reel URLs from an Instagram profile/reels page.

    Strategy:
    1. Navigate to profile reels tab, wait for hydration.
    2. Extract /reel/{shortcode} links from the DOM.
    3. Scroll to load more if needed.
    """
    # Ensure we land on the reels tab
    reels_url = profile_url.rstrip("/")
    if not reels_url.endswith("/reels"):
        reels_url += "/reels"
    reels_url += "/"

    log_info("profile.expand.start", site="instagram", url=full_url(reels_url), max_videos=max_videos)

    try:
        page.goto(reels_url, wait_until="domcontentloaded", timeout=timeout_secs * 1000)
    except Exception as exc:
        log_warn("profile.expand.goto_failed", site="instagram", url=full_url(reels_url), error=str(exc))
        return ProfileExpandResult(video_urls=[], pinned_urls=[], author="")

    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_secs * 1000, 10000))
    except Exception:
        pass

    page.wait_for_timeout(3000)

    seen_codes: set[str] = set()
    collected_codes: list[str] = []

    def _collect_from_dom() -> None:
        hrefs = page.eval_on_selector_all(
            'a[href*="/reel/"]',
            "els => els.map(e => e.getAttribute('href'))",
        )
        for href in hrefs:
            if not isinstance(href, str):
                continue
            match = INSTAGRAM_REEL_LINK_RE.search(href)
            if match:
                code = match.group(1)
                if code not in seen_codes:
                    seen_codes.add(code)
                    collected_codes.append(code)

    _collect_from_dom()
    log_info("profile.expand.dom", site="instagram", found=len(collected_codes))

    # Scroll to load more if needed
    scroll_attempts = 0
    max_scroll_attempts = 5
    while len(collected_codes) < max_videos and scroll_attempts < max_scroll_attempts:
        prev_count = len(collected_codes)
        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        page.wait_for_timeout(2000)
        _collect_from_dom()
        if len(collected_codes) == prev_count:
            scroll_attempts += 1
        else:
            scroll_attempts = 0

    author = _extract_author_from_dom(page, [
        'header h2',
        'header span',
        'title',
    ])
    # Fallback: try to extract username from URL
    if not author:
        from urllib.parse import urlparse
        path_parts = urlparse(profile_url).path.strip("/").split("/")
        if path_parts:
            author = path_parts[0]

    video_urls = [
        INSTAGRAM_REEL_URL_TEMPLATE.format(shortcode=code)
        for code in collected_codes[:max_videos]
    ]
    log_info(
        "profile.expand.complete",
        site="instagram",
        url=full_url(profile_url),
        author=author,
        found=len(collected_codes),
        returned=len(video_urls),
    )
    return ProfileExpandResult(video_urls=video_urls, pinned_urls=[], author=author)


# Provider-keyed dispatch table.
_PROFILE_EXPANDERS: dict[str, type[None] | callable] = {
    "douyin": _expand_douyin_profile,
    "bilibili": _expand_bilibili_profile,
    "xiaohongshu": _expand_xiaohongshu_profile,
}
