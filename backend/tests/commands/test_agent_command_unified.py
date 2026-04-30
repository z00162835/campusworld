"""Unified ``agent`` command: registry cut-over and JSON shape."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_get_agent_commands_registers_agent_and_aico_only():
    from app.commands import agent_commands

    agent_commands._agent_commands_cache = None
    cmds = agent_commands.get_agent_commands()
    names = {c.name for c in cmds}
    assert names == {"aico", "agent"}
    assert all(c.name not in ("agent_tools", "agent_capabilities") for c in cmds)


def test_agent_row_dict_emits_id_not_service_id():
    from app.commands.agent_commands import _agent_row_dict

    node = MagicMock()
    node.id = 42
    node.name = "TestAgent"
    node.is_active = True
    node.attributes = {"service_id": "alpha"}

    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None

    row = _agent_row_dict(node, session)
    assert row["id"] == "alpha"
    assert row["agent_node_id"] == 42
    assert "service_id" not in row


@patch("app.commands.agent_commands.resolve_npc_agent_by_handle")
def test_agent_show_includes_id_in_data(resolve_mock: MagicMock) -> None:
    from app.commands.agent_commands import AgentCommand
    from app.commands.base import CommandContext
    from app.models.graph import Node, NodeType

    node = MagicMock(spec=Node)
    node.id = 7
    node.type_id = 1
    node.attributes = {"service_id": "svc", "decision_mode": "llm"}
    resolve_mock.return_value = (node, None)

    nt = MagicMock(spec=NodeType)
    nt.typeclass = "NpcAgent"

    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = nt

    ctx = CommandContext(
        user_id="u",
        username="u",
        session_id="s",
        permissions=[],
        db_session=session,
    )
    res = AgentCommand().execute(ctx, ["show", "svc"])
    assert res.success
    assert res.data is not None
    assert res.data.get("id") == "svc"
    assert res.data.get("agent_node_id") == 7
    assert "service_id" not in (res.data or {})


@patch("app.commands.agent_commands.flag_modified")
@patch("app.commands.agent_commands.permission_checker.check_permission", return_value=True)
@patch("app.commands.agent_commands._resolve_tool_to_primary", return_value="look")
@patch("app.commands.agent_commands.resolve_npc_agent_by_handle")
def test_agent_tool_add_success_data_uses_id(
    resolve_mock: MagicMock, _prim: MagicMock, _perm: MagicMock, _fm: MagicMock
) -> None:
    from app.commands.agent_commands import AgentCommand
    from app.commands.base import CommandContext
    from app.models.graph import Node

    node = MagicMock(spec=Node)
    node.id = 99
    node.attributes = {"service_id": "x1", "tool_allowlist": []}
    resolve_mock.return_value = (node, None)

    session = MagicMock()
    ctx = CommandContext(
        user_id="u",
        username="u",
        session_id="s",
        permissions=["admin.agent.tools.manage"],
        db_session=session,
    )
    res = AgentCommand().execute(ctx, ["tool", "add", "x1", "look"])
    assert res.success
    assert res.data is not None
    assert res.data.get("id") == "x1"
    assert "service_id" not in (res.data or {})
