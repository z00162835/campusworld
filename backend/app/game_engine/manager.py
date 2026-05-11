"""
引擎管理器 - 整合所有内容引擎组件

提供统一的内容引擎管理接口，包括：
- 引擎生命周期管理
- 内容加载和管理
- SSH系统集成
- 配置管理
"""
import logging
from typing import Any, Dict, List, Optional
from app.core.config_manager import get_setting
from .base import GameEngine
from .interface import GameInterface
from .loader import GameLoader

class CampusWorldGameEngine(GameEngine):
    """CampusWorld内容引擎 - 继承自GameEngine基类"""

    def __init__(self):
        super().__init__('CampusWorld', '1.0.0')
        self.loader = GameLoader(self)
        self.interface = GameInterface(self)

    def start(self) -> bool:
        """启动内容引擎"""
        try:
            if not super().start():
                return False
            if get_setting('game_engine.load_installed_worlds_on_start', True):
                loaded_installed = self.loader.load_installed_worlds_at_start()
                self.logger.info('game_engine.load_installed_worlds_on_start loaded=%s', loaded_installed)
            else:
                self.logger.info('game_engine.load_installed_worlds_on_start=false; skip loading installed worlds at startup')
            legacy_discover = get_setting('game_engine.auto_load_discovered_on_start', None)
            if legacy_discover is None:
                legacy_discover = get_setting('game_engine.auto_load_on_start', False)
            if legacy_discover:
                worlds_cfg = get_setting('game_engine.auto_load_worlds', None)
                loaded_extra = self.loader.auto_load_games(only_world_ids=worlds_cfg if isinstance(worlds_cfg, list) else None)
                self.logger.info('auto_load_discovered / legacy auto_load_on_start loaded=%s', loaded_extra)
            return True
        except Exception as e:
            self.logger.error(f'Failed to start content engine: {e}')
            return False

    def stop(self) -> bool:
        """停止内容引擎"""
        return super().stop()

    def get_engine_info(self) -> Dict[str, Any]:
        """获取内容引擎详细信息"""
        info = super().get_status()
        loaded = self.loader.get_loaded_games() if self.loader else []
        runtime_states: Dict[str, Any] = {}
        for game_name in loaded:
            runtime_states[game_name] = self.loader.get_runtime_state(game_name)
        info.update({'loader_status': 'running' if self.loader else 'stopped', 'interface_status': 'running' if self.interface else 'stopped', 'available_games': self.loader.discover_games() if self.loader else [], 'loaded_games': loaded, 'runtime_states': runtime_states})
        return info

    def stop_engine(self) -> bool:
        """停止内容引擎"""
        return self.stop()

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
            self.logger = logging.getLogger('game_engine.manager')
            self.initialized = True

    def initialize_engine(self) -> bool:
        """初始化内容引擎"""
        try:
            if self.engine:
                self.logger.warning('Content engine already exists')
                return True
            self.engine = CampusWorldGameEngine()
            return True
        except Exception as e:
            self.logger.error(f'Failed to initialize content engine: {e}')
            return False

    def start_engine(self) -> bool:
        """启动内容引擎"""
        try:
            if not self.engine:
                if not self.initialize_engine():
                    return False
            if self.engine.start():
                return True
            else:
                self.logger.error('Failed to start content engine')
                return False
        except Exception as e:
            self.logger.error(f'Failed to start content engine: {e}')
            return False

    def stop_engine(self) -> bool:
        """停止内容引擎"""
        try:
            if not self.engine:
                self.logger.warning('Content engine does not exist')
                return True
            if self.engine.stop():
                return True
            else:
                self.logger.error('Failed to stop content engine')
                return False
        except Exception as e:
            self.logger.error(f'Failed to stop content engine: {e}')
            return False

    def get_engine(self) -> Optional[CampusWorldGameEngine]:
        """获取内容引擎实例"""
        return self.engine

    def get_engine_status(self) -> Dict[str, Any]:
        """获取内容引擎状态"""
        if not self.engine:
            return {'status': 'not_initialized'}
        return self.engine.get_engine_info()

    def load_game(self, game_name: str) -> Dict[str, Any]:
        """加载内容（结构化返回）"""
        try:
            if not self.engine:
                self.logger.error('Content engine not initialized')
                return {'ok': False, 'world_id': game_name, 'status_before': 'not_initialized', 'status_after': 'not_initialized', 'error_code': 'WORLD_INTERNAL_ERROR', 'message': 'engine not initialized', 'details': {}}
            return self.engine.loader.load_game(game_name)
        except Exception as e:
            self.logger.error(f"Load content '{game_name}' failed: {e}")
            return {'ok': False, 'world_id': game_name, 'status_before': 'unknown', 'status_after': 'broken', 'error_code': 'WORLD_INTERNAL_ERROR', 'message': f'load exception: {e}', 'details': {}}

    def unload_game(self, game_name: str) -> Dict[str, Any]:
        """卸载内容（结构化返回）"""
        try:
            if not self.engine:
                self.logger.error('Content engine not initialized')
                return {'ok': False, 'world_id': game_name, 'status_before': 'not_initialized', 'status_after': 'not_initialized', 'error_code': 'WORLD_INTERNAL_ERROR', 'message': 'engine not initialized', 'details': {}}
            return self.engine.loader.unload_game(game_name)
        except Exception as e:
            self.logger.error(f"Unload content '{game_name}' failed: {e}")
            return {'ok': False, 'world_id': game_name, 'status_before': 'unknown', 'status_after': 'broken', 'error_code': 'WORLD_INTERNAL_ERROR', 'message': f'unload exception: {e}', 'details': {}}

    def reload_game(self, game_name: str) -> Dict[str, Any]:
        """重新加载内容（结构化返回）"""
        try:
            if not self.engine:
                self.logger.error('Content engine not initialized')
                return {'ok': False, 'world_id': game_name, 'status_before': 'not_initialized', 'status_after': 'not_initialized', 'error_code': 'WORLD_INTERNAL_ERROR', 'message': 'engine not initialized', 'details': {}}
            return self.engine.loader.reload_game(game_name)
        except Exception as e:
            self.logger.error(f"Reload content '{game_name}' failed: {e}")
            return {'ok': False, 'world_id': game_name, 'status_before': 'unknown', 'status_after': 'broken', 'error_code': 'WORLD_INTERNAL_ERROR', 'message': f'reload exception: {e}', 'details': {}}

    def list_games(self) -> List[str]:
        """列出所有内容"""
        try:
            if not self.engine:
                return []
            return self.engine.loader.discover_games()
        except Exception as e:
            self.logger.error(f'Failed to list content: {e}')
            return []

    def get_game_status(self, game_name: str) -> Optional[Dict[str, Any]]:
        """获取内容状态"""
        try:
            if not self.engine:
                return None
            return self.engine.interface.get_game_status(game_name)
        except Exception as e:
            self.logger.error(f"Get content '{game_name}' state failed: {e}")
            return None

    def execute_game_command(self, game_name: str, command: str, *args, **kwargs) -> Any:
        """执行内容命令"""
        try:
            if not self.engine:
                self.logger.error('Content engine not initialized')
                return None
            return self.engine.interface.execute_game_command(game_name, command, *args, **kwargs)
        except Exception as e:
            self.logger.error(f"Execute content '{game_name}' command '{command}' failed: {e}")
            return None
game_engine_manager = GameEngineManager()
