"""
游戏加载器 - 负责动态加载和管理游戏模块

参考Evennia框架的插件系统设计，提供：
- 游戏模块发现和加载
- 热重载支持
- 依赖管理
- 版本兼容性检查
"""

import logging
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any, Type, Callable
import sys
import os

from .base import BaseGame
from app.core.paths import get_backend_root, get_project_root


class GameLoader:
    """游戏加载器"""
    
    def __init__(self, engine):
        self.engine = engine
        self.logger = logging.getLogger(f"game_engine.{engine.name}.loader")
        
        # 使用项目路径管理系统
        self.backend_root = get_backend_root()
        self.project_root = get_project_root()
        
        # 游戏搜索路径 - 基于项目路径系统
        self.search_paths = [
            self.backend_root / "app" / "games",    # 内置游戏
            self.project_root / "games",            # 外部游戏
            self.backend_root / "games",            # 后端games目录
        ]
        
        # 已加载的游戏
        self.loaded_games: Dict[str, BaseGame] = {}
        self.game_modules: Dict[str, Any] = {}
        
        self.logger.info("游戏加载器初始化完成")
    
    def discover_games(self) -> List[str]:
        """发现可用的游戏"""
        available_games = []
        
        for search_path in self.search_paths:
            if search_path.exists() and search_path.is_dir():
                try:
                    for game_dir in search_path.iterdir():
                        if game_dir.is_dir() and self._is_valid_game_directory(game_dir):
                            game_name = game_dir.name
                            if game_name not in available_games:
                                available_games.append(game_name)
                                self.logger.debug(f"发现游戏: {game_name} (路径: {game_dir})")
                except Exception as e:
                    self.logger.error(f"搜索路径 {search_path} 时出错: {e}")
        
        self.logger.info(f"发现 {len(available_games)} 个可用游戏: {available_games}")
        return available_games
    
    def _is_valid_game_directory(self, game_dir: Path) -> bool:
        """检查是否为有效的游戏目录"""
        required_files = ["__init__.py", "game.py"]
        
        for required_file in required_files:
            if not (game_dir / required_file).exists():
                return False
        
        return True

    def load_game(self, game_name: str) -> Optional[BaseGame]:
        """加载指定游戏"""
        try:
            if game_name in self.loaded_games:
                self.logger.warning(f"游戏 '{game_name}' 已加载")
                return self.loaded_games[game_name]
            
            # 查找游戏路径
            game_path = self._find_game_path(game_name)
            if not game_path:
                self.logger.error(f"找不到游戏 '{game_name}' 的目录")
                return None
            
            # 加载游戏模块
            game_module = self._load_game_module(game_name, game_path)
            if not game_module:
                self.logger.error(f"加载游戏模块 '{game_name}' 失败")
                return None
            
            # 创建游戏实例
            game_instance = self._create_game_instance(game_name, game_module)
            if not game_instance:
                self.logger.error(f"创建游戏实例 '{game_name}' 失败")
                return None
            
            # 初始化游戏实例
            if not game_instance.initialize_game():
                self.logger.error(f"初始化游戏实例 '{game_name}' 失败")
                return None

            # 启动游戏实例
            if not game_instance.start():
                self.logger.error(f"启动游戏实例 '{game_name}' 失败")
                return None

            # 注册到引擎
            if self.engine.register_game(game_instance):
                self.loaded_games[game_name] = game_instance
                self.game_modules[game_name] = game_module
                
                self.logger.info(f"游戏 '{game_name}' 加载成功")
                return game_instance
            else:
                self.logger.error(f"注册游戏 '{game_name}' 到引擎失败")
                return None
                
        except Exception as e:
            self.logger.error(f"加载游戏 '{game_name}' 失败: {e}")
            return None

    def _find_game_path(self, game_name: str) -> Optional[Path]:
        """查找游戏目录路径"""
        for search_path in self.search_paths:
            game_path = search_path / game_name
            if game_path.exists() and game_path.is_dir():
                return game_path
        return None

    def _load_game_module(self, game_name: str, game_path: Path) -> Optional[Any]:
        """加载游戏模块"""
        try:
            # 根据路径位置确定正确的模块名
            if self.backend_root / "app" / "games" in game_path.parents:
                # 内置游戏：app.games.{game_name}
                module_name = f"app.games.{game_name}"
                # 添加app目录到sys.path
                app_dir = str(self.backend_root / "app")
                if app_dir not in sys.path:
                    sys.path.insert(0, app_dir)
                    self.logger.debug(f"添加app目录到sys.path: {app_dir}")
            else:
                # 外部游戏：games.{game_name}
                module_name = f"games.{game_name}"
                # 添加games的父目录到sys.path
                games_parent = str(game_path.parent)
                if games_parent not in sys.path:
                    sys.path.insert(0, games_parent)
                    self.logger.debug(f"添加games父目录到sys.path: {games_parent}")
            
            # 如果模块已加载，先卸载
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # 导入游戏模块
            spec = importlib.util.spec_from_file_location(
                module_name, 
                game_path / "__init__.py"
            )
            
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
            else:
                self.logger.error(f"无法创建游戏模块 '{game_name}' 的规范")
                return None
                
        except Exception as e:
            self.logger.error(f"加载游戏模块 '{game_name}' 失败: {e}")
            return None

    def _create_game_instance(self, game_name: str, game_module: Any) -> Optional[BaseGame]:
        """创建游戏实例"""
        try:
            # 获取游戏实例获取函数
            get_game_instance_func = getattr(game_module, "get_game_instance", None)
            if not get_game_instance_func:
                self.logger.error(f"游戏模块 '{game_name}' 中没有找到 'get_game_instance' 函数")
                return None
            
            # 验证是否为可调用对象
            if not callable(get_game_instance_func):
                self.logger.error(f"游戏模块 '{game_name}' 的 'get_game_instance' 不是可调用对象")
                return None
            
            # 调用函数获取游戏实例
            game_instance = get_game_instance_func()
            
            return game_instance
            
        except Exception as e:
            self.logger.error(f"创建游戏实例 '{game_name}' 失败: {e}")
            return None
    
    def unload_game(self, game_name: str) -> bool:
        """卸载游戏"""
        try:
            if game_name not in self.loaded_games:
                self.logger.warning(f"游戏 '{game_name}' 未加载")
                return False
            
            # 从引擎注销
            if self.engine.unregister_game(game_name):
                # 清理资源
                del self.loaded_games[game_name]
                if game_name in self.game_modules:
                    del self.game_modules[game_name]
                
                self.logger.info(f"游戏 '{game_name}' 卸载成功")
                return True
            else:
                self.logger.error(f"从引擎注销游戏 '{game_name}' 失败")
                return False
                
        except Exception as e:
            self.logger.error(f"卸载游戏 '{game_name}' 失败: {e}")
            return False
    
    def reload_game(self, game_name: str) -> Optional[BaseGame]:
        """重新加载指定游戏"""
        try:
            self.logger.info(f"开始重新加载游戏 '{game_name}'")
            
            # 先卸载
            if self.unload_game(game_name):
                # 再加载
                return self.load_game(game_name)
            else:
                self.logger.error(f"卸载游戏 '{game_name}' 失败，无法重新加载")
                return None
                
        except Exception as e:
            self.logger.error(f"重新加载游戏 '{game_name}' 失败: {e}")
            return None
    
    def get_loaded_games(self) -> List[str]:
        """获取已加载的游戏列表"""
        return list(self.loaded_games.keys())
    
    def get_game_info(self, game_name: str) -> Optional[Dict[str, Any]]:
        """获取游戏信息"""
        if game_name not in self.loaded_games:
            return None
        
        game_instance = self.loaded_games[game_name]
        return {
            "name": game_instance.name,
            "version": game_instance.version,
            "description": getattr(game_instance, 'description', ''),
            "author": getattr(game_instance, 'author', ''),
            "status": "loaded"
        }
    
    def auto_load_games(self) -> List[str]:
        """自动加载所有发现的游戏"""
        available_games = self.discover_games()
        loaded_games = []
        
        for game_name in available_games:
            try:
                if self.load_game(game_name):
                    loaded_games.append(game_name)
            except Exception as e:
                self.logger.error(f"自动加载游戏 '{game_name}' 失败: {e}")
        
        self.logger.info(f"自动加载完成，成功加载 {len(loaded_games)} 个游戏: {loaded_games}")
        return loaded_games
