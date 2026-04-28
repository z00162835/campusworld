import pytest

from app.commands.ability_sync import _sync_llm_hints_from_command
from app.commands.base import BaseCommand, CommandContext, CommandResult, CommandType


class _Dummy(BaseCommand):
    def __init__(self):
        super().__init__("x", "Alpha")
        self.description_i18n = {"zh-CN": "甲", "en-US": "A"}

    def execute(self, context: CommandContext, args):
        return CommandResult.success_result("ok")


@pytest.mark.unit
def test_sync_llm_hints_from_command() -> None:
    d = _Dummy()
    attrs: dict = {}
    _sync_llm_hints_from_command(d, attrs)
    # tool_manifest_locale is zh-CN by default: pick zh line for llm_hint
    assert attrs["llm_hint"] == "甲"
    assert attrs["llm_hint_i18n"] == {"zh-CN": "甲", "en-US": "A"}
