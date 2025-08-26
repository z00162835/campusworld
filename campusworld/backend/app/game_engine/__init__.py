"""
CampusWorld 游戏引擎包

提供游戏与引擎解耦的基础设施，参考Evennia框架设计。
"""

__version__ = "0.1.0"
__author__ = "CampusWorld Team"

from .base import GameEngine, BaseGame
from .loader import GameLoader
from .interface import GameInterface
from .manager import GameEngineManager, CampusWorldGameEngine, game_engine_manager

__all__ = [
    "GameEngine",
    "BaseGame",
    "GameLoader", 
    "GameInterface",
    "GameEngineManager",
    "CampusWorldGameEngine",
    "game_engine_manager"
]
