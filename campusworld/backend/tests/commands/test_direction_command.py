import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import CommandContext
from app.commands.game.direction_command import (
    MovementCommand,
    FixedDirectionCommand,
    build_direction_commands,
    normalize_direction,
)


def _ctx() -> CommandContext:
    return CommandContext(
        user_id="1",
        username="tester",
        session_id="s1",
        permissions=["game.campus_life"],
        game_state={},
    )


def test_fixed_direction_command_returns_error_when_move_fails():
    cmd = FixedDirectionCommand(name="north", description="向北移动", aliases=["n"], direction="north")
    cmd._move = lambda _uid, _direction: (False, "无法向north移动", None)
    out = cmd.execute(_ctx(), [])
    assert not out.success
    assert "无法向north移动" in out.message


def test_move_returns_world_bridge_disabled_error_code():
    cmd = FixedDirectionCommand(name="north", description="向北移动", aliases=["n"], direction="north")
    cmd._move = lambda _uid, _direction: (False, "该方向的跨世界桥接已关闭", "WORLD_BRIDGE_DISABLED")
    out = cmd.execute(_ctx(), [])
    assert not out.success
    assert out.error == "WORLD_BRIDGE_DISABLED"


def test_fixed_direction_command_returns_success_when_move_succeeds():
    cmd = FixedDirectionCommand(name="north", description="向北移动", aliases=["n"], direction="north")
    cmd._move = lambda _uid, _direction: (True, "你向北移动，来到 HiCampus Bridge", None)
    out = cmd.execute(_ctx(), [])
    assert out.success
    assert "Bridge" in out.message


def test_movement_command_supports_go_with_compound_alias():
    cmd = MovementCommand()
    cmd._move = lambda _uid, direction: (True, f"moved:{direction}", None)
    out = cmd.execute(_ctx(), ["sw"])
    assert out.success
    assert "southwest" in out.message


def test_direction_normalization_supports_vertical_and_enter_out():
    assert normalize_direction("u") == "up"
    assert normalize_direction("d") == "down"
    assert normalize_direction("in") == "enter"
    assert normalize_direction("o") == "out"


def test_direction_normalization_keeps_custom_direction():
    assert normalize_direction("lab") == "lab"


def test_movement_and_fixed_direction_are_distinct_command_classes():
    cmds = build_direction_commands()
    by_name = {c.name: c for c in cmds}
    assert "go" in by_name
    assert "north" in by_name
    assert "n" not in by_name["go"].aliases
    assert "walk" in by_name["go"].aliases
    assert "n" in by_name["north"].aliases


def _session_cm(session: MagicMock):
    cm = MagicMock()
    cm.__enter__.return_value = session
    cm.__exit__.return_value = None
    return cm


def test_move_does_not_use_cross_world_edge_without_bridge_id():
    """Topology treats cross_world_bridge without bridge_id as unauthorized; movement must match."""
    cmd = MovementCommand()
    user = MagicMock()
    user.attributes = {"active_world": "w1", "world_location": "ra"}
    room = MagicMock()
    room.id = 10
    room.attributes = {"world_id": "w1", "package_node_id": "ra"}
    dest = MagicMock()
    dest.attributes = {"world_id": "w2", "package_node_id": "rb", "display_name": "Far"}
    rel = MagicMock()
    rel.attributes = {"cross_world_bridge": True, "direction": "north"}

    n = {"i": 0}

    def query_fn(*_a, **_k):
        n["i"] += 1
        m = MagicMock()
        if n["i"] == 1:
            m.filter.return_value.first.return_value = user
        elif n["i"] == 2:
            m.filter.return_value.first.return_value = room
        elif n["i"] == 3:
            m.join.return_value.filter.return_value.all.return_value = []
        elif n["i"] == 4:
            m.join.return_value.filter.return_value.all.return_value = [(rel, dest)]
        return m

    session = MagicMock()
    session.query.side_effect = query_fn
    session.add = MagicMock()
    session.commit = MagicMock()

    with patch("app.commands.game.direction_command.db_session_context", return_value=_session_cm(session)):
        ok, msg, err = cmd._move("1", "north")
    assert ok is False
    assert err is None
    assert "该方向目标不可达" in msg


def test_move_uses_authorized_bridge_to_change_world():
    cmd = MovementCommand()
    user = MagicMock()
    user.attributes = {"active_world": "w1", "world_location": "ra"}
    room = MagicMock()
    room.id = 10
    room.attributes = {"world_id": "w1", "package_node_id": "ra"}
    dest = MagicMock()
    dest.attributes = {"world_id": "w2", "package_node_id": "rb", "display_name": "RoomB"}
    dest.name = "RoomB"
    rel = MagicMock()
    rel.attributes = {"cross_world_bridge": True, "bridge_id": "b-1", "direction": "north", "enabled": True}

    n = {"i": 0}

    def query_fn(*_a, **_k):
        n["i"] += 1
        m = MagicMock()
        if n["i"] == 1:
            m.filter.return_value.first.return_value = user
        elif n["i"] == 2:
            m.filter.return_value.first.return_value = room
        elif n["i"] == 3:
            m.join.return_value.filter.return_value.all.return_value = []
        elif n["i"] == 4:
            m.join.return_value.filter.return_value.all.return_value = [(rel, dest)]
        return m

    session = MagicMock()
    session.query.side_effect = query_fn
    session.add = MagicMock()
    session.commit = MagicMock()

    with patch("app.commands.game.direction_command.db_session_context", return_value=_session_cm(session)):
        ok, msg, err = cmd._move("1", "north")
    assert ok is True
    assert err is None
    assert "跨世界" in msg
    assert "w2" in msg
    assert user.attributes.get("active_world") == "w2"
    assert user.attributes.get("world_location") == "rb"
    session.commit.assert_called_once()


def test_move_bridge_disabled_returns_error_code():
    cmd = MovementCommand()
    user = MagicMock()
    user.attributes = {"active_world": "w1", "world_location": "ra"}
    room = MagicMock()
    room.id = 10
    room.attributes = {"world_id": "w1", "package_node_id": "ra"}
    dest = MagicMock()
    dest.attributes = {"world_id": "w2", "package_node_id": "rb"}
    rel = MagicMock()
    rel.attributes = {
        "cross_world_bridge": True,
        "bridge_id": "b-2",
        "direction": "north",
        "enabled": False,
    }

    n = {"i": 0}

    def query_fn(*_a, **_k):
        n["i"] += 1
        m = MagicMock()
        if n["i"] == 1:
            m.filter.return_value.first.return_value = user
        elif n["i"] == 2:
            m.filter.return_value.first.return_value = room
        elif n["i"] == 3:
            m.join.return_value.filter.return_value.all.return_value = []
        elif n["i"] == 4:
            m.join.return_value.filter.return_value.all.return_value = [(rel, dest)]
        return m

    session = MagicMock()
    session.query.side_effect = query_fn
    session.add = MagicMock()
    session.commit = MagicMock()

    with patch("app.commands.game.direction_command.db_session_context", return_value=_session_cm(session)):
        ok, msg, err = cmd._move("1", "north")
    assert ok is False
    assert err == "WORLD_BRIDGE_DISABLED"
    session.commit.assert_not_called()


def test_move_prefers_local_exit_over_cross_world_bridge():
    """Same direction: local connects_to wins; fourth query (bridge scan) is not executed."""
    cmd = MovementCommand()
    user = MagicMock()
    user.attributes = {"active_world": "w1", "world_location": "ra"}
    room = MagicMock()
    room.id = 10
    room.attributes = {"world_id": "w1", "package_node_id": "ra"}
    local_dest = MagicMock()
    local_dest.attributes = {
        "world_id": "w1",
        "package_node_id": "near",
        "display_name": "NearRoom",
    }
    local_dest.name = "NearRoom"
    rel_local = MagicMock()
    rel_local.attributes = {"direction": "north"}

    n = {"i": 0}

    def query_fn(*_a, **_k):
        n["i"] += 1
        m = MagicMock()
        if n["i"] == 1:
            m.filter.return_value.first.return_value = user
        elif n["i"] == 2:
            m.filter.return_value.first.return_value = room
        elif n["i"] == 3:
            m.join.return_value.filter.return_value.all.return_value = [(rel_local, local_dest)]
        else:
            raise AssertionError(f"unexpected session.query call index {n['i']}")
        return m

    session = MagicMock()
    session.query.side_effect = query_fn
    session.add = MagicMock()
    session.commit = MagicMock()

    with patch("app.commands.game.direction_command.db_session_context", return_value=_session_cm(session)):
        ok, msg, err = cmd._move("1", "north")
    assert ok is True
    assert err is None
    assert n["i"] == 3
    assert user.attributes.get("active_world") == "w1"
    assert user.attributes.get("world_location") == "near"

