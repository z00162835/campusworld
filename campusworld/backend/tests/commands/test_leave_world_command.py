import sys
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import CommandContext
from app.commands.game.leave_world_command import LeaveWorldCommand


def _ctx() -> CommandContext:
    return CommandContext(
        user_id="1",
        username="tester",
        session_id="s1",
        permissions=["game.campus_life"],
        game_state={"is_running": True, "current_game": "campus_life", "game_info": {}},
    )


def test_leave_world_rejects_extra_args():
    cmd = LeaveWorldCommand()
    out = cmd.execute(_ctx(), ["x"])
    assert not out.success


@patch("app.ssh.game_handler.game_handler")
def test_leave_world_success(mock_gh):
    mock_gh.leave_world.return_value = {"success": True, "message": "已离开世界，回到奇点屋"}
    cmd = LeaveWorldCommand()
    out = cmd.execute(_ctx(), [])
    assert out.success
    assert "奇点屋" in out.message
    mock_gh.leave_world.assert_called_once_with(user_id="1", username="tester")


@patch("app.ssh.game_handler.game_handler")
def test_leave_world_propagates_failure(mock_gh):
    mock_gh.leave_world.return_value = {"success": False, "message": "你当前已在奇点屋"}
    cmd = LeaveWorldCommand()
    out = cmd.execute(_ctx(), [])
    assert not out.success
    assert "奇点屋" in out.message
