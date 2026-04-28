"""SSHHandler command result formatting (usage vs. errors)."""

import pytest
from app.protocols.ssh_handler import SSHHandler
from app.commands.base import CommandResult


@pytest.mark.unit
def test_error_result_prefixed_error():
    h = SSHHandler()
    r = CommandResult.error_result("database session required")
    assert h._format_command_result(r) == "Error: database session required\n"


@pytest.mark.unit
def test_usage_is_usage_no_error_prefix():
    h = SSHHandler()
    r = CommandResult.error_result("agent <list|status> ...", is_usage=True)
    out = h._format_command_result(r)
    assert not out.startswith("Error:")
    assert "usage: agent" in out


@pytest.mark.unit
def test_usage_message_starts_with_usage_passthrough():
    h = SSHHandler()
    r = CommandResult.error_result("usage: aico <message...>")
    assert h._format_command_result(r) == "usage: aico <message...>\n"


@pytest.mark.unit
def test_usage_chinese_用法_prefix_passthrough():
    h = SSHHandler()
    r = CommandResult.error_result("用法: go <direction>")
    assert h._format_command_result(r) == "用法: go <direction>\n"
