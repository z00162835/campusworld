"""Unit tests for try_dispatch_at_line (line-prefix assistant dispatch)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.commands.at_agent_dispatch import try_dispatch_at_line
from app.commands.base import CommandContext


@pytest.mark.unit
def test_try_dispatch_not_at_line():
    ctx = CommandContext("1", "u", "s", [], db_session=MagicMock())
    assert try_dispatch_at_line("look", ctx) is None


@pytest.mark.unit
@patch("app.commands.at_agent_dispatch.run_npc_agent_nlp_tick")
@patch("app.commands.at_agent_dispatch.resolve_npc_agent_by_handle")
def test_try_dispatch_success(mock_resolve, mock_tick):
    node = MagicMock()
    node.attributes = {"decision_mode": "llm"}
    mock_resolve.return_value = (node, None)
    mock_res = MagicMock()
    mock_res.ok = True
    mock_res.message = "hi"
    mock_res.final_phase = "act"
    mock_tick.return_value = mock_res

    ctx = CommandContext("1", "u", "s", ["admin.system"], db_session=MagicMock())
    with patch("app.commands.at_agent_dispatch.command_registry.get_command", return_value=None):
        r = try_dispatch_at_line('@aico hello', ctx)

    assert r is not None and r.success
    mock_tick.assert_called_once()


@pytest.mark.unit
@patch("app.commands.at_agent_dispatch.resolve_npc_agent_by_handle")
def test_try_dispatch_resolve_error(mock_resolve):
    mock_resolve.return_value = (None, "unknown agent handle 'x'. Type 'help' for available commands.")

    ctx = CommandContext("1", "u", "s", [], db_session=MagicMock())
    with patch("app.commands.at_agent_dispatch.command_registry.get_command", return_value=None):
        r = try_dispatch_at_line('@x hello', ctx)

    assert r is not None and not r.success
    assert "unknown" in r.message.lower()
