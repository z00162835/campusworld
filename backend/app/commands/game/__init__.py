"""
场景命令模块

包含所有场景相关的命令实现
"""
from .look_command import LookCommand
from .enter_world_command import EnterWorldCommand
from .leave_world_command import LeaveWorldCommand
from .direction_command import build_direction_commands
from .notice_command import NoticeCommand
from .world_command import WorldCommand
from .task import TASK_COMMANDS, TaskCommand
from app.commands.lexicon_command import LEXICON_COMMAND
GAME_COMMANDS = [LookCommand(), EnterWorldCommand(), LeaveWorldCommand(), *build_direction_commands(), NoticeCommand(), WorldCommand(), LEXICON_COMMAND, *TASK_COMMANDS]
__all__ = ['LookCommand', 'EnterWorldCommand', 'LeaveWorldCommand', 'NoticeCommand', 'WorldCommand', 'TaskCommand', 'GAME_COMMANDS']
