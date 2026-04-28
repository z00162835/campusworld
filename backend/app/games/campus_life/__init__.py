"""
园区世界包 - 统一接口

提供与单文件版本兼容的接口，内部使用模块化实现。
采用工厂模式，由 loader 通过 get_game_instance() 统一创建实例，
避免模块级单例在 import 时触发副作用。
"""

from .game import Game as CampusLifeGame
from .commands import CampusLifeCommands
from .objects import CampusLifeObjects
from .scripts import CampusLifeScripts


def get_game_instance():
    """获取场景实例 - 工厂函数，每次返回新实例

    由 loader.load_game() 调用，创建后由 loader 负责初始化和启动。
    """
    return CampusLifeGame()


def initialize_game() -> bool:
    """初始化场景 - 兼容接口

    直接委托给实例的 initialize_game()。
    注意：实际初始化由 loader.load_game() 统一调用。
    """
    instance = get_game_instance()
    return instance.initialize_game()


def start_game() -> bool:
    """启动场景 - 兼容接口"""
    instance = get_game_instance()
    return instance.start()


def stop_game() -> bool:
    """停止场景 - 兼容接口"""
    instance = get_game_instance()
    return instance.stop()


def cleanup_game():
    """清理场景 - 兼容接口"""
    instance = get_game_instance()
    instance.stop()


# 导出所有接口
__all__ = [
    'CampusLifeGame',
    'initialize_game',
    'start_game',
    'stop_game',
    'cleanup_game',
    'get_game_instance'
]
