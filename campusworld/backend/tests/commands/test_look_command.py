import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import CommandContext


def _build_context() -> CommandContext:
    return CommandContext(
        user_id="1",
        username="tester",
        session_id="s1",
        permissions=["game.campus_life"],
        game_state={"is_running": True, "current_game": "campus_life", "game_info": {}},
    )


def test_look_command_works_without_running_game():
    from app.commands.game.look_command import LookCommand

    cmd = LookCommand()
    ctx = _build_context()
    ctx.game_state = {"is_running": False}
    cmd._get_current_room = lambda _ctx: {"name": "Singularity", "description": "root", "items": [], "exits": []}
    result = cmd.execute(ctx, [])
    assert result.success
    assert "Singularity" in result.message


def test_look_command_forwards_target_args_to_object_appearance():
    from app.commands.game.look_command import LookCommand

    cmd = LookCommand()
    ctx = _build_context()

    cmd._search_objects = lambda _ctx, _target: [{"id": "b1", "name": "bulletin_board", "type_code": "system_bulletin_board"}]

    captured = {}

    def _fake_build(_ctx, _obj, target_args=None):
        captured["target_args"] = target_args
        return "ok"

    cmd._build_object_description = _fake_build

    result = cmd.execute(ctx, ["bulletin_board", "page", "2"])
    assert result.success
    assert result.message == "ok"
    assert captured["target_args"] == ["page", "2"]


def test_look_command_returns_multiple_match_prompt():
    from app.commands.game.look_command import LookCommand

    cmd = LookCommand()
    ctx = _build_context()
    cmd._search_objects = lambda _ctx, _target: [
        {"id": "1", "name": "board1", "type": "obj"},
        {"id": "2", "name": "board2", "type": "obj"},
    ]

    result = cmd.execute(ctx, ["board"])
    assert result.success
    assert "多个匹配" in result.message


def test_look_command_world_object_shows_enter_hint():
    from app.commands.game.look_command import LookCommand

    cmd = LookCommand()
    ctx = _build_context()
    obj = {
        "name": "hicampus",
        "type_code": "world",
        "attributes": {"world_id": "hicampus", "description": "HiCampus world"},
    }
    out = cmd._build_object_description(ctx, obj)
    assert "HiCampus world" in out
    assert "enter hicampus" in out


def test_look_command_world_prefers_node_description_over_entry_text():
    from app.commands.game.look_command import LookCommand

    cmd = LookCommand()
    ctx = _build_context()
    obj = {
        "name": "hicampus",
        "type_code": "world",
        "description": "WORLD NODE DESC",
        "attributes": {
            "world_id": "hicampus",
            "description": "ATTR DESC",
            "entry_description": "ENTRY DESC",
        },
    }
    out = cmd._build_object_description(ctx, obj)
    assert "WORLD NODE DESC" in out
    assert "ENTRY DESC" not in out

