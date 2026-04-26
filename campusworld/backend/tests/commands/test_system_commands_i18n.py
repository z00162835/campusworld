"""i18n contract tests for the four pure-text system commands.

Covers ``quit`` / ``time`` / ``stats`` / ``whoami``: each resolves user-facing
text through ``commands.<name>.<key>`` locale bundles; fallback chain hits
en-US when zh-CN explicit, etc.
"""

from __future__ import annotations

import pytest

from app.commands.base import CommandContext
from app.commands.system_commands import (
    QuitCommand,
    StatsCommand,
    TimeCommand,
    WhoamiCommand,
)


def _ctx(locale: str = "en-US"):
    return CommandContext(
        user_id="1",
        username="admin",
        session_id="s1",
        permissions=[],
        roles=[],
        metadata={"locale": locale},
    )


@pytest.mark.unit
def test_quit_uses_en_us_goodbye_locale():
    res = QuitCommand().execute(_ctx("en-US"), [])
    assert res.success is True
    assert res.message == "Goodbye!"
    assert getattr(res, "should_exit", False) is True


@pytest.mark.unit
def test_quit_uses_zh_cn_goodbye_locale():
    res = QuitCommand().execute(_ctx("zh-CN"), [])
    assert res.success is True
    assert res.message == "再见！"
    assert getattr(res, "should_exit", False) is True


@pytest.mark.unit
def test_time_format_template_en_us():
    res = TimeCommand().execute(_ctx("en-US"), [])
    assert res.success is True
    assert res.message.startswith("Current time: ")


@pytest.mark.unit
def test_time_format_template_zh_cn():
    res = TimeCommand().execute(_ctx("zh-CN"), [])
    assert res.success is True
    assert res.message.startswith("当前时间：")


@pytest.mark.unit
def test_stats_title_localized_en_us():
    res = StatsCommand().execute(_ctx("en-US"), [])
    assert res.success is True
    assert "System Statistics:" in res.message


@pytest.mark.unit
def test_stats_title_localized_zh_cn():
    res = StatsCommand().execute(_ctx("zh-CN"), [])
    assert res.success is True
    assert "系统统计:" in res.message


@pytest.mark.unit
def test_whoami_template_en_us():
    res = WhoamiCommand().execute(_ctx("en-US"), [])
    assert res.success is True
    assert res.message == "Current user: admin"


@pytest.mark.unit
def test_whoami_template_zh_cn():
    res = WhoamiCommand().execute(_ctx("zh-CN"), [])
    assert res.success is True
    assert res.message == "当前用户：admin"
