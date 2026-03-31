"""
场景命令模块

包含所有场景相关的命令实现
"""

from .look_command import LookCommand
from .enter_world_command import EnterWorldCommand
from .notice_command import NoticeCommand

# 场景命令列表
GAME_COMMANDS = [
    LookCommand(),
    EnterWorldCommand(),
    NoticeCommand(),
]

__all__ = ['LookCommand', 'EnterWorldCommand', 'NoticeCommand', 'GAME_COMMANDS']
