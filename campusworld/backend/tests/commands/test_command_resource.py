import pytest

from app.commands.i18n.command_resource import (
    get_command_i18n_map,
    get_localized_string_from_resource,
)


@pytest.mark.unit
def test_help_string_in_both_locales() -> None:
    m = get_command_i18n_map("help", "description")
    assert "zh-CN" in m and "en-US" in m
    assert "列出" in m["zh-CN"]
    assert "List available" in m["en-US"]


@pytest.mark.unit
def test_get_localized_string_from_resource_zh() -> None:
    s = get_localized_string_from_resource("help", "description", "zh-CN")
    assert "列出" in s
