"""
游戏命令模块

包含所有游戏相关的命令实现
"""

from .look_command import LookCommand

# 游戏命令列表
GAME_COMMANDS = [
    LookCommand(),
]

__all__ = ['LookCommand', 'GAME_COMMANDS']
