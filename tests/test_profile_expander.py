from types import SimpleNamespace

import pytest

from videocp.errors import DownloadError
from videocp.profile_expander import _expand_xiaohongshu_profile


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
