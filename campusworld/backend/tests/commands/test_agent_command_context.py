"""command_context_for_npc_agent resolution."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.agent_command_context import command_context_for_npc_agent
from app.commands.base import CommandContext


def test_uses_invoker_when_no_service_account():
    agent = MagicMock()
    agent.id = 7
    agent.attributes = {}
    session = MagicMock()
    fb = CommandContext(
        user_id="10",
        username="invoker",
        session_id="sess",
        permissions=["p1"],
        roles=["r1"],
        db_session=session,
    )
    ctx = command_context_for_npc_agent(session, agent, fb)
    assert ctx.user_id == "10"
    assert ctx.permissions == ["p1"]
    assert ctx.metadata.get("principal") == "invoker"
    assert ctx.metadata.get("agent_node_id") == 7


def test_resolves_service_account_node():
    from app.models.graph import Node

    acc = MagicMock(spec=Node)
    acc.id = 99
    acc.name = "svc_acc"
    acc.attributes = {"permissions": ["agent.x"], "roles": ["bot"]}

    agent = MagicMock(spec=Node)
    agent.id = 3
    agent.attributes = {"service_account_id": "99"}

    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = acc

    fb = CommandContext(
        user_id="10",
        username="invoker",
        session_id="sess1",
        permissions=["ignored"],
        db_session=session,
    )
    ctx = command_context_for_npc_agent(session, agent, fb)

    assert ctx.user_id == "99"
    assert ctx.username == "svc_acc"
    assert "agent.x" in ctx.permissions
    assert "bot" in ctx.roles
    assert ctx.metadata.get("principal") == "service_account"
    assert ctx.metadata.get("agent_node_id") == 3
