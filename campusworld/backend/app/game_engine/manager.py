"""
引擎管理器 - 整合所有内容引擎组件

提供统一的内容引擎管理接口，包括：
- 引擎生命周期管理
- 内容加载和管理
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
    """CampusWorld内容引擎 - 继承自GameEngine基类"""
    
    def __init__(self):
        super().__init__("CampusWorld", "1.0.0")
        
        # 初始化组件
        self.loader = GameLoader(self)
        self.interface = GameInterface(self)
        
        self.logger.info("CampusWorld内容引擎初始化完成")
    
    def start(self) -> bool:
        """启动内容引擎"""
        try:
            if not super().start():
                return False
            
            # 自动加载内容
            loaded_games = self.loader.auto_load_games()
            if loaded_games:
                self.logger.info(f"自动加载了 {len(loaded_games)} 个内容: {loaded_games}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"启动内容引擎失败: {e}")
            return False
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取内容引擎详细信息"""
        info = super().get_status()
        info.update({
            "loader_status": "running" if self.loader else "stopped",
            "interface_status": "running" if self.interface else "stopped",
            "available_games": self.loader.discover_games() if self.loader else [],
            "loaded_games": self.loader.get_loaded_games() if self.loader else []
        })
        return info


class GameEngineManager:
    """内容引擎管理器 - 单例模式"""
    
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
            self.logger.info("内容引擎管理器初始化完成")
    
    def initialize_engine(self) -> bool:
        """初始化内容引擎"""
        try:
            if self.engine:
                self.logger.warning("内容引擎已存在")
                return True
            
            self.engine = CampusWorldGameEngine()
            self.logger.info("内容引擎初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化内容引擎失败: {e}")
            return False
    
    def start_engine(self) -> bool:
        """启动内容引擎"""
        try:
            if not self.engine:
                if not self.initialize_engine():
                    return False
            
            if self.engine.start():
                self.logger.info("内容引擎启动成功")
                return True
            else:
                self.logger.error("内容引擎启动失败")
                return False
                
        except Exception as e:
            self.logger.error(f"启动内容引擎失败: {e}")
            return False
    
    def stop_engine(self) -> bool:
        """停止内容引擎"""
        try:
            if not self.engine:
                self.logger.warning("内容引擎不存在")
                return True
            
            if self.engine.stop():
                self.logger.info("内容引擎停止成功")
                return True
            else:
                self.logger.error("内容引擎停止失败")
                return False
                
        except Exception as e:
            self.logger.error(f"停止内容引擎失败: {e}")
            return False
    
    def get_engine(self) -> Optional[CampusWorldGameEngine]:
        """获取内容引擎实例"""
        return self.engine
    
    def get_engine_status(self) -> Dict[str, Any]:
        """获取内容引擎状态"""
        if not self.engine:
            return {"status": "not_initialized"}
        
        return self.engine.get_engine_info()
    
    def load_game(self, game_name: str) -> Optional[Any]:
        """加载内容"""
        try:
            if not self.engine:
                self.logger.error("内容引擎未初始化")
                return None
            
            return self.engine.loader.load_game(game_name)
            
        except Exception as e:
            self.logger.error(f"加载内容 '{game_name}' 失败: {e}")
            return None
    
    def unload_game(self, game_name: str) -> bool:
        """卸载内容"""
        try:
            if not self.engine:
                self.logger.error("内容引擎未初始化")
                return False
            
            return self.engine.loader.unload_game(game_name)
            
        except Exception as e:
            self.logger.error(f"卸载内容 '{game_name}' 失败: {e}")
            return False
    
    def reload_game(self, game_name: str) -> Optional[Any]:
        """重新加载内容"""
        try:
            if not self.engine:
                self.logger.error("内容引擎未初始化")
                return None
            
            return self.engine.loader.reload_game(game_name)
            
        except Exception as e:
            self.logger.error(f"重新加载内容 '{game_name}' 失败: {e}")
            return None
    
    def list_games(self) -> List[str]:
        """列出所有内容"""
        try:
            if not self.engine:
                return []
            
            return self.engine.loader.discover_games()
            
        except Exception as e:
            self.logger.error(f"列出内容失败: {e}")
            return []
    
    def get_game_status(self, game_name: str) -> Optional[Dict[str, Any]]:
        """获取内容状态"""
        try:
            if not self.engine:
                return None
            
            return self.engine.interface.get_game_status(game_name)
            
        except Exception as e:
            self.logger.error(f"获取内容 '{game_name}' 状态失败: {e}")
            return None
    
    def execute_game_command(self, game_name: str, command: str, *args, **kwargs) -> Any:
        """执行内容命令"""
        try:
            if not self.engine:
                self.logger.error("内容引擎未初始化")
                return None
            
            return self.engine.interface.execute_game_command(game_name, command, *args, **kwargs)
            
        except Exception as e:
            self.logger.error(f"执行内容 '{game_name}' 命令 '{command}' 失败: {e}")
            return None


# 全局内容引擎管理器实例
game_engine_manager = GameEngineManager()
