import sys
from pathlib import Path

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
    cmd._move = lambda _uid, _direction: (False, "无法向north移动")
    out = cmd.execute(_ctx(), [])
    assert not out.success
    assert "无法向north移动" in out.message


def test_fixed_direction_command_returns_success_when_move_succeeds():
    cmd = FixedDirectionCommand(name="north", description="向北移动", aliases=["n"], direction="north")
    cmd._move = lambda _uid, _direction: (True, "你向北移动，来到 HiCampus Bridge")
    out = cmd.execute(_ctx(), [])
    assert out.success
    assert "Bridge" in out.message


def test_movement_command_supports_go_with_compound_alias():
    cmd = MovementCommand()
    cmd._move = lambda _uid, direction: (True, f"moved:{direction}")
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

