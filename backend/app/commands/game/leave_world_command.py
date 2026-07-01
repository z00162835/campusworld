"""
Leave world command — return account to singularity room (Evennia-like).
"""
from typing import List
from ..base import GameCommand, CommandContext, CommandResult
from app.commands.command_tool_semantics import CommandToolSemantics, build_error_schema

class LeaveWorldCommand(GameCommand):

    tool_semantics = CommandToolSemantics(
        interaction_profile='mutate',
        invocation_guard={
            'requires_confirmation': False,
            'allowed_intents': ['execute'],
            'side_effect_scope': 'state_change',
        },
        side_effect_level='write_low',
        idempotent=False,
        deterministic=True,
        data_classification='internal',
        data_scope=('world', 'character'),
        error_schema=build_error_schema(('NOT_AVAILABLE', 'POLICY_DENIED')),
    )

    def __init__(self):
        super().__init__(name='leave', description='离开当前世界，回到奇点屋', aliases=['ooc'], game_name='')

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if args:
            return CommandResult.error_result('用法: leave')
        from app.ssh.game_handler import game_handler
        result = game_handler.leave_world(user_id=context.user_id, username=context.username)
        if not result.get('success'):
            return CommandResult.error_result(str(result.get('message') or '离开世界失败'))
        return CommandResult.success_result(str(result.get('message') or '已离开世界'))

    def get_usage(self) -> str:
        return 'leave  # 回到奇点屋（需先离开世界才能从奇点屋 enter 其他世界）'
