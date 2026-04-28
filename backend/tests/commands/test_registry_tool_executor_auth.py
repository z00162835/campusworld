"""RegistryToolExecutor: policy alignment with CommandRegistry (authorize + list)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import CommandContext
from app.commands.policy_store import CommandPolicyRepository


def _policy(*, enabled=True, any_perms=None, all_perms=None, roles_any=None):
    m = MagicMock()
    m.enabled = enabled
    m.required_permissions_any = list(any_perms or [])
    m.required_permissions_all = list(all_perms or [])
    m.required_roles_any = list(roles_any or [])
    m.policy_expr = None
    return m


@pytest.fixture(autouse=True)
def _register_help_and_notice():
    """Minimal registry rows — avoids full initialize_commands (builder model discovery)."""
    from app.commands.game.notice_command import NoticeCommand
    from app.commands.registry import command_registry
    from app.commands.system_commands import HelpCommand

    for cmd in (HelpCommand(), NoticeCommand()):
        if command_registry.get_command(cmd.name) is None:
            command_registry.register_command(cmd)


def test_registry_tool_executor_denies_execute_when_policy_denies():
    from app.game_engine.agent_runtime.tooling import RegistryToolExecutor

    session = MagicMock()
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        db_session=session,
    )

    def fake_get_policy(name):
        if name == "notice":
            return _policy(any_perms=["admin.system_notice"])
        return _policy(any_perms=[])

    with patch.object(CommandPolicyRepository, "get_policy", side_effect=fake_get_policy):
        ex = RegistryToolExecutor()
        r = ex.execute_command(ctx, "notice", ["list"])

    assert not r.success
    assert "not authorized" in r.message.lower()


def test_registry_tool_executor_allows_execute_when_policy_allows():
    from app.game_engine.agent_runtime.tooling import RegistryToolExecutor

    session = MagicMock()
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        db_session=session,
    )

    def fake_get_policy(name):
        if name == "help":
            return _policy(any_perms=[])
        return _policy(any_perms=["admin.blocked"])

    with patch.object(CommandPolicyRepository, "get_policy", side_effect=fake_get_policy):
        ex = RegistryToolExecutor()
        r = ex.execute_command(ctx, "help", [])

    assert r.success


def test_list_tool_ids_matches_get_available_commands_not_raw_registry():
    from app.commands.registry import command_registry
    from app.game_engine.agent_runtime.tooling import RegistryToolExecutor

    session = MagicMock()
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        db_session=session,
    )

    def fake_get_policy(name):
        if name == "help":
            return _policy(any_perms=[])
        return _policy(any_perms=["admin.blocked"])

    with patch.object(CommandPolicyRepository, "get_policy", side_effect=fake_get_policy):
        expected = sorted(c.name for c in command_registry.get_available_commands(ctx))
        ex = RegistryToolExecutor()
        got = ex.list_tool_ids(ctx)

    assert got == expected
    assert "help" in got


def test_list_tool_ids_applies_allowlist_after_policy():
    from app.game_engine.agent_runtime.tooling import RegistryToolExecutor

    session = MagicMock()
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        db_session=session,
    )

    def fake_get_policy(name):
        if name == "help":
            return _policy(any_perms=[])
        return _policy(any_perms=["admin.blocked"])

    with patch.object(CommandPolicyRepository, "get_policy", side_effect=fake_get_policy):
        ex = RegistryToolExecutor()
        got = ex.list_tool_ids(ctx, allowlist=["help", "missing"])

    assert got == ["help"]
