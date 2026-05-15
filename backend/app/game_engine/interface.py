"""
场景接口 - 提供场景与引擎的交互接口

参考Evennia框架的接口设计，提供：
- 场景生命周期管理
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
    """场景接口 - 场景与引擎的交互桥梁"""

    def __init__(self, engine):
        self.engine = engine
        self.logger = logging.getLogger(f'game_engine.{engine.name}.interface')
        self.logger.info('World interface initialization complete')

    def register_game_commands(self, game: BaseGame) -> bool:
        """注册场景命令到全局命令注册表"""
        try:
            if not hasattr(game, 'get_commands'):
                self.logger.warning(f"world '{game.name}' has no get_commands method")
                return True
            commands = game.get_commands()
            if not commands:
                self.logger.info(f"world '{game.name}' no commands to register")
                return True
            if not isinstance(commands, list):
                self.logger.error(f"world '{game.name}' command contract invalid: expected list, got {type(commands)}")
                return False
            from app.commands.init_commands import register_game_commands
            ok = register_game_commands(game.name, commands)
            if ok:
                self.logger.info(f"world '{game.name}' registered {len(commands)} commands")
            return ok
        except Exception as e:
            self.logger.error(f"Register world '{game.name}' command failed: {e}")
            return False

    def unregister_game_commands(self, game: BaseGame) -> bool:
        """从全局命令注册表注销场景命令"""
        try:
            from app.commands.init_commands import unregister_game_commands
            ok = unregister_game_commands(game.name)
            if ok:
                self.logger.info(f"world '{game.name}' command unregistered")
            return ok
        except Exception as e:
            self.logger.error(f"Unregister world '{game.name}' command failed: {e}")
            return False

    def register_game_objects(self, game: BaseGame) -> bool:
        """注册场景对象到引擎"""
        try:
            if not hasattr(game, 'get_objects'):
                self.logger.warning(f"world '{game.name}' has no get_objects method")
                return True
            objects = game.get_objects()
            if not objects:
                self.logger.info(f"world '{game.name}' no objects to register")
                return True
            registered_count = 0
            for (obj_id, obj) in objects.items():
                if self.engine.object_manager.register_object(obj_id, obj):
                    registered_count += 1
                    self.logger.debug(f"object '{obj_id}' registered successfully")
                else:
                    self.logger.error(f"object '{obj_id}' registration failed")
            self.logger.info(f"world '{game.name}' registered {registered_count} objects")
            return True
        except Exception as e:
            self.logger.error(f"Register world '{game.name}' object failed: {e}")
            return False

    def register_game_hooks(self, game: BaseGame) -> bool:
        """注册场景事件钩子到引擎"""
        try:
            if not hasattr(game, 'get_hooks'):
                self.logger.warning(f"world '{game.name}' has no get_hooks method")
                return True
            hooks = game.get_hooks()
            if not hooks:
                self.logger.info(f"world '{game.name}' no hooks to register")
                return True
            registered_count = 0
            for (event_name, callback) in hooks.items():
                if self.engine.hook_manager.register_hook(event_name, callback):
                    registered_count += 1
                    self.logger.debug(f"hook '{event_name}' registered successfully")
                else:
                    self.logger.error(f"hook '{event_name}' registration failed")
            self.logger.info(f"world '{game.name}' registered {registered_count} hooks")
            return True
        except Exception as e:
            self.logger.error(f"Register world '{game.name}' hook failed: {e}")
            return False

    def trigger_game_event(self, event_name: str, *args, **kwargs) -> List[Any]:
        """触发场景事件"""
        try:
            results = self.engine.hook_manager.trigger_hook(event_name, *args, **kwargs)
            if results:
                self.logger.debug(f"Event '{event_name}' triggered successfully, returned {len(results)} results")
            return results
        except Exception as e:
            self.logger.error(f"Trigger event '{event_name}' failed: {e}")
            return []

    def get_game_status(self, game_name: str) -> Optional[Dict[str, Any]]:
        """获取场景状态"""
        try:
            game = self.engine.get_game(game_name)
            if not game:
                return None
            status = {'name': game.name, 'version': game.version, 'is_running': game.is_running, 'start_time': getattr(game, 'start_time', None), 'player_count': getattr(game, 'get_player_count', lambda : 0)(), 'description': getattr(game, 'description', ''), 'author': getattr(game, 'author', '')}
            if status['start_time']:
                status['start_time'] = status['start_time'].isoformat()
            return status
        except Exception as e:
            self.logger.error(f"Get world '{game_name}' state failed: {e}")
            return None

    def list_all_games_status(self) -> List[Dict[str, Any]]:
        """列出所有场景状态"""
        try:
            games_status = []
            for game_name in self.engine.list_games():
                status = self.get_game_status(game_name)
                if status:
                    games_status.append(status)
            return games_status
        except Exception as e:
            self.logger.error(f'Failed to get state for all worlds: {e}')
            return []

    def execute_game_command(self, game_name: str, command: str, *args, **kwargs) -> Any:
        """执行场景命令"""
        try:
            game = self.engine.get_game(game_name)
            if not game:
                self.logger.error(f"world '{game_name}' does not exist")
                return None
            if not hasattr(game, 'execute_command'):
                self.logger.error(f"world '{game_name}' has no execute_command method")
                return None
            result = game.execute_command(command, *args, **kwargs)
            self.logger.debug(f"world '{game_name}' command '{command}' executed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Execute world '{game_name}' command '{command}' failed: {e}")
            return None

    def get_available_commands(self, game_name: str) -> List[str]:
        """获取场景可用命令列表"""
        try:
            game = self.engine.get_game(game_name)
            if not game:
                return []
            if hasattr(game, 'get_commands'):
                commands = game.get_commands()
                return list(commands.keys()) if commands else []
            return []
        except Exception as e:
            self.logger.error(f"Get world '{game_name}' available commands failed: {e}")
            return []

    def get_game_help(self, game_name: str, command: str=None) -> Optional[str]:
        """获取场景帮助信息"""
        try:
            game = self.engine.get_game(game_name)
            if not game:
                return None
            if hasattr(game, 'get_help'):
                return game.get_help(command)
            return None
        except Exception as e:
            self.logger.error(f"Get world '{game_name}' help info failed: {e}")
            return None
