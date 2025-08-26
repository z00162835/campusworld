"""
游戏引擎管理器 - 整合所有游戏引擎组件

提供统一的游戏引擎管理接口，包括：
- 引擎生命周期管理
- 游戏加载和管理
- SSH系统集成
- 配置管理
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .base import GameEngine
from .loader import GameLoader
from .interface import GameInterface


class CampusWorldGameEngine(GameEngine):
    """CampusWorld游戏引擎 - 继承自GameEngine基类"""
    
    def __init__(self):
        super().__init__("CampusWorld", "1.0.0")
        
        # 初始化组件
        self.loader = GameLoader(self)
        self.interface = GameInterface(self)
        
        self.logger.info("CampusWorld游戏引擎初始化完成")
    
    def start(self) -> bool:
        """启动游戏引擎"""
        try:
            if not super().start():
                return False
            
            # 自动加载游戏
            loaded_games = self.loader.auto_load_games()
            if loaded_games:
                self.logger.info(f"自动加载了 {len(loaded_games)} 个游戏: {loaded_games}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"启动游戏引擎失败: {e}")
            return False
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取引擎详细信息"""
        info = super().get_status()
        info.update({
            "loader_status": "running" if self.loader else "stopped",
            "interface_status": "running" if self.interface else "stopped",
            "available_games": self.loader.discover_games() if self.loader else [],
            "loaded_games": self.loader.get_loaded_games() if self.loader else []
        })
        return info


class GameEngineManager:
    """游戏引擎管理器 - 单例模式"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.engine = None
            self.logger = logging.getLogger("game_engine.manager")
            self.initialized = True
            self.logger.info("游戏引擎管理器初始化完成")
    
    def initialize_engine(self) -> bool:
        """初始化游戏引擎"""
        try:
            if self.engine:
                self.logger.warning("游戏引擎已存在")
                return True
            
            self.engine = CampusWorldGameEngine()
            self.logger.info("游戏引擎初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化游戏引擎失败: {e}")
            return False
    
    def start_engine(self) -> bool:
        """启动游戏引擎"""
        try:
            if not self.engine:
                if not self.initialize_engine():
                    return False
            
            if self.engine.start():
                self.logger.info("游戏引擎启动成功")
                return True
            else:
                self.logger.error("游戏引擎启动失败")
                return False
                
        except Exception as e:
            self.logger.error(f"启动游戏引擎失败: {e}")
            return False
    
    def stop_engine(self) -> bool:
        """停止游戏引擎"""
        try:
            if not self.engine:
                self.logger.warning("游戏引擎不存在")
                return True
            
            if self.engine.stop():
                self.logger.info("游戏引擎停止成功")
                return True
            else:
                self.logger.error("游戏引擎停止失败")
                return False
                
        except Exception as e:
            self.logger.error(f"停止游戏引擎失败: {e}")
            return False
    
    def get_engine(self) -> Optional[CampusWorldGameEngine]:
        """获取游戏引擎实例"""
        return self.engine
    
    def get_engine_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        if not self.engine:
            return {"status": "not_initialized"}
        
        return self.engine.get_engine_info()
    
    def load_game(self, game_name: str) -> Optional[Any]:
        """加载游戏"""
        try:
            if not self.engine:
                self.logger.error("游戏引擎未初始化")
                return None
            
            return self.engine.loader.load_game(game_name)
            
        except Exception as e:
            self.logger.error(f"加载游戏 '{game_name}' 失败: {e}")
            return None
    
    def unload_game(self, game_name: str) -> bool:
        """卸载游戏"""
        try:
            if not self.engine:
                self.logger.error("游戏引擎未初始化")
                return False
            
            return self.engine.loader.unload_game(game_name)
            
        except Exception as e:
            self.logger.error(f"卸载游戏 '{game_name}' 失败: {e}")
            return False
    
    def reload_game(self, game_name: str) -> Optional[Any]:
        """重新加载游戏"""
        try:
            if not self.engine:
                self.logger.error("游戏引擎未初始化")
                return None
            
            return self.engine.loader.reload_game(game_name)
            
        except Exception as e:
            self.logger.error(f"重新加载游戏 '{game_name}' 失败: {e}")
            return None
    
    def list_games(self) -> List[str]:
        """列出所有游戏"""
        try:
            if not self.engine:
                return []
            
            return self.engine.loader.discover_games()
            
        except Exception as e:
            self.logger.error(f"列出游戏失败: {e}")
            return []
    
    def get_game_status(self, game_name: str) -> Optional[Dict[str, Any]]:
        """获取游戏状态"""
        try:
            if not self.engine:
                return None
            
            return self.engine.interface.get_game_status(game_name)
            
        except Exception as e:
            self.logger.error(f"获取游戏 '{game_name}' 状态失败: {e}")
            return None
    
    def execute_game_command(self, game_name: str, command: str, *args, **kwargs) -> Any:
        """执行游戏命令"""
        try:
            if not self.engine:
                self.logger.error("游戏引擎未初始化")
                return None
            
            return self.engine.interface.execute_game_command(game_name, command, *args, **kwargs)
            
        except Exception as e:
            self.logger.error(f"执行游戏 '{game_name}' 命令 '{command}' 失败: {e}")
            return None


# 全局游戏引擎管理器实例
game_engine_manager = GameEngineManager()
