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
    assert result.message in {"用户不存在", "你当前不在世界内"}


def test_enter_world_command_accepts_hicampus():
    from app.commands.game.enter_world_command import EnterWorldCommand
    from app.ssh.game_handler import game_handler
    from app.game_engine.world_entry_service import world_entry_service, WorldEntryDecision

    # Mock game_handler.enter_world
    original_enter_world = game_handler.enter_world
    original_build = world_entry_service.build_entry_request
    game_handler.enter_world = lambda **kwargs: {"success": True, "message": "已进入世界 hicampus"}
    world_entry_service.build_entry_request = lambda *_args, **_kwargs: WorldEntryDecision(
        ok=True, world_id="hicampus", spawn_key="hicampus_gate"
    )

    try:
        cmd = EnterWorldCommand()
        result = cmd.execute(_build_context(), ["hicampus"])

        assert result.success
        assert "hicampus" in result.message
    finally:
        # Restore original
        game_handler.enter_world = original_enter_world
        world_entry_service.build_entry_request = original_build


def test_enter_world_command_rejects_when_entry_missing():
    from app.commands.game.enter_world_command import EnterWorldCommand
    from app.game_engine.world_entry_service import world_entry_service, WorldEntryDecision

    original_build = world_entry_service.build_entry_request
    world_entry_service.build_entry_request = lambda *_args, **_kwargs: WorldEntryDecision(
        ok=False,
        world_id="hicampus",
        spawn_key="",
        error_code="WORLD_ENTRY_PORTAL_MISSING",
        message="奇点屋中未找到世界入口: hicampus",
    )
    try:
        cmd = EnterWorldCommand()
        result = cmd.execute(_build_context(), ["hicampus"])
        assert not result.success
        assert result.error == "WORLD_ENTRY_PORTAL_MISSING"
    finally:
        world_entry_service.build_entry_request = original_build


def test_enter_world_command_maps_game_unavailable_error():
    from app.commands.game.enter_world_command import EnterWorldCommand
    from app.ssh.game_handler import game_handler
    from app.game_engine.world_entry_service import world_entry_service, WorldEntryDecision

    original_build = world_entry_service.build_entry_request
    original_enter = game_handler.enter_world
    world_entry_service.build_entry_request = lambda *_args, **_kwargs: WorldEntryDecision(
        ok=True, world_id="hicampus", spawn_key="hicampus_gate"
    )
    game_handler.enter_world = lambda **_kwargs: {"success": False, "message": "世界未加载: hicampus"}
    try:
        cmd = EnterWorldCommand()
        result = cmd.execute(_build_context(), ["hicampus"])
        assert not result.success
        assert result.error == "WORLD_ENTRY_GAME_UNAVAILABLE"
    finally:
        world_entry_service.build_entry_request = original_build
        game_handler.enter_world = original_enter


def test_enter_world_command_rejects_forbidden_from_authorize():
    from app.commands.game.enter_world_command import EnterWorldCommand
    from app.game_engine.world_entry_service import world_entry_service, WorldEntryDecision

    original_build = world_entry_service.build_entry_request
    original_auth = world_entry_service.authorize_entry
    world_entry_service.build_entry_request = lambda *_args, **_kwargs: WorldEntryDecision(
        ok=True, world_id="hicampus", spawn_key="hicampus_gate"
    )
    world_entry_service.authorize_entry = lambda *_args, **_kwargs: WorldEntryDecision(
        ok=False,
        world_id="hicampus",
        spawn_key="hicampus_gate",
        error_code="WORLD_ENTRY_FORBIDDEN",
        message="当前用户无权限进入世界: hicampus",
    )
    try:
        cmd = EnterWorldCommand()
        result = cmd.execute(_build_context(), ["hicampus"])
        assert not result.success
        assert result.error == "WORLD_ENTRY_FORBIDDEN"
    finally:
        world_entry_service.build_entry_request = original_build
        world_entry_service.authorize_entry = original_auth


def test_enter_world_usage_mentions_direction_semantics():
    from app.commands.game.enter_world_command import EnterWorldCommand

    usage = EnterWorldCommand().get_usage()
    assert "无参数时在世界内按方向 enter 移动" in usage
