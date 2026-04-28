"""Visibility for world_entrance (Evennia Exit) in room listings."""

import sys
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import CommandContext
from app.commands.game.look_command import LookCommand


def _ctx() -> CommandContext:
    return CommandContext(
        user_id="1",
        username="admin",
        session_id="s1",
        permissions=["admin.*", "game.campus_life"],
        game_state={"is_running": True, "current_game": "campus_life", "game_info": {}},
    )


def test_world_entrance_visible_with_room_domain():
    cmd = LookCommand()
    node = SimpleNamespace(
        type_code="world_entrance",
        attributes={
            "portal_world_id": "hicampus",
            "presentation_domains": ["room"],
            "entity_kind": "exit",
            "access_locks": {"view": "all()", "interact": "all()"},
        },
    )
    assert cmd._is_visible_in_room(_ctx(), node) is True


def test_world_entrance_portal_disabled_hidden():
    cmd = LookCommand()
    node = SimpleNamespace(
        type_code="world_entrance",
        attributes={
            "portal_world_id": "hicampus",
            "portal_enabled": False,
            "presentation_domains": ["room"],
            "entity_kind": "exit",
            "access_locks": {"view": "all()"},
        },
    )
    assert cmd._is_visible_in_room(_ctx(), node) is False


def test_graph_world_metadata_system_only_not_auto_visible_in_room():
    """Graph-seeded world row (system catalog) is not a singularity exit; may be hidden in room."""
    cmd = LookCommand()
    node = SimpleNamespace(
        type_code="world",
        attributes={
            "world_id": "hicampus",
            "presentation_domains": ["system"],
            "access_locks": {"view": "all()", "interact": "perm(world.enter)"},
        },
    )
    assert cmd._is_visible_in_room(_ctx(), node) is False
