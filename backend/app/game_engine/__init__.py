"""
CampusWorld 场景引擎包

提供场景与引擎解耦的基础设施，参考Evennia框架设计。
"""

__author__ = "CampusWorld OS Team"

from .base import GameEngine, BaseGame
from .loader import GameLoader
from .interface import GameInterface
from .manager import GameEngineManager, CampusWorldGameEngine, game_engine_manager
from .runtime_store import OperationResult, WorldRuntimeStatus, WorldErrorCode

__all__ = [
    "GameEngine",
    "BaseGame",
    "GameLoader", 
    "GameInterface",
    "GameEngineManager",
    "CampusWorldGameEngine",
    "game_engine_manager",
    "OperationResult",
    "WorldRuntimeStatus",
    "WorldErrorCode",
]
