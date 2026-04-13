import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.init_commands import initialize_commands
from app.commands.invoke import invoke_command_line
from app.commands.policy_store import CommandPolicyRepository

def _policy(*, enabled=True, any_perms=None, all_perms=None, roles_any=None):
    m = MagicMock()
    m.enabled = enabled
    m.required_permissions_any = list(any_perms or [])
    m.required_permissions_all = list(all_perms or [])
    m.required_roles_any = list(roles_any or [])
    return m


def test_npc_gateway_denies_without_policy_match(monkeypatch):
    assert initialize_commands(force_reinit=True)

    # Deny `notice` to normal npc
    with patch.object(CommandPolicyRepository, "get_policy", return_value=_policy(any_perms=["admin.system_notice"])):
        res = invoke_command_line(
            actor_id="npc1",
            actor_name="npc",
            permissions=["player"],
            command_line="notice list",
            game_state={"is_running": True, "current_game": "campus_life", "game_info": {}},
        )
    assert not res.success
    assert "Permission denied" in res.message


def test_npc_gateway_allows_help_by_default(monkeypatch):
    assert initialize_commands(force_reinit=True)

    # Empty policy => allow.
    with patch.object(CommandPolicyRepository, "get_policy", return_value=_policy(any_perms=[])):
        res = invoke_command_line(
            actor_id="npc1",
            actor_name="npc",
            permissions=[],
            command_line="help",
            game_state={},
        )
    assert res.success
    assert "Available commands" in res.message


def test_npc_gateway_allows_world_list_with_admin_world_permission(monkeypatch):
    assert initialize_commands(force_reinit=True)

    with patch.object(CommandPolicyRepository, "get_policy", return_value=_policy(any_perms=["admin.world.*"])):
        with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
            with patch("app.commands.game.world_command.game_engine_manager.get_engine", return_value=None):
                res = invoke_command_line(
                    actor_id="npc1",
                    actor_name="npc_admin",
                    permissions=["admin.world.*"],
                    command_line="world list",
                    game_state={"is_running": True, "current_game": "campus_life", "game_info": {}},
                )
    assert res.success
    assert "hicampus" in res.message
    assert "world_id" in res.message

