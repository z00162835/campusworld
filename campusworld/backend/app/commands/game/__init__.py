"""
场景命令模块

包含所有场景相关的命令实现
"""

from .look_command import LookCommand

# 场景命令列表
GAME_COMMANDS = [
    LookCommand(),
]

__all__ = ['LookCommand', 'GAME_COMMANDS']
