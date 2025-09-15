"""
园区世界包 - 统一接口

提供与单文件版本兼容的接口，内部使用模块化实现
"""

from .game import Game as CampusLifeGame
from .commands import CampusLifeCommands
from .objects import CampusLifeObjects
from .scripts import CampusLifeScripts

# 创建场景实例
campus_life_game = CampusLifeGame()

# 提供兼容接口
def initialize_game() -> bool:
    """初始化场景 - 兼容接口"""
    return campus_life_game.start()

def start_game() -> bool:
    """启动场景 - 兼容接口"""
    return campus_life_game.start()

def stop_game() -> bool:
    """停止场景 - 兼容接口"""
    return campus_life_game.stop()

def cleanup_game():
    """清理场景 - 兼容接口"""
    campus_life_game.stop()

def get_game_instance():
    """获取场景实例 - 兼容接口"""
    return campus_life_game

# 导出所有接口
__all__ = [
    'CampusLifeGame',
    'campus_life_game',
    'initialize_game',
    'start_game', 
    'stop_game',
    'cleanup_game',
    'get_game_instance'
]
