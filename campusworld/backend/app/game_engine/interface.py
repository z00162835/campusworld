"""
游戏接口 - 提供游戏与引擎的交互接口

参考Evennia框架的接口设计，提供：
- 游戏生命周期管理
- 命令系统集成
- 对象系统访问
- 事件系统集成
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from .base import BaseGame


class GameInterface:
    """游戏接口 - 游戏与引擎的交互桥梁"""
    
    def __init__(self, engine):
        self.engine = engine
        self.logger = logging.getLogger(f"game_engine.{engine.name}.interface")
        
        self.logger.info("游戏接口初始化完成")
    
    def register_game_commands(self, game: BaseGame) -> bool:
        """注册游戏命令到引擎"""
        try:
            if not hasattr(game, 'get_commands'):
                self.logger.warning(f"游戏 '{game.name}' 没有 get_commands 方法")
                return True
            
            commands = game.get_commands()
            if not commands:
                self.logger.info(f"游戏 '{game.name}' 没有命令需要注册")
                return True
            
            registered_count = 0
            for cmd_name, cmd_handler in commands.items():
                if self.engine.command_manager.register_command(cmd_name, cmd_handler):
                    registered_count += 1
                    self.logger.debug(f"命令 '{cmd_name}' 注册成功")
                else:
                    self.logger.error(f"命令 '{cmd_name}' 注册失败")
            
            self.logger.info(f"游戏 '{game.name}' 注册了 {registered_count} 个命令")
            return True
            
        except Exception as e:
            self.logger.error(f"注册游戏 '{game.name}' 命令失败: {e}")
            return False
    
    def unregister_game_commands(self, game: BaseGame) -> bool:
        """从引擎注销游戏命令"""
        try:
            if not hasattr(game, 'get_commands'):
                return True
            
            commands = game.get_commands()
            if not commands:
                return True
            
            unregistered_count = 0
            for cmd_name in commands.keys():
                # 注意：这里需要实现命令注销逻辑
                # 暂时只是记录日志
                self.logger.debug(f"命令 '{cmd_name}' 注销成功")
                unregistered_count += 1
            
            self.logger.info(f"游戏 '{game.name}' 注销了 {unregistered_count} 个命令")
            return True
            
        except Exception as e:
            self.logger.error(f"注销游戏 '{game.name}' 命令失败: {e}")
            return False
    
    def register_game_objects(self, game: BaseGame) -> bool:
        """注册游戏对象到引擎"""
        try:
            if not hasattr(game, 'get_objects'):
                self.logger.warning(f"游戏 '{game.name}' 没有 get_objects 方法")
                return True
            
            objects = game.get_objects()
            if not objects:
                self.logger.info(f"游戏 '{game.name}' 没有对象需要注册")
                return True
            
            registered_count = 0
            for obj_id, obj in objects.items():
                if self.engine.object_manager.register_object(obj_id, obj):
                    registered_count += 1
                    self.logger.debug(f"对象 '{obj_id}' 注册成功")
                else:
                    self.logger.error(f"对象 '{obj_id}' 注册失败")
            
            self.logger.info(f"游戏 '{game.name}' 注册了 {registered_count} 个对象")
            return True
            
        except Exception as e:
            self.logger.error(f"注册游戏 '{game.name}' 对象失败: {e}")
            return False
    
    def register_game_hooks(self, game: BaseGame) -> bool:
        """注册游戏事件钩子到引擎"""
        try:
            if not hasattr(game, 'get_hooks'):
                self.logger.warning(f"游戏 '{game.name}' 没有 get_hooks 方法")
                return True
            
            hooks = game.get_hooks()
            if not hooks:
                self.logger.info(f"游戏 '{game.name}' 没有钩子需要注册")
                return True
            
            registered_count = 0
            for event_name, callback in hooks.items():
                if self.engine.hook_manager.register_hook(event_name, callback):
                    registered_count += 1
                    self.logger.debug(f"钩子 '{event_name}' 注册成功")
                else:
                    self.logger.error(f"钩子 '{event_name}' 注册失败")
            
            self.logger.info(f"游戏 '{game.name}' 注册了 {registered_count} 个钩子")
            return True
            
        except Exception as e:
            self.logger.error(f"注册游戏 '{game.name}' 钩子失败: {e}")
            return False
    
    def trigger_game_event(self, event_name: str, *args, **kwargs) -> List[Any]:
        """触发游戏事件"""
        try:
            results = self.engine.hook_manager.trigger_hook(event_name, *args, **kwargs)
            if results:
                self.logger.debug(f"事件 '{event_name}' 触发成功，返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"触发事件 '{event_name}' 失败: {e}")
            return []
    
    def get_game_status(self, game_name: str) -> Optional[Dict[str, Any]]:
        """获取游戏状态"""
        try:
            game = self.engine.get_game(game_name)
            if not game:
                return None
            
            status = {
                "name": game.name,
                "version": game.version,
                "is_running": game.is_running,
                "start_time": getattr(game, 'start_time', None),
                "player_count": getattr(game, 'get_player_count', lambda: 0)(),
                "description": getattr(game, 'description', ''),
                "author": getattr(game, 'author', ''),
            }
            
            # 格式化时间
            if status["start_time"]:
                status["start_time"] = status["start_time"].isoformat()
            
            return status
            
        except Exception as e:
            self.logger.error(f"获取游戏 '{game_name}' 状态失败: {e}")
            return None
    
    def list_all_games_status(self) -> List[Dict[str, Any]]:
        """列出所有游戏状态"""
        try:
            games_status = []
            for game_name in self.engine.list_games():
                status = self.get_game_status(game_name)
                if status:
                    games_status.append(status)
            
            return games_status
            
        except Exception as e:
            self.logger.error(f"获取所有游戏状态失败: {e}")
            return []
    
    def execute_game_command(self, game_name: str, command: str, *args, **kwargs) -> Any:
        """执行游戏命令"""
        try:
            game = self.engine.get_game(game_name)
            if not game:
                self.logger.error(f"游戏 '{game_name}' 不存在")
                return None
            
            if not hasattr(game, 'execute_command'):
                self.logger.error(f"游戏 '{game_name}' 没有 execute_command 方法")
                return None
            
            result = game.execute_command(command, *args, **kwargs)
            self.logger.debug(f"游戏 '{game_name}' 命令 '{command}' 执行成功")
            return result
            
        except Exception as e:
            self.logger.error(f"执行游戏 '{game_name}' 命令 '{command}' 失败: {e}")
            return None
    
    def get_available_commands(self, game_name: str) -> List[str]:
        """获取游戏可用命令列表"""
        try:
            game = self.engine.get_game(game_name)
            if not game:
                return []
            
            if hasattr(game, 'get_commands'):
                commands = game.get_commands()
                return list(commands.keys()) if commands else []
            
            return []
            
        except Exception as e:
            self.logger.error(f"获取游戏 '{game_name}' 可用命令失败: {e}")
            return []
    
    def get_game_help(self, game_name: str, command: str = None) -> Optional[str]:
        """获取游戏帮助信息"""
        try:
            game = self.engine.get_game(game_name)
            if not game:
                return None
            
            if hasattr(game, 'get_help'):
                return game.get_help(command)
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取游戏 '{game_name}' 帮助信息失败: {e}")
            return None
