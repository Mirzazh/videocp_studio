from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from videocp.errors import DownloadError
from videocp.profile_expander import _bilibili_video_page_url, _expand_bilibili_profile, _expand_xiaohongshu_profile


class FakeXhsPage:
    def __init__(self, *, login_visible: bool = True, unlock_after_wait: bool = True):
        self.login_visible = login_visible
        self.unlock_after_wait = unlock_after_wait
        self.banner_shown = False
        self.content_ready = False
        self.response_handler = None

    def on(self, event, handler):
        if event == "response":
            self.response_handler = handler

    def goto(self, *args, **kwargs):
        return None

    def wait_for_load_state(self, *args, **kwargs):
        return None

    def wait_for_timeout(self, milliseconds):
        if self.banner_shown and self.unlock_after_wait and milliseconds <= 1500:
            self.content_ready = True
            self.login_visible = False

    def evaluate(self, script, arg=None):
        if arg is not None:
            self.banner_shown = True
            return None
        if "document.querySelectorAll(\"section.note-item\")" in script:
            return [
                "https://www.xiaohongshu.com/explore/69be081c0000000021010b12"
                "?xsec_token=token-demo&xsec_source=pc_user"
            ] if self.content_ready else []
        if "const selectors" in script:
            return self.login_visible
        return None

    def query_selector(self, selector):
        return None


class EmptyLocator:
    @property
    def first(self):
        return self

    def count(self):
        return 0

    def is_disabled(self):
        return True

    def click(self):
        raise AssertionError("empty locator should not be clicked")


class FakeBilibiliPage:
    def __init__(self, pages: dict[int, list[str]], direct_pages: set[int] | None = None):
        self.pages = pages
        self.direct_pages = direct_pages or {1}
        self.response_handler = None
        self.goto_urls: list[str] = []
        self.clicked_pages: list[int] = []

    def on(self, event, handler):
        if event == "response":
            self.response_handler = handler

    def _emit_page(self, page_number: int):
        if self.response_handler is None or page_number not in self.pages:
            return
        self.response_handler(
            SimpleNamespace(
                url=f"https://api.bilibili.com/x/space/wbi/arc/search?pn={page_number}",
                headers={"content-type": "application/json"},
                json=lambda: {
                    "data": {
                        "archives": [
                            {"bvid": bvid}
                            for bvid in self.pages[page_number]
                        ]
                    }
                },
            )
        )

    def goto(self, url, *args, **kwargs):
        self.goto_urls.append(url)
        parsed = urlparse(url)
        page_number = int(parse_qs(parsed.query).get("pn", ["1"])[0])
        if page_number in self.direct_pages:
            self._emit_page(page_number)

    def wait_for_load_state(self, *args, **kwargs):
        return None

    def wait_for_timeout(self, milliseconds):
        return None

    def eval_on_selector_all(self, selector, script):
        return []

    def evaluate(self, script, arg=None):
        if arg is not None:
            page_number = int(arg)
            self.clicked_pages.append(page_number)
            self._emit_page(page_number)
            return page_number in self.pages
        return None

    def locator(self, selector):
        return EmptyLocator()

    def query_selector(self, selector):
        return SimpleNamespace(text_content=lambda: "测试UP主")


def test_bilibili_page_url_preserves_order_and_sets_page_number():
    result = _bilibili_video_page_url(
        "https://space.bilibili.com/7612168/video?order=click",
        3,
    )

    assert result == "https://space.bilibili.com/7612168/video?order=click&pn=3"


def test_bilibili_profile_keeps_collecting_after_first_40_by_clicking_next():
    page = FakeBilibiliPage(
        pages={
            1: [f"BV{index:03d}" for index in range(1, 41)],
            2: [f"BV{index:03d}" for index in range(41, 81)],
        },
        direct_pages={1},
    )

    result = _expand_bilibili_profile(
        page=page,
        profile_url="https://space.bilibili.com/7612168/video",
        max_videos=80,
        timeout_secs=1,
    )

    assert len(result.video_urls) == 80
    assert result.video_urls[39] == "https://www.bilibili.com/video/BV040"
    assert result.video_urls[-1] == "https://www.bilibili.com/video/BV080"
    assert page.clicked_pages == [2]


def test_bilibili_profile_popular_pagination_preserves_click_order():
    page = FakeBilibiliPage(
        pages={
            1: [f"BV{index:03d}" for index in range(1, 41)],
            2: [f"BV{index:03d}" for index in range(41, 51)],
        },
        direct_pages={1, 2},
    )

    result = _expand_bilibili_profile(
        page=page,
        profile_url="https://space.bilibili.com/7612168/video?order=click",
        max_videos=45,
        timeout_secs=1,
    )

    assert len(result.video_urls) == 45
    assert result.video_urls[-1] == "https://www.bilibili.com/video/BV045"
    assert any("order=click" in url and "pn=2" in url for url in page.goto_urls)


def test_xiaohongshu_profile_waits_for_login_then_continues():
    page = FakeXhsPage()

    result = _expand_xiaohongshu_profile(
        page=page,
        profile_url="https://www.xiaohongshu.com/user/profile/demo",
        max_videos=1,
        timeout_secs=1,
    )

    assert page.banner_shown is True
    assert result.video_urls == [
        "https://www.xiaohongshu.com/explore/69be081c0000000021010b12"
        "?xsec_token=token-demo&xsec_source=pc_user"
    ]


def test_xiaohongshu_profile_reports_login_timeout(monkeypatch):
    page = FakeXhsPage(unlock_after_wait=False)
    monkeypatch.setattr("videocp.profile_expander._wait_for_xhs_login", lambda *args, **kwargs: False)

    with pytest.raises(DownloadError, match="小红书登录等待超时"):
        _expand_xiaohongshu_profile(
            page=page,
            profile_url="https://www.xiaohongshu.com/user/profile/demo",
            max_videos=1,
            timeout_secs=1,
        )


def test_xiaohongshu_profile_collects_video_ids_from_json():
    page = FakeXhsPage(login_visible=False, unlock_after_wait=False)

    def goto(*args, **kwargs):
        page.response_handler(
            SimpleNamespace(
                url="https://edith.xiaohongshu.com/api/sns/web/v1/user_posted",
                headers={"content-type": "application/json"},
                json=lambda: {
                    "data": {
                        "notes": [
                            {
                                "note_id": "69be081c0000000021010b12",
                                "xsec_token": "token-json",
                                "xsec_source": "pc_user",
                                "note_card": {"type": "video"},
                            }
                        ]
                    }
                },
            )
        )

    page.goto = goto
    result = _expand_xiaohongshu_profile(
        page=page,
        profile_url="https://www.xiaohongshu.com/user/profile/demo",
        max_videos=1,
        timeout_secs=1,
    )

    assert result.video_urls == [
        "https://www.xiaohongshu.com/explore/69be081c0000000021010b12"
        "?xsec_token=token-json&xsec_source=pc_user"
    ]
