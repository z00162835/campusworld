"""
Enter world command.
"""
from typing import List
from ..base import GameCommand, CommandContext, CommandResult
from app.commands.command_tool_semantics import CommandToolSemantics, build_error_schema
from app.game_engine.world_entry_service import world_entry_service
from .direction_command import FixedDirectionCommand

class EnterWorldCommand(GameCommand):

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
        data_scope=('world', 'world_entrance'),
        error_schema=build_error_schema(('NOT_FOUND', 'NOT_AVAILABLE', 'PERMISSION_DENIED', 'POLICY_DENIED')),
    )

    def __init__(self):
        super().__init__(name='enter', description='进入指定世界（通用命令）', aliases=[], game_name='')

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return FixedDirectionCommand(name='enter', description='进入方向', aliases=[], direction='enter').execute(context, [])
        world_name = args[0].strip().lower()
        spawn_key = args[1].strip().lower() if len(args) > 1 else ''
        if not world_name:
            return CommandResult.error_result('世界名不能为空')
        decision = world_entry_service.build_entry_request(world_name, spawn_key or None)
        decision = world_entry_service.authorize_entry(decision, user=context)
        if not decision.ok:
            return CommandResult.error_result(decision.message or '进入世界失败', error=decision.error_code)
        from app.ssh.game_handler import game_handler
        result = game_handler.enter_world(user_id=context.user_id, username=context.username, world_name=decision.world_id, spawn_key=decision.spawn_key)
        if not result.get('success'):
            msg = str(result.get('message', '进入世界失败'))
            lowered = msg.lower()
            if '未加载' in msg or 'unavailable' in lowered:
                return CommandResult.error_result(msg, error='WORLD_ENTRY_GAME_UNAVAILABLE')
            if '权限' in msg or 'forbidden' in lowered or '无权' in msg:
                return CommandResult.error_result(msg, error='WORLD_ENTRY_FORBIDDEN')
            return CommandResult.error_result(msg, error='WORLD_ENTRY_FAILED')
        return CommandResult.success_result(result.get('message', f'已进入世界 {world_name}'))

    def get_usage(self) -> str:
        return 'enter <world_name> [spawn_key]  # 世界入口；无参数时在世界内按方向 enter 移动'

    def _get_specific_help(self) -> str:
        return '\n说明:\n  - enter <world_name> [spawn_key]: 从奇点屋进入指定世界（须先 leave 离开世界）\n  - enter（无参数）: 仅在世界内作为方向命令使用（等价于 in/enter 方向）\n'
