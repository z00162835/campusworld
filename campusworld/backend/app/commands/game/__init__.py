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

# 场景命令列表
GAME_COMMANDS = [
    LookCommand(),
    EnterWorldCommand(),
    LeaveWorldCommand(),
    *build_direction_commands(),
    NoticeCommand(),
    WorldCommand(),
    *TASK_COMMANDS,
]

__all__ = [
    'LookCommand',
    'EnterWorldCommand',
    'LeaveWorldCommand',
    'NoticeCommand',
    'WorldCommand',
    'TaskCommand',
    'GAME_COMMANDS',
]
