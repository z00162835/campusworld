"""LookCommand resolves current room via location_id (Evennia-like) when set."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import CommandContext
from app.commands.game.look_command import LookCommand


def _ctx() -> CommandContext:
    return CommandContext(
        user_id="42",
        username="u1",
        session_id="s1",
        permissions=["game.campus_life"],
        game_state={"is_running": True, "current_game": "campus_life", "game_info": {}},
    )


def _session_cm(session: MagicMock):
    cm = MagicMock()
    cm.__enter__.return_value = session
    cm.__exit__.return_value = None
    return cm


def test_get_user_current_room_ref_prefers_location_id_room():
    cmd = LookCommand()
    user = MagicMock()
    user.location_id = 777
    user.attributes = {"active_world": "hicampus", "world_location": "hicampus_plaza"}
    room_node = MagicMock()
    room_node.type_code = "room"
    room_node.id = 777

    session = MagicMock()
    calls = {"n": 0}

    def query_side_effect(*_a, **_k):
        calls["n"] += 1
        m = MagicMock()
        if calls["n"] == 1:
            m.filter.return_value.first.return_value = user
        elif calls["n"] == 2:
            m.filter.return_value.first.return_value = room_node
        return m

    session.query.side_effect = query_side_effect

    with patch("app.core.database.db_session_context", return_value=_session_cm(session)):
        ref = cmd._get_user_current_room_ref(_ctx())

    assert ref == {"scope": "system", "room_id": "777"}
