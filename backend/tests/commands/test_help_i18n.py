import pytest

from app.commands.base import CommandContext, CommandResult
from app.commands.init_commands import initialize_commands
from app.commands.system_commands import HelpCommand


@pytest.fixture(scope="module", autouse=True)
def _load_cmds():
    initialize_commands()
    yield


def _ctx(locale: str) -> CommandContext:
    return CommandContext(
        user_id="1",
        username="u1",
        session_id="s",
        permissions=[],
        metadata={"locale": locale},
    )


@pytest.mark.unit
def test_help_list_zh_shell() -> None:
    h = HelpCommand()
    r = h.execute(_ctx("zh-CN"), [])
    assert r.success
    assert "可用命令" in r.message


@pytest.mark.unit
def test_help_list_en_shell() -> None:
    h = HelpCommand()
    r = h.execute(_ctx("en-US"), [])
    assert r.success
    assert "Available Commands" in r.message


@pytest.mark.unit
def test_help_detail_matches_locale() -> None:
    h = HelpCommand()
    r_en: CommandResult = h.execute(_ctx("en-US"), ["version"])
    assert "Description:" in r_en.message
    r_zh: CommandResult = h.execute(_ctx("zh-CN"), ["version"])
    assert "描述:" in r_zh.message
