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


def test_enter_world_command_requires_world_name():
    from app.commands.game.enter_world_command import EnterWorldCommand

    cmd = EnterWorldCommand()
    result = cmd.execute(_build_context(), [])

    assert not result.success
    assert "用法" in result.message


def test_enter_world_command_accepts_campus_life():
    from app.commands.game.enter_world_command import EnterWorldCommand
    from app.commands.game import enter_world_command

    cmd = EnterWorldCommand()
    enter_world_command.game_handler.enter_world = lambda **kwargs: {"success": True, "message": "已进入世界 campus_life"}
    result = cmd.execute(_build_context(), ["campus_life"])

    assert result.success
    assert "campus_life" in result.message
