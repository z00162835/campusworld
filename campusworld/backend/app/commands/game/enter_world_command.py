"""
Enter world command.
"""

from typing import List

from ..base import GameCommand, CommandContext, CommandResult
from app.ssh.game_handler import game_handler


class EnterWorldCommand(GameCommand):
    def __init__(self):
        super().__init__(
            name="enter",
            description="从奇点屋进入指定世界",
            aliases=["world", "enterworld"],
            game_name="campus_life",
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: enter <world_name> [spawn_key]")

        world_name = args[0].strip().lower()
        spawn_key = args[1].strip().lower() if len(args) > 1 else "campus"
        if not world_name:
            return CommandResult.error_result("世界名不能为空")

        result = game_handler.enter_world(
            user_id=context.user_id,
            username=context.username,
            world_name=world_name,
            spawn_key=spawn_key,
        )
        if not result.get("success"):
            return CommandResult.error_result(result.get("message", "进入世界失败"))
        return CommandResult.success_result(result.get("message", f"已进入世界 {world_name}"))

    def get_usage(self) -> str:
        return "enter <world_name> [spawn_key]"

