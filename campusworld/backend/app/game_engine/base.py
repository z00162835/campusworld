"""
场景引擎基类 - 参考Evennia框架设计

提供场景引擎的核心功能，包括：
- 场景生命周期管理
- 对象系统管理
- 命令系统集成
- 事件钩子系统
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import asyncio
from pathlib import Path
from app.core.log import (
    get_logger, 
    LoggerNames,
)


class GameEngine(ABC):
    """场景引擎基类 - 参考Evennia框架设计"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.logger = get_logger(LoggerNames.GAME)
        
        # 引擎状态
        self.is_running = False
        self.start_time = None
        self.games: Dict[str, 'BaseGame'] = {}
        
        # 核心系统
        self.object_manager = ObjectManager(self)
        self.command_manager = CommandManager(self)
        self.script_manager = ScriptManager(self)
        self.hook_manager = HookManager(self)
        
        self.logger.info(f"场景引擎 '{name}' v{version} 初始化完成")
    
    def start(self) -> bool:
        """启动场景引擎"""
        try:
            if self.is_running:
                self.logger.warning("场景引擎已在运行中")
                return True
            
            self.start_time = datetime.now()
            self.is_running = True
            
            # 启动核心系统
            self.object_manager.start()
            self.command_manager.start()
            self.script_manager.start()
            self.hook_manager.start()
            
            self.logger.info(f"场景引擎 '{self.name}' 启动成功，启动时间: {self.start_time}")
            return True
            
        except Exception as e:
            self.logger.error(f"场景引擎启动失败: {e}")
            return False
    
    def stop(self) -> bool:
        """停止场景引擎"""
        try:
            if not self.is_running:
                self.logger.warning("场景引擎未在运行")
                return True
            
            # 停止所有场景
            for game_name, game in self.games.items():
                try:
                    game.stop()
                    self.logger.info(f"场景 '{game_name}' 已停止")
                except Exception as e:
                    self.logger.error(f"停止场景 '{game_name}' 失败: {e}")
            
            # 停止核心系统
            self.object_manager.stop()
            self.command_manager.stop()
            self.script_manager.stop()
            self.hook_manager.stop()
            
            self.is_running = False
            runtime = datetime.now() - self.start_time if self.start_time else None
            
            self.logger.info(f"场景引擎 '{self.name}' 已停止，运行时间: {runtime}")
            return True
            
        except Exception as e:
            self.logger.error(f"场景引擎停止失败: {e}")
            return False
    
    def register_game(self, game: 'BaseGame') -> bool:
        """注册场景到引擎"""
        try:
            if game.name in self.games:
                self.logger.warning(f"场景 '{game.name}' 已存在，将被覆盖")
            
            self.games[game.name] = game
            game.engine = self
            
            self.logger.info(f"场景 '{game.name}' 注册成功")
            return True
            
        except Exception as e:
            self.logger.error(f"注册场景 '{game.name}' 失败: {e}")
            return False
    
    def unregister_game(self, game_name: str) -> bool:
        """从引擎注销场景"""
        try:
            if game_name not in self.games:
                self.logger.warning(f"场景 '{game_name}' 不存在")
                return True
            
            game = self.games.pop(game_name)
            game.engine = None
            
            self.logger.info(f"场景 '{game_name}' 注销成功")
            return True
            
        except Exception as e:
            self.logger.error(f"注销场景 '{game_name}' 失败: {e}")
            return False
    
    def get_game(self, game_name: str) -> Optional['BaseGame']:
        """获取指定场景"""
        return self.games.get(game_name)
    
    def list_games(self) -> List[str]:
        """列出所有已注册的场景"""
        return list(self.games.keys())
    
    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        return {
            "name": self.name,
            "version": self.version,
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "games_count": len(self.games),
            "games": list(self.games.keys()),
        }


class ObjectManager:
    """对象管理器 - 管理场景中的所有对象"""
    
    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.logger = get_logger(LoggerNames.GAME)
        self.objects: Dict[str, Any] = {}
        self.is_running = False
    
    def start(self):
        """启动对象管理器"""
        self.is_running = True
        self.logger.info("对象管理器启动成功")
    
    def stop(self):
        """停止对象管理器"""
        self.is_running = False
        self.logger.info("对象管理器已停止")
    
    def register_object(self, obj_id: str, obj: Any) -> bool:
        """注册对象"""
        try:
            self.objects[obj_id] = obj
            self.logger.debug(f"对象 '{obj_id}' 注册成功")
            return True
        except Exception as e:
            self.logger.error(f"注册对象 '{obj_id}' 失败: {e}")
            return False
    
    def get_object(self, obj_id: str) -> Optional[Any]:
        """获取对象"""
        return self.objects.get(obj_id)


class CommandManager:
    """命令管理器 - 管理场景命令系统"""
    
    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.logger = get_logger(LoggerNames.GAME)
        self.commands: Dict[str, Any] = {}
        self.is_running = False
    
    def start(self):
        """启动命令管理器"""
        self.is_running = True
        self.logger.info("命令管理器启动成功")
    
    def stop(self):
        """停止命令管理器"""
        self.is_running = False
        self.logger.info("命令管理器已停止")
    
    def register_command(self, cmd_name: str, cmd_handler: Any) -> bool:
        """注册命令"""
        try:
            self.commands[cmd_name] = cmd_handler
            self.logger.debug(f"命令 '{cmd_name}' 注册成功")
            return True
        except Exception as e:
            self.logger.error(f"注册命令 '{cmd_name}' 失败: {e}")
            return False


class ScriptManager:
    """脚本管理器 - 管理场景脚本和定时任务"""
    
    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.logger = get_logger(LoggerNames.GAME)
        self.scripts: Dict[str, Any] = {}
        self.is_running = False
    
    def start(self):
        """启动脚本管理器"""
        self.is_running = True
        self.logger.info("脚本管理器启动成功")
    
    def stop(self):
        """停止脚本管理器"""
        self.is_running = False
        self.logger.info("脚本管理器已停止")


class HookManager:
    """钩子管理器 - 管理事件钩子系统"""
    
    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.logger = get_logger(LoggerNames.GAME)
        self.hooks: Dict[str, List[Callable]] = {}
        self.is_running = False
    
    def start(self):
        """启动钩子管理器"""
        self.is_running = True
        self.logger.info("钩子管理器启动成功")
    
    def stop(self):
        """停止钩子管理器"""
        self.is_running = False
        self.logger.info("钩子管理器已停止")
    
    def register_hook(self, event_name: str, callback: Callable) -> bool:
        """注册事件钩子"""
        try:
            if event_name not in self.hooks:
                self.hooks[event_name] = []
            self.hooks[event_name].append(callback)
            self.logger.debug(f"钩子 '{event_name}' 注册成功")
            return True
        except Exception as e:
            self.logger.error(f"注册钩子 '{event_name}' 失败: {e}")
            return False
    
    def trigger_hook(self, event_name: str, *args, **kwargs) -> List[Any]:
        """触发事件钩子"""
        results = []
        if event_name in self.hooks:
            for callback in self.hooks[event_name]:
                try:
                    result = callback(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"执行钩子 '{event_name}' 失败: {e}")
        return results


class BaseGame(ABC):
    """场景基类 - 所有场景必须继承此类"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.description = getattr(self, 'description', '')
        self.author = getattr(self, 'author', '')
        
        # 场景状态
        self.is_running = False
        self.start_time = None
        self.engine = None
        
        # 日志
        self.logger = get_logger(LoggerNames.GAME)
        
        self.logger.info(f"场景 '{name}' v{version} 初始化完成")
    
    @abstractmethod
    def start(self) -> bool:
        """启动场景"""
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """停止场景"""
        pass
    
    @abstractmethod
    def get_commands(self) -> Dict[str, Any]:
        """获取场景命令列表"""
        pass
    
    def get_objects(self) -> Dict[str, Any]:
        """获取场景对象列表 - 可选实现"""
        return {}
    
    def get_hooks(self) -> Dict[str, Callable]:
        """获取场景事件钩子 - 可选实现"""
        return {}
    
    def execute_command(self, command: str, *args, **kwargs) -> Any:
        """执行场景命令 - 可选实现"""
        if hasattr(self, 'command_handler'):
            return self.command_handler.execute(command, *args, **kwargs)
        return None
    
    def get_help(self, command: str = None) -> Optional[str]:
        """获取场景帮助信息 - 可选实现"""
        if command:
            return f"命令 '{command}' 的帮助信息"
        return f"场景 '{self.name}' 的帮助信息"
    
    def get_player_count(self) -> int:
        """获取玩家数量 - 可选实现"""
        return 0
    
    def get_status(self) -> Dict[str, Any]:
        """获取场景状态"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "player_count": self.get_player_count()
        }
